"""Export complete, first-attempt paired SQL answers with auditable grades."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import numpy as np

def read(p):return json.loads(p.read_text(encoding='utf8'))

def publish(work,out,task):
    if task in ('spider','long','short'):
        name,count={'spider':('spider',1034),'long':('spider-long',100),'short':('spider-short',100)}[task]
        by_model={m:{r['id']:r for p in (work/f'{name}-{m}-grades').glob('*.json') for r in [read(p)]} for m in ('base','lora')}
    else:
        count=480;name='confirm-b'
        by_model={m:{r['id']:r for r in map(json.loads,(work/f'{name}-{m}-grades.jsonl').read_text(encoding='utf8').splitlines())} for m in ('base','lora')}
    if len(by_model['base'])!=count or by_model['base'].keys()!=by_model['lora'].keys():raise ValueError("Incomplete scoring")
    rows=[]
    for key,one in sorted(by_model['base'].items()):
        item=dict(id=key,database=one['database'])
        if 'category' in one:item['category']=one['category']
        for m in ('base','lora'):
            answer=read(work/f'{name}-{m}'/(key+'.json'))
            item[m+'_answer']=answer['answer']; item[m+'_status']=answer['status'];item[m+'_pass']=by_model[m][key]['passed']
        rows.append(item)
    with (out/(name+'-answers.jsonl')).open('w',encoding='utf8') as f:
        for r in rows:print(json.dumps(r,ensure_ascii=False),file=f)
    with (out/(name+'-grades.csv')).open('w',encoding='utf8',newline='') as f:
        keys=[k for k in rows[0] if not k.endswith('_answer')]
        writer=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    from paired import paired
    normalized=[dict(id=r['id'],cluster=r['database'],base=r['base_pass'],lora=r['lora_pass']) for r in rows]
    if task=='sql':
        result=paired(normalized)
    else:
        # Dev databases vary in size, so bootstrap the ratio of sums to retain the question-weighted estimand.
        groups={}
        for r in normalized:
            n,d=groups.get(r['cluster'],(0,0));groups[r['cluster']]=n+1,d+int(r['lora'])-int(r['base'])
        data=np.array([v for _,v in sorted(groups.items())])
        idx=np.random.default_rng(20261126).integers(0,len(data),size=(20000,len(data)))
        sums=data[idx].sum(axis=1)
        result=dict(items=count,clusters=len(groups),base=sum(r['base'] for r in normalized),lora=sum(r['lora'] for r in normalized),
                    delta_pp=100*sum(d for n,d in groups.values())/count,
                    ci97_5_pp=list(np.quantile(100*sums[:,1]/sums[:,0],[.0125,.9875])),
                    improved=sum(r['lora'] and not r['base'] for r in normalized),regressed=sum(r['base'] and not r['lora'] for r in normalized))
    result['generation']={m:dict(Counter(r[m+'_status'] for r in rows)) for m in ('base','lora')}
    result['first_gain']=next((r['id'] for r in rows if not r['base_pass'] and r['lora_pass']),None)
    result['regression_ids']=[r['id'] for r in rows if r['base_pass'] and not r['lora_pass']]
    if 'category' in rows[0]:
        result['categories']={cat:{m:sum(r[m+'_pass'] for r in rows if r['category']==cat) for m in ('base','lora')} for cat in sorted(set(r['category'] for r in rows))}
    (out/(name+'-summary.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
    print({k:v for k,v in result.items() if k!='regression_ids'})
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);p.add_argument('out',type=Path);p.add_argument('task',choices=['spider','sql','long','short'])
    a=p.parse_args();a.out.mkdir(exist_ok=True,parents=True);publish(a.work,a.out,a.task)
