"""Replace known training-side query structures before the first formal SQL generation."""
from collections import Counter
import argparse
import json
from pathlib import Path
import re
from sql_cases import fixture, execute


def amend(pack, flagged):
    for s in pack:
        db=fixture(s,{})
        try:
            for i,c in enumerate(s['cases'],1):
                key=s['id']+'-'+str(i)
                if key not in flagged:continue
                q=c['question'].split(' The declared relationship is ')[0]
                rel=c['question'][len(q):]
                old=c['sql']; values=c['expected']; cat=c['category']
                if cat=='filter':
                    m=re.fullmatch(r'SELECT ("[^"]+") FROM (.*)',old)
                    col,tail=m.groups()
                    c['question']=q.replace('Preserve duplicate rows.','In the report return each resulting key once and its number of occurrences, including the missing-key group.')
                    c['sql']=f'SELECT {col}, COUNT(*) FROM {tail} GROUP BY {col}'
                    output=list(Counter(r[0] for r in values).items())
                elif cat=='distinct':
                    m=re.fullmatch(r'SELECT COUNT\(DISTINCT ("[^"]+")\) FROM ("[^"]+")',old)
                    col,table=m.groups()
                    names=[r[1] for r in db.execute('PRAGMA table_info('+table+')')]
                    raw=[r[names.index(col.strip('"'))] for r in s['base'][table.strip('"')]]
                    known=[v for v in raw if v is not None]
                    c['question']=q+' Return two columns: the distinct count and the number of extra known rows beyond the first occurrence of each known value.'
                    c['sql']=f'SELECT COUNT(DISTINCT {col}), COUNT({col})-COUNT(DISTINCT {col}) FROM {table}'
                    output=[(len(set(known)),len(known)-len(set(known)))]
                elif cat=='zero':
                    count=re.search(r'COUNT\(c\."[^"]+"\)',old).group()
                    c['question']=q+' For the capacity report keep only groups below two matches. Add a third column giving the number of additional matches needed to reach two.'
                    c['sql']=old.replace(count+' FROM',count+', 2-'+count+' FROM')+f' HAVING {count}<2'
                    output=[(k,n,2-n) for k,n in values if n<2]
                elif cat=='date':
                    col=re.search(r'SELECT ("[^"]+") FROM',old)[1]
                    tail=old.split(' FROM ',1)[1]
                    c['question']=q.split(', list the ')[0]+f', what was the latest eligible {col.strip(chr(34))} value in calendar year 2024, and how many rows had that value? Return one row only if an eligible value exists.'
                    c['sql']=f'SELECT {col},COUNT(*) FROM {tail} GROUP BY {col} ORDER BY {col} DESC LIMIT 1'
                    data=[r[0] for r in values]
                    output=[(max(data),data.count(max(data)))] if data else []
                elif cat=='join':
                    col=re.search(r'SELECT (p\."[^"]+") FROM',old)[1]
                    c['question']=q+' Summarize those unmatched keys in a single row. Return the number of keys and the smallest unmatched key, or NULL for the smallest when none exist.'
                    c['sql']=old.replace('SELECT '+col+' FROM',f'SELECT COUNT(*),MIN({col}) FROM',1)
                    data=[r[0] for r in values];output=[(len(data),min(data) if data else None)]
                else:raise ValueError(cat)
                c['question']+=rel
                c['expected']=[list(r) for r in output]
                assert execute(db,c['sql'])==Counter(map(tuple,c['expected'])),key
        finally:db.close()
    return pack

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('original',type=Path);p.add_argument('audit',type=Path);p.add_argument('out',type=Path)
    a=p.parse_args();pack=json.loads(a.original.read_text(encoding='utf8'));flagged=set(json.loads(a.audit.read_text(encoding='utf8'))['overlapping_ids'])
    result=amend(pack,flagged)
    with a.out.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False)
