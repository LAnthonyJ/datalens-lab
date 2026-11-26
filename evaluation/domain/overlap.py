"""Audit exact/near question overlap and declared SQL source names before inference."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

def words(s):
    return re.findall(r'[a-z]+|\d+',s.lower())

def norm(s):
    return " ".join(words(s))

def sk(s):
    tokens=["#" if t.isdigit() else t for t in words(s)]
    return set(zip(tokens,tokens[1:],tokens[2:],tokens[3:]))

def filehash(p):
    return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()

def docs(file):
    if file.suffix==".csv":
        return list(csv.DictReader(file.open(encoding="utf-8-sig")))
    if file.suffix==".jsonl":
        return [json.loads(x) for x in file.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    return json.loads(file.read_text(encoding="utf-8-sig"))

def audit(root,work,code):
    sources=set(root.glob('train_2k*json*'))|set(root.glob('val_500*json*'))
    sources|={root/'datamind_12k.json',root/'quality/heldout.jsonl',code.parent.parent/'docs/english-confirmation.csv'}
    for directory in ('datamind-2k','cloud-pilot','english-method-comparison','english-sql-clarify','english-lr-schedule','english-lr-grid'):
        sources.update((root/'runs'/directory).glob('*.jsonl'))
    corpus=set();source_names=set();all_queries=set();entries={}
    for source in sorted(sources):
        n=0
        for r in docs(source):
            if not isinstance(r,dict):continue
            messages=r.get('messages',r.get('trajectory',[]))
            qs=[r.get('question',''),r.get('prompt','')]
            for m in messages:
                if m.get('role',m.get('from','')) in ('user','human'):
                    qs.append(m.get('content',m.get('value','')))
                elif m.get('role')=='assistant':
                    all_queries.add(str(m.get('content','')))
            if any(qs):n+=1
            corpus.update(q for q in qs if isinstance(q,str) and q.strip())
            all_queries.add(str(r.get('reference','')))
            for key in ('source','filename'):
                if isinstance(r.get(key),str):source_names.add(Path(r[key]).stem.casefold())
        entries[str(source.relative_to(root))]=dict(records_with_questions=n,sha256=filehash(source))
    for name in ('pilot-a','pilot-b'):
        corpus.update(item['prompt'] for item in docs(work/(name+'.jsonl')))
    index=defaultdict(set); ref=list(sorted(corpus));sets=[sk(q) for q in ref];exact={norm(q) for q in ref}
    for i,s in enumerate(sets):
        for gram in s:index[gram].add(i)
    schema=json.loads((work/'confirm-db.json').read_text(encoding='utf8'))
    text={s['id']+'-'+str(i):c['question'] for s in schema for i,c in enumerate(s['cases'],1)}
    names=sorted(s['source'] for s in schema if s['source'].casefold() in source_names)
    knownsql=set(norm(q) for q in all_queries)
    sql_exact=[s['id']+'-'+str(i) for s in schema for i,c in enumerate(s['cases'],1) if norm(c['sql']) in knownsql]
    matches=[]; exact_match=[]
    for name in ('confirm-a','confirm-b'):
        for r in docs(work/(name+'.jsonl')):
            q=text.get(r['id'],r['prompt'])
            if norm(q) in exact: exact_match.append(r['id'])
            s=sk(q);counts=Counter(j for g in s for j in index.get(g,()))
            if not counts: continue
            sim,j=max((n/(len(s)+len(sets[j])-n),j) for j,n in counts.items())
            matches.append(dict(id=r['id'],score=round(sim,4),prior=ref[j][:320],question=q))
    return dict(files=entries,distinct_prior_prompts=len(ref),exact_question_matches=exact_match,exact_SQL_text_matches=sql_exact,
                training_source_name_matches=names,closest=sorted(matches,key=lambda x:-x['score'])[:12],
                limitations="Four-word Jaccard, source names and normalized SQL text do not detect semantic equivalence or pretraining exposure. Simple SQL operators recur by design.")

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);p.add_argument('work',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();report=audit(a.project.resolve(),a.work.resolve(),Path(__file__).resolve().parent)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(report['distinct_prior_prompts'],report['exact_question_matches'],report['training_source_name_matches'],report['exact_SQL_text_matches'])
    print([(r['id'],r['score']) for r in report['closest'][:4]])
