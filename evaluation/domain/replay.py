"""Replay published SQL answers and recompute the business-pair score without weights."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from paired import load_file, paired, sql_rows

HERE=Path(__file__).resolve().parent
RESULTS=HERE/'results'

def export_sql(rows,folder):
    folder.mkdir(parents=True,exist_ok=True)
    for model in ('base','lora'):
        out=folder/model
        out.mkdir(exist_ok=False)
        for r in rows:
            key=r['id']
            if not re.fullmatch(r'[A-Za-z0-9_-]+',key):raise ValueError(key)
            (out/(key+'.json')).write_text(json.dumps(dict(id=key,answer=r[model+'_answer'],status=r[model+'_status'])),encoding='utf8')

def check(name,rows):
    got=paired(rows);record=json.loads((RESULTS/(name+'-summary.json')).read_text(encoding='utf8'))
    for k in ('base','lora','items','clusters','improved','regressed','ci97_5_pp','meets_threshold'):
        if got[k]!=record[k]:raise ValueError(f"{name} summary differs for {k}")
    print(f"{name}: {got['base']} to {got['lora']} of {got['items']}")

def replay_sql(work):
    rows=load_file(RESULTS/'confirm-b-answers.jsonl');export_sql(rows,work)
    grades=[]
    for m in ('base','lora'):
        output=work/(m+'-grades.jsonl')
        subprocess.run([sys.executable,str(HERE/'sql_cases.py'),'--pack',str(HERE/'confirm-db.json'),'--answers',str(work/m),'--out',str(output)],check=True)
        rs=load_file(output);flags={r['id']:r['passed'] for r in rs}
        if any(flags[r['id']]!=r[m+'_pass'] for r in rows):raise ValueError('SQL score mismatch')
        grades.append(rs)
    check('confirm-b',sql_rows(*grades))

def replay_business():
    answers=load_file(RESULTS/'business-answers.jsonl')
    arms={r['id']:r for r in answers}
    if len(arms)!=800:raise ValueError('Incomplete business answers')
    cases={k.rsplit('-',1)[0] for k in arms};pairs=[]
    for case in sorted(cases):
        pairs.append(dict(id=case,cluster=case,**{m:all(arms[case+'-'+arm][m]['passed'] for arm in ('missing','complete')) for m in ('base','lora')}))
    check('business',pairs)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('task',choices=['sql','business','export-spider','export-long'])
    p.add_argument('--out',type=Path);a=p.parse_args()
    if a.task=='sql':
        with tempfile.TemporaryDirectory() as temp:replay_sql(Path(temp))
    elif a.task=='business':replay_business()
    elif not a.out:p.error('--out is required for export')
    else:
        name='spider' if a.task=='export-spider' else 'spider-long'
        export_sql(load_file(RESULTS/(name+'-answers.jsonl')),a.out)
