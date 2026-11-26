"""Compare fully paired business results by reviewer before adjudication."""
import json
from pathlib import Path
import argparse
from paired import paired

def main():
    p=argparse.ArgumentParser();p.add_argument('answers',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();rows={r['id']:r for r in map(json.loads,a.answers.read_text(encoding='utf8').splitlines())};cases=sorted({i.rsplit('-',1)[0] for i in rows})
    assert len(rows)==800 and len(cases)==400
    results={}
    for judge in ['reviewer1','reviewer2','passed']:
        pairs=[]
        for case in cases:
            pair={m:all(rows[case+'-'+arm][m][judge] for arm in ('missing','complete')) for m in ('base','lora')}
            pairs.append(dict(id=case,cluster=case,**pair))
        results[judge]=paired(pairs)
    a.out.write_text(json.dumps(results,indent=2),encoding='utf8')
    print([(k,r['base'],r['lora'],r['meets_threshold']) for k,r in results.items()])
if __name__=='__main__':main()
