"""Build and grade the SQL pilot or an identically formatted frozen scenario pack."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import time

HERE = Path(__file__).resolve().parent


def fixture(schema, extra):
    db=sqlite3.connect(":memory:")
    for definition in schema["ddl"]:
        db.execute("CREATE TABLE "+definition)
    for rows in (schema["base"], extra):
        for table, values in rows.items():
            db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' for _ in values[0])})",values)
    db.commit()
    db.execute("PRAGMA query_only=ON")
    return db


def execute(db, sql):
    deadline=time.monotonic()+2
    db.set_progress_handler(lambda: time.monotonic()>deadline,1000)
    allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_RECURSIVE}
    functions={"abs","avg","sum","total","count","round","min","max","coalesce","ifnull",
               "nullif","iif","strftime","date","substr","lower","upper","julianday","cast",
               "length","trim","dense_rank","row_number","rank","instr","like","glob"}
    db.set_authorizer(lambda op,a,b,*_: sqlite3.SQLITE_OK if op in allowed or
                      (op==sqlite3.SQLITE_FUNCTION and (b or "").lower() in functions) else sqlite3.SQLITE_DENY)
    try:
        rows=db.execute(sql).fetchmany(1001)
        if len(rows)>1000: raise ValueError("Too many result rows")
        return Counter(tuple(round(x,7) if isinstance(x,float) else x for x in row) for row in rows)
    finally:
        db.set_authorizer(None)
        db.set_progress_handler(None,0)


def statement(answer):
    fenced=re.findall(r"`{3}(?:sql|sqlite)?\s*\n(.*?)\n?\s*`{3}",answer,flags=re.I|re.S)
    if len(fenced)==1: return fenced[0].strip()
    if fenced: return ""
    return answer.strip()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pack",type=Path,default=HERE/"pilot-db.json")
    p.add_argument("--answers",type=Path)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    records=[]
    for s in json.loads(args.pack.read_text(encoding="utf-8-sig")):
        if len(s["extra"])<2: raise ValueError("At least three fixtures required")
        databases=[fixture(s, extra) for extra in [{},*s["extra"]]]
        try:
            for i,c in enumerate(s["cases"],1):
                id_=s["id"]+"-"+str(i)
                gold=[execute(db,c["sql"]) for db in databases]
                assert gold[0]==Counter(tuple(row) for row in c["expected"]),id_
                if args.answers is None:
                    row=dict(id=id_,prompt="Write a single SQLite SELECT query. Schema: "+"; ".join(s["ddl"])+". "+c["question"])
                else:
                    answer=json.loads((args.answers/(id_+".json")).read_text(encoding="utf8"))
                    try:
                        passed=all(execute(db,statement(answer["answer"]))==g for db,g in zip(databases,gold))
                    except (ValueError,sqlite3.Error):
                        passed=False
                    row=dict(id=id_,database=s["id"],category=c["category"],passed=passed,answer=answer["answer"])
                records.append(row)
        finally:
            for db in databases: db.close()
    with args.out.open("x",encoding="utf8") as f:
        for row in records: print(json.dumps(row),file=f)


if __name__=="__main__":
    main()
