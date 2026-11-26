"""Derive paired analytical queries from diverse public Spider training-side schemas.

Keep original table/column names and types for the selected fields. Only synthetic rows
are inserted. Cases are new; dev databases and Spider's own questions are excluded.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

def qi(s):
    return '"' + s.replace('"','""') + '"'

def build(source, count):
    with zipfile.ZipFile(source) as archive:
        all_schemas=json.loads(archive.read("spider_data/tables.json"))
        train_ids={r["db_id"] for r in json.loads(archive.read("spider_data/train_spider.json"))}
        dev_ids={r["db_id"] for r in json.loads(archive.read("spider_data/dev.json"))}
    def priority(s):
        return hashlib.sha256(("datalens-confirmation-v1:"+s["db_id"]).encode()).hexdigest()
    pack=[]
    for s in sorted(all_schemas,key=priority):
        if s["db_id"] not in train_ids-dev_ids:continue
        names=s["table_names_original"]
        cols=s["column_names_original"]
        types=s["column_types"]
        dates=[j for j,(_,name) in enumerate(cols) if (re.search(r'date|year|birthday',name,re.I) and not re.search(r'candidate|years_|years$|year_working|yearsplayed|dates_active|time_in_year',name,re.I))]
        if not dates:continue
        links=[(a,b) for a,b in s["foreign_keys"] if a!=b and cols[a][0]!=cols[b][0] and b in s["primary_keys"]]
        if not links:continue
        # Prefer a temporal attribute on one side of the relationship.
        links.sort(key=lambda ab:(not any(cols[j][0] in {cols[k][0] for k in ab} for j in dates),ab))
        a,b=links[0]
        c,p=cols[a][0],cols[b][0]
        if not all(re.fullmatch(r"[A-Za-z_][\w]*",n) for n in names):continue
        date_col=next((j for j in dates if cols[j][0] in (p,c) and j not in (a,b)),None)
        if date_col is None:date_col=next((j for j in dates if j not in (a,b)),None)
        if date_col is None:continue
        ci=next((j for j,(t,n) in enumerate(cols) if t==c and j!=a and j!=date_col and j not in s["primary_keys"]),None)
        pi=next((j for j,(t,n) in enumerate(cols) if t==p and j!=b and j!=date_col),None)
        if ci is None or pi is None:continue
        child,parent=names[c],names[p]
        date_table=names[cols[date_col][0]]
        tables=[t for t in range(len(names)) if t in {p,c,cols[date_col][0]}]
        # Retain all columns and the documented join key in the prompt.
        columns={t:[j for j,(tid,_) in enumerate(cols) if tid==t] for t in tables}
        numeric=lambda j: types[j]=="number"
        value=lambda j,i: i if numeric(j) else f"v{i}"
        def key(i):return str(i) if not numeric(b) or not numeric(a) else i
        def date(i):
            if re.search('year',cols[date_col][1],re.I):return [2023,2024,2024,2025,2022,2024,2025,2024,2024][i]
            return ["2023-12-31","2024-01-01","2024-12-31","2025-01-01","2022-11-02","2024-02-29","2025-06-01","2024-06-08","2024-01-01"][i]
        ddl=[]
        base={}; extra=[{},{}]
        for t in tables:
            field=columns[t]
            decl=[]
            for j in field:
                typ="INTEGER" if numeric(j) else "TEXT"
                if j in (a,b):typ="INTEGER" if isinstance(key(1),int) else "TEXT"
                if j==date_col:typ="INTEGER" if isinstance(date(0),int) else "TEXT"
                decl.append(qi(cols[j][1])+" "+typ)
            ddl.append(qi(names[t])+"("+", ".join(decl)+")")
            data=[]
            for i in range(9):
                row={j:value(j,i+1) for j in field}
                if t==c:
                    foreign=[1,1,2,None,2,4,1,99,5][i]
                    row[a]=key(foreign) if foreign is not None else None
                    n=[1,2,2,1,None,3,1,None,2][i]
                    row[ci]=value(ci,n) if n is not None else None
                if t==p:
                    row[b]=key(i+1)
                    row[pi]=value(pi,[3,1,3,2,1,6,3,3,1][i])
                if date_col in field: row[date_col]=date(i)
                data.append([row[j] for j in field])
            base[names[t]]=data[:5]
            extra[0][names[t]]=data[5:7]
            extra[1][names[t]]=data[7:]
        idx=len(pack)
        n,a1,b1,v,w,tcol=(qi(x) for x in (child,cols[a][1],cols[b][1],cols[ci][1],cols[pi][1],cols[date_col][1]))
        par=qi(parent)
        P=base[parent]; C=base[child]; D=base[date_table]
        field=lambda row,table,col:row[columns[table].index(col)]
        ca=lambda row:field(row,c,a)
        cv=lambda row:field(row,c,ci)
        pb=lambda row:field(row,p,b)
        pv=lambda row:field(row,p,pi)
        fks=[ca(r) for r in C]
        vals=[cv(r) for r in C]
        names2=(cols[a][1],cols[b][1],cols[ci][1],cols[pi][1])
        fk,pk,attr,label=names2
        lit=value(ci,1)
        literal=str(lit) if isinstance(lit,int) else "'"+lit+"'"
        cases=[]
        def add(category,q,sql,expected):
            cases.append(dict(category=category,question=q,sql=sql,expected=[list(row) for row in expected]))
        mode=idx%3
        target=lambda x: (x==lit if mode==0 else x is None if mode==1 else x is not None and x!=lit)
        pred=f"{v}={literal}" if mode==0 else f"{v} IS NULL" if mode==1 else f"{v}<>{literal}"
        request=(f"equals {literal}" if mode==0 else "is missing" if mode==1 else f"is known and differs from {literal}")
        add("filter",f"In {child}, return {fk} for each row whose {attr} {request}. Preserve duplicate rows.",f"SELECT {a1} FROM {n} WHERE {pred}",[(ca(r),) for r in C if target(cv(r))])
        col,jj=(a1,fks) if idx%2 else (v,vals)
        colname=fk if idx%2 else attr
        subset=idx%4==1
        qualifying=[x for x,y in zip(jj,vals) if not subset or y==lit]
        add("distinct",f"How many different known {colname} values are in {child}"+(f" among rows with {attr} equal to {literal}" if subset else "")+"?",f"SELECT COUNT(DISTINCT {col}) FROM {n}"+(f" WHERE {v}={literal}" if subset else ""),[(len(set(qualifying)-{None}),)])
        groups=defaultdict(list)
        for row in C:groups[ca(row)].append(cv(row))
        agg=["COUNT","MIN","MAX"][idx%3]
        def ag(vs):
            vs=[x for x in vs if x is not None]
            if agg=="COUNT":return len(vs)
            return (min(vs) if agg=="MIN" else max(vs)) if vs else None
        limit=idx%5==1
        add("aggregate",f"For each {fk} in {child}, give {fk} and the {dict(COUNT='count',MIN='minimum',MAX='maximum')[agg]} of known {attr} values. "+("Only include groups with at least two rows." if limit else "Keep the missing-key group."),f"SELECT {a1},{agg}({v}) FROM {n} GROUP BY {a1}"+(" HAVING COUNT(*)>=2" if limit else ""),[(k,ag(vs)) for k,vs in groups.items() if not limit or len(vs)>=2])
        anti=idx%3==2
        if anti:
            add("join",f"Which {parent}.{pk} values do not have a matching row in {child}? Ignore unassigned {child} rows.",f"SELECT p.{b1} FROM {par} p WHERE NOT EXISTS (SELECT 1 FROM {n} c WHERE c.{a1}=p.{b1})",[(pb(r),) for r in P if pb(r) not in fks])
        else:
            add("join",f"List {parent}.{label} and {child}.{attr} for every matching {child} row"+(f" where {child}.{attr} is known." if idx%2 else "."),f"SELECT p.{w},c.{v} FROM {n} c JOIN {par} p ON p.{b1}=c.{a1}"+(f" WHERE c.{v} IS NOT NULL" if idx%2 else ""),[(pv(pr),cv(cr)) for cr in C for pr in P if ca(cr)==pb(pr) and (not idx%2 or cv(cr) is not None)])
        year=isinstance(date(0),int)
        lo,hi=(2024,2025) if year else ("2024-01-01","2025-01-01")
        dat=[field(r,cols[date_col][0],date_col) for r in D]
        inside=[x for x in dat if lo<=x<hi]
        count_dates=idx%2==0
        add("date",f"In {date_table}, "+("how many records" if count_dates else f"list the {cols[date_col][1]} values, retaining duplicates, for records that")+f" fall in calendar year 2024 according to {cols[date_col][1]}?",f"SELECT "+("COUNT(*)" if count_dates else tcol)+f" FROM {qi(date_table)} WHERE {tcol}>={repr(lo)} AND {tcol}<{repr(hi)}",[(len(inside),)] if count_dates else [(x,) for x in inside])
        cond=idx%3
        hint=["all matching records",f"matching records whose {attr} is known",f"matching records whose {attr} equals {literal}"][cond]
        suffix=["",f" AND c.{v} IS NOT NULL",f" AND c.{v}={literal}"][cond]
        add("zero",f"For every {parent}.{pk}, count {hint} in {child}. Return {pk} and the count, including {parent} rows with zero.",f"SELECT p.{b1},COUNT(c.{a1}) FROM {par} p LEFT JOIN {n} c ON c.{a1}=p.{b1}{suffix} GROUP BY p.{b1}",[(pb(pr),sum(ca(cr)==pb(pr) and (cond==0 or cond==1 and cv(cr) is not None or cond==2 and cv(cr)==lit) for cr in C)) for pr in P])
        for case in cases:case["question"]+=f" The declared relationship is {child}.{fk} to {parent}.{pk}."
        pack.append(dict(id="db-"+s["db_id"],source=s["db_id"],ddl=ddl,base=base,extra=extra,cases=cases))
        if len(pack)==count: break
    if len(pack)!=count:raise ValueError(f"Only {len(pack)} candidate schemas")
    return pack


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("archive",type=Path)
    p.add_argument("out",type=Path)
    p.add_argument("--count",type=int,default=80)
    args=p.parse_args()
    with args.out.open("x",encoding="utf8") as f:
        json.dump(build(args.archive,args.count),f,ensure_ascii=False)

