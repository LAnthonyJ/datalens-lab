"""Prepare all Spider development prompts, using only the question and public schema."""
import argparse
import json
from pathlib import Path
import pyarrow.parquet as pq

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("dev", "tables", "out"):
        p.add_argument("--"+name, type=Path, required=True)
    args=p.parse_args()
    tables={s["db_id"]:s for s in json.loads(args.tables.read_text(encoding="utf8"))}
    questions=pq.read_table(args.dev).to_pylist()
    assert len(questions)==1034 and len(set(q["db_id"] for q in questions))==20
    with args.out.open("x", encoding="utf8") as out:
        for i,q in enumerate(questions):
            s=tables[q["db_id"]]
            names=s["table_names_original"]
            cols=s["column_names_original"]
            parts=[n+"("+", ".join(c for t,c in cols if t==j)+")" for j,n in enumerate(names)]
            def cname(index):
                t,c=cols[index]
                return names[t]+"."+c
            links=[cname(a)+"="+cname(b) for a,b in s["foreign_keys"]]
            prompt="Write a single SQLite SELECT query. Schema: "+"; ".join(parts)+". Foreign keys: "+", ".join(links)+". "+q["question"]
            print(json.dumps(dict(id=f"spider-{i:04}",prompt=prompt)),file=out)
if __name__=="__main__": main()
