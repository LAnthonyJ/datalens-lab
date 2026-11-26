"""Separate failure to return executable SQL from wrong results on executable queries."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
from sql_cases import fixture, statement, execute

def main():
    p=argparse.ArgumentParser();p.add_argument('pack',type=Path);p.add_argument('answers',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
    rows={r['id']:r for r in map(json.loads,a.answers.read_text(encoding='utf8').splitlines())}
    flags={};counts={m:Counter() for m in ('base','lora')};both=Counter()
    for s in json.loads(a.pack.read_text(encoding='utf8')):
        dbs=[fixture(s,extra) for extra in [{},*s['extra']]]
        try:
            for i,c in enumerate(s['cases'],1):
                key=s['id']+'-'+str(i);r=rows[key];ok={}
                for m in counts:
                    sql=statement(r[m+'_answer'])
                    try:
                        if not sql:raise ValueError('Empty statement')
                        for db in dbs:execute(db,sql)
                    except (sqlite3.Error,ValueError):ok[m]=False
                    else:ok[m]=True
                    assert ok[m] or not r[m+'_pass']
                    counts[m]['executable']+=ok[m];counts[m]['correct']+=r[m+'_pass']
                if all(ok.values()):
                    both['items']+=1
                    for m in counts:both[m]+=r[m+'_pass']
                    both['improved']+=r['lora_pass'] and not r['base_pass'];both['regressed']+=r['base_pass'] and not r['lora_pass']
                flags[key]=ok
        finally:
            for db in dbs:db.close()
    assert len(flags)==len(rows)==480
    out=dict(models=counts,same_questions_both_executable=both,by_question=flags)
    a.out.write_text(json.dumps(out,indent=2),encoding='utf8')
    print(counts,both)
if __name__=='__main__':main()
