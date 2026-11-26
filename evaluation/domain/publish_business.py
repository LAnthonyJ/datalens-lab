"""Join masked grades only after adjudication and publish all paired business answers."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from paired import paired, business_rows, load_file

def publish(work,out):
    pack=list(csv.DictReader((work/'confirm-a.tsv').open(encoding='utf8'),delimiter='\t'))
    blind=work/'formal-blind';key=load_file(blind/'key.jsonl');votes=load_file(blind/'adjudicated.jsonl')
    ids={r['token']:r for r in key};packet={r['token']:r for r in load_file(blind/'packet.jsonl')}
    pairs=business_rows(key,votes)
    if len(pairs)!=400:raise ValueError('Expected 400 pairs')
    rows={}; agreement=0; category=Counter();flags=Counter();metrics=Counter();margins=Counter();limits=Counter()
    for v in votes:
        token=v['token'];k=ids[token];question=packet[token];qid=k['id'];group,arm=qid.rsplit('-',1)
        gold=pack[int(group.split('-')[-1])-1];cat=gold['category']
        row=rows.setdefault(qid,dict(id=qid,category=cat,form=gold['form'],source_table=gold['source_table'],prompt=question['prompt'],criterion=question['criterion']))
        first,second=v['reviewer1'],v['reviewer2'];agreement+=first==second
        margins['first']+=first;margins['second']+=second
        for m in k['models']:
            model='base' if m=='baseline' else m
            receipt=json.loads((work/('confirm-a-'+model)/(qid+'.json')).read_text(encoding='utf8'))
            assert receipt['answer']==question['answer']
            row[model]=dict(answer=question['answer'],generation=receipt['status'],token=token,reviewer1=first,reviewer2=second,
                            passed=v['passed'],reason=v['reason'],issue=v.get('issue'))
            metrics[(model,arm)]+=v['passed'];limits[(model,receipt['status'])]+=1
            if v.get('issue'):flags[(model,arm,v['issue'])]+=1
    assert len(rows)==800 and all('lora' in r and 'base' in r for r in rows.values())
    with (out/'business-answers.jsonl').open('w',encoding='utf8') as f:
        # Some length-limited generations ended in a partial UTF-8 character.
        # JSON escapes preserve the recorded code units exactly on replay.
        for k in sorted(rows):print(json.dumps(rows[k],ensure_ascii=True),file=f)
    for p in pairs:
        cat=pack[int(p['id'].split('-')[-1])-1]['category']
        for m in ('base','lora'):category[cat,m]+=p[m]
    with (out/'business-scenarios.csv').open('w',newline='',encoding='utf8') as f:
        fields=['scenario','category','source_table','base_missing','base_complete','base_pair','lora_missing','lora_complete','lora_pair'];writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for p in pairs:
            gold=pack[int(p['id'].split('-')[-1])-1];record=dict(scenario=p['id'],category=gold['category'],source_table=gold['source_table'])
            for m in ('base','lora'):
                for arm in ('missing','complete'):record[m+'_'+arm]=rows[p['id']+'-'+arm][m]['passed']
                record[m+'_pair']=p[m]
            writer.writerow(record)
    summary=paired(pairs);n=len(votes);rate=agreement/n
    chance=(margins['first']*margins['second']+(n-margins['first'])*(n-margins['second']))/(n*n)
    summary.update(agree=agreement,rated=n,kappa=(rate-chance)/(1-chance) if chance<1 else None,
        categories={cat:{m:category[cat,m] for m in ('base','lora')} for cat in sorted({r['category'] for r in pack})},
        arm_pass={m:{a:metrics[m,a] for a in ('missing','complete')} for m in ('base','lora')},
        issues={'/'.join(k):v for k,v in flags.items()},generation={'/'.join(k):v for k,v in limits.items()},
        first_gain=next((p['id'] for p in pairs if p['lora'] and not p['base']),None),
        regression_ids=[p['id'] for p in pairs if p['base'] and not p['lora']])
    (out/'business-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print({k:v for k,v in summary.items() if k not in ('regression_ids','categories')})
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();publish(a.work,a.out)
