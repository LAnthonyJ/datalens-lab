from pathlib import Path
import json, csv,re
from collections import Counter
import argparse
p=argparse.ArgumentParser(description='Compare the core SQL shapes with prior project SQL.')
p.add_argument('project',type=Path);p.add_argument('pack',type=Path);p.add_argument('out',type=Path)
args=p.parse_args();root=args.project
data=json.loads(args.pack.read_text(encoding='utf8'))
sources=[root/'runs/english-sql-clarify/train.jsonl',root/'quality/heldout.jsonl',root/'runs/datamind-2k/train.jsonl',root/'runs/datamind-2k/validation.jsonl']
sources+=list((root/'runs/english-lr-grid').glob('confirm-start.jsonl'))+list((root/'runs/english-sql-clarify').glob('confirm-first.jsonl'))
ref=[]
for f in sources:
 for s in f.read_text(encoding='utf-8-sig').splitlines():
    r=json.loads(s); q=r.get('reference','')
    for m in r.get('trajectory',[]):
        if m.get('role')=='assistant':ref.extend(re.findall(r'`{3}(?:sqlite|sql)\s*(.*?)`{3}',m.get('content',''),re.I|re.S))
        if m.get('role')=='assistant' and re.match(r'\s*(?:select|with)\b',m.get('content',''),re.I):ref.append(m['content'])
    if q and isinstance(q,str) and 'select' in q.lower():ref.append(q)
keys=set('select distinct from group by where count left outer join inner on is null not between in exists and or min max sum having order desc asc as union limit except like strftime date case when then else end cast integer'.split())
def skeleton(s):
    t=re.findall(r'"[^"]*"|\x27[^\x27]*\x27|\b\d+(?:\.\d+)?\b|[a-z_][\w]*|<>|<=|>=|!=|[()*.=,<+>/-]',s.lower())
    return ' '.join(x if x in keys or not x[0].isalnum() and x[0] not in ('"',"'") else 'v' if x[0].isdigit() or x.startswith("'") else 'c' for x in t)
pool=set(skeleton(s) for s in ref)
pairs=[(s['id']+'-'+str(i),c['category'],skeleton(c['sql'])) for s in data for i,c in enumerate(s['cases'],1)]
counts=Counter(cat for id,cat,sk in pairs if sk in pool)
out=dict(reference_queries=len(ref),reference_skeletons=len(pool),formal_skeletons=len({s for _,_,s in pairs}),matching_patterns_by_category=dict(counts),overlapping_ids=[id for id,_,sk in pairs if sk in pool],scope='Token-level abstraction of identifiers and literals; operators and clauses retained. This is a coarse sensitivity check, not AST equivalence or a pretraining audit.')
print({k:v for k,v in out.items() if k!='overlapping_ids'})
args.out.write_text(json.dumps(out,indent=2),encoding='utf8')
