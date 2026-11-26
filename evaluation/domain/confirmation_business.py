"""Build new paired analyst questions around distinct TAT-QA company-report tables.

The original benchmark questions and narrative passages are never passed to a model.
Amounts are expressed as worksheet units. Planning and audit assumptions are synthetic.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import re
import statistics

SOURCE = "2df6e722cdbaaa37efcbfb280f5c9a15be29a6ec18f618ef936fe63cc6d07c69"
CATEGORIES = ("duration", "finance", "weighted", "distribution", "rank", "change", "coverage", "rate")
DATE = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b", re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

def short(value):
    return f"{value:,.6f}".rstrip("0").rstrip(".")

def numeric(text):
    token = str(text).strip().replace(",","").replace("$","").strip()
    if not re.fullmatch(r"\d+(?:\.\d+)?", token): return None
    return float(token)

def records(table):
    header = None
    for i, row in enumerate(table[:5]):
        years = {j:int(YEAR.search(cell).group()) for j,cell in enumerate(row) if j and len(YEAR.findall(cell))==1}
        if len(set(years.values())) >= 2 and len(years)==len(set(years.values())):
            header = i, years
            break
    if header is None: return []
    i, years=header
    out=[]
    for row in table[i+1:]:
        label=" ".join(row[0].split()).strip() if row else ""
        if not 3<=len(label)<=75 or not re.search(r"[A-Za-z]",label) or not all(c.isprintable() for c in label):continue
        if re.search(r"^(?:total|balance|other|beginning|ending|net|at end|at beginning|amount|year ended|as at|as of)\s*[:1-9()]*$",label,re.I):continue
        points=sorted((year,numeric(row[j])) for j,year in years.items() if j<len(row) and numeric(row[j]) is not None and 0<numeric(row[j])<1e8)
        if len(set(v for _,v in points))>=2:
            out.append((label,points))
    return out

def construct(cat, k, label, pts, dates, rng):
    y0,a=pts[0]; y1,b=pts[-1]
    init=f'The reporting worksheet tracks "{label}". '
    unit="worksheet units"
    mode=k%6
    known=f'The {y0} entry was {short(a)} units.'
    need=f'the {y0} entry for {label} or equivalent information that determines it'
    other=f'For {y1} it shows {short(b)} units. '
    def result(q, ev, req, answer, u):
        return dict(missing_question=init+q,added_evidence=ev,required_information=req,expected=f"{answer:.10g}",unit=u)
    if cat=="duration":
        if len(dates)<2:return
        start,end=dates[0],dates[-1]
        span=(end-start).days
        if span<40:return
        a=start.isoformat(); b=end.isoformat()
        pause=rng.randint(2,19); hours=rng.randint(3,9); count=rng.randint(2,7)
        begin=f"The review opened on {a}."; finish=f"The review closed on {b}."
        n1="opening date or elapsed calendar days of the review"; n2="closing date or elapsed calendar days of the review"
        if mode==0:return result(f"The review closed on {b}. How many calendar days elapsed from opening to closing?",begin,n1,span,"days")
        if mode==1:return result(f"The review started on {a}. On {pause} days all work stopped. How many active days elapsed, counting the start date and excluding the close date?",finish,n2,span-pause,"days")
        if mode==2:return result(f"The audit team covered {hours} hours per day, from opening inclusive to closing exclusive. It closed on {b}. What was total staffed time?",begin,n1,span*hours,"hours")
        if mode==3:return result(f"The review opened on {a}. Staff worked on every elapsed day except {pause}. What percentage of elapsed days had staff, excluding the closing day?",finish,n2,100*(span-pause)/span,"%")
        if mode==4:return result(f"The tracking period ended on {b}. A full cycle lasts {count} calendar days. How many entire cycles fitted between opening and closing?",begin,n1,span//count,"cycles")
        return result(f"The review opened on {a}. We completed {count} checks spaced over the period. What was the average number of elapsed calendar days per check?",finish,n2,span/count,"days/check")
    if cat=="weighted":
        weight=rng.choice([15,20,25,30,35,40,60,65,70,75,80,85])
        # Labels describe vintage, not a ranking by size.
        facts=f"Scenario A uses the {y0} entry of {short(a)} units. Scenario B uses the {y1} entry of {short(b)} units. "
        ev=f"Scenario A has a {weight}% weight; B gets the remainder."
        req="the weights or relative likelihoods of scenarios A and B, or either share since they sum to 100%"
        mix=(a*weight+b*(100-weight))/100
        if mode==0:return result(facts+"What is the probability-weighted forecast across the two scenarios?",ev,req,mix,unit)
        if mode==1:return result(facts+"How many units does A contribute to the mixed forecast after probability weighting?",ev,req,a*weight/100,unit)
        if mode==2:return result(facts+"How much higher or lower is the combined probability-weighted estimate than using scenario B alone? Give the signed difference.",ev,req,mix-b,unit)
        if mode==3:return result(facts+"We plan for two successive periods with this same mix. What is the expected two-period total?",ev,req,2*mix,unit)
        if mode==4:
            return result(facts+f"Our current weighted plan is {short(mix)} units. What percentage weight did it assign to A? A third scenario may also be in the plan.","The plan used only A and B; their weights sum to one.","whether a third scenario contributed and its weight and value if it did, or confirmation of a two-scenario mix",weight,"%")
        return result(facts+"What percentage of the probability-weighted total comes from scenario B?",ev,req,b*(100-weight)/mix,"%")
    if cat in ("distribution","rank"):
        if len(pts)<3 or len({v for _,v in pts})!=len(pts):return
        # Rotate the withheld year. A value outside the observed range can change any requested rank/statistic.
        idx=k%len(pts); yh,h=pts[idx]
        shown=", ".join(f"{y}: {short(v)}" for y,v in pts if y!=yh)
        q=f"The series lists {shown}, all in worksheet units. The {yh} entry is blank in my copy. "
        ev=f"The {yh} entry is {short(h)} units."
        req=f"the missing {yh} value of {label} or information sufficient to locate it for this statistic"
        values=[v for _,v in pts]
        if cat=="distribution":
            functions=[("median", statistics.median,unit),("arithmetic mean",statistics.mean,unit),("range (maximum minus minimum)",lambda v:max(v)-min(v),unit),("population standard deviation",statistics.pstdev,unit),("mean absolute deviation from the arithmetic mean",lambda v:statistics.mean(abs(x-statistics.mean(v)) for x in v),unit),("root mean square",lambda v:math.sqrt(statistics.mean(x*x for x in v)),unit)]
            name,fn,u=functions[mode]
            return result(q+f"What is the {name} across all {len(values)} annual entries?",ev,req,fn(values),u)
        if mode in (0,1):
            high=mode==0
            return result(q+f"What rank does {yh} have, using one for the {'largest' if high else 'smallest'} amount?",ev,req,sorted(values,reverse=high).index(h)+1,"rank")
        if mode==2:return result(q+"What year ranks second when sorted from largest to smallest?",ev,req,sorted(pts,key=lambda p:-p[1])[1][0],"year")
        if mode==3:return result(q+"By how much does the largest annual entry exceed the runner-up?",ev,req,sorted(values)[-1]-sorted(values)[-2],unit)
        if mode==4:return result(q+"How many other reported years rank above the blank year by amount?",ev,req,sum(x>h for x in values),"years")
        return result(q+"What is the ratio of the largest annual entry to the second-largest?",ev,req,sorted(values)[-1]/sorted(values)[-2],"times")
    if cat=="change":
        q0=f"{other}How many units did the line change from {y0} to {y1}? Give a signed amount."
        if mode==0:return result(q0,known,need,b-a,unit)
        if mode==1:return result(other+f"What was the percentage change since {y0}, using the earlier value as the base?",known,need,100*(b-a)/a,"%")
        if mode==2:return result(other+f"What was the average absolute-unit change per year from {y0} to {y1}? Retain the sign.",known,need,(b-a)/(y1-y0),"units/year")
        if mode==3:return result(other+f"Index {y0} at 100. What is the index in {y1}?",known,need,100*b/a,"index points")
        if mode==4:return result(other+f"What constant compounded annual growth rate connects {y0} and {y1}?",known,need,100*((b/a)**(1/(y1-y0))-1),"%")
        return result(other+f"If we repeat the total absolute-unit change since {y0} once more, what is the projected amount?",known,need,b+b-a,unit)
    if cat=="finance":
        if not re.search(r"cost|expens|profit|revenue|income|interest paid|rent|earnings|sales|fees",label,re.I):return
        h=rng.choice([5,10,15,20,25]); fixed=round(a*.13,2)
        if mode==0:return result(other+f"How much should we set aside for a reserve equal to {h}% of the {y0} amount?",known,need,a*h/100,unit)
        if mode==1:return result(other+f"We budgeted {h}% above the {y0} amount for {y1}. What is actual minus budget?",known,need,b-a*(1+h/100),unit)
        if mode==2:return result(other+f"An analyst applies a {h}% haircut to this line in both reported years. What is the adjusted two-year total for {y0} and {y1}?",known,need,(a+b)*(1-h/100),unit)
        if mode==3:return result(other+f"Our contract fee is {h}% of the {y0} amount plus a flat {short(fixed)} units. What fee is due?",known,need,a*h/100+fixed,unit)
        if mode==4:return result(other+f"The {y1} provision must equal the larger of its reported amount and the {y0} benchmark. At what amount should we book it?",known,need,max(a,b),unit)
        return result(other+f"How much of a two-period budget equal to three times the {y0} figure remains after charging both reported amounts?",known,need,2*a-b,unit)
    if cat=="coverage":
        h=rng.choice([12,18,22,28,32,37,42,48,53,57]); add=rng.choice([4,6,8,10])
        tested=round(b*h/100,4); extra=round(b*add/100,4)
        if tested<=0 or extra==0:return
        req=f"the full in-scope {y1} balance for {label} or an equivalent denominator"
        ev=f"The full in-scope {y1} balance was {short(b)} units."
        q=f"In {y1} we traced {short(tested)} units of this balance to source documents. "
        if mode==0:return result(q+"What percentage of the full balance did we trace?",ev,req,100*tested/b,"%")
        if mode==1:return result(q+"How many units still have no trace?",ev,req,b-tested,unit)
        if mode==2:return result(q+f"We then traced another disjoint block of {short(extra)} units. What percentage remains untraced?",ev,req,100*(b-tested-extra)/b,"%")
        if mode==3:return result(q+f"A second check covered {short(tested)} units and overlapped the first by {short(extra)}. How many percentage points of coverage did the second check add?",ev,req,100*(tested-extra)/b,"percentage points")
        if mode==4:return result(q+"The target is to trace 90% by value. How many more units must be traced?",ev,req,.9*b-tested,unit)
        return result(q+f"The {short(extra)} units traced by a junior reviewer are now invalid. What percentage of the full balance still has valid evidence?",ev,req,100*(tested-extra)/b,"%")
    if cat=="rate":
        if not re.search(r"sales|revenue|income|cost|benefit|tax|cash|assets|expenses|purchases|debt|liabilit|stock|interest|receivable|units|production",label,re.I):return
        n=rng.randint(3,12); h=rng.choice([5,10,15,20,25,30])
        if mode==0:return result(other+f"Across {y0} and {y1}, what percent of their combined positive entries came from {y1}?",known,need,100*b/(a+b),"%")
        if mode==1:return result(other+f"How many units of the {y0} entry were there per unit in {y1}?",known,need,a/b,"units per unit")
        if mode==2:return result(other+f"Assume {h}% of the {y0} figure was converted to cash. What percent of {y1}'s reported entry would that cash cover?",known,need,a*h/b,"%")
        if mode==3:return result(other+f"We spread the {y0} entry equally over {n} batches. How many units per batch did that year average?",known,need,a/n,"units/batch")
        if mode==4:return result(other+f"The {y0} operation handled {n} cases per worksheet unit. How many cases would there be per {y1} worksheet unit?",known,need,n*a/b,"cases/unit")
        return result(other+f"How much of the combined figures for {y0} and {y1} passes a {h}% conversion step? Give the converted quantity.",known,need,(a+b)*h/100,unit)

def build(source):
    data=source.read_bytes()
    if hashlib.sha256(data).hexdigest()!=SOURCE:raise ValueError("Unexpected source digest")
    candidates=[]
    for doc in json.loads(data):
        table=doc["table"]["table"]; uid=doc["table"]["uid"]
        rec=records(table)
        dates=set()
        for line in table:
            for cell in line:
                for match in DATE.findall(cell):
                    try: dates.add(datetime.strptime(match.replace(",",""),"%B %d %Y").date())
                    except ValueError:pass
        if rec:candidates.append((uid,rec,sorted(dates)))
    rows=[]; seen=set(); labels=set();seen_text=set()
    for cat in CATEGORIES:
        ordered=sorted(candidates,key=lambda x:hashlib.sha256((cat+x[0]).encode()).hexdigest())
        n=0
        for uid,rec,ds in ordered:
            if uid in seen:continue
            rng=random.Random(cat+uid)
            rng.shuffle(rec)
            for label,pts in rec:
                canon=re.sub(r"\W+"," ",label.lower()).strip()
                if (cat,canon) in labels:continue
                case=construct(cat,n,label,pts,ds,rng)
                if case and case['missing_question'] not in seen_text:break
            else:continue
            seen.add(uid);labels.add((cat,canon));seen_text.add(case['missing_question'])
            rows.append(dict(category=cat,source_table=uid,form=n%6,**case))
            n+=1
            if n==50:break
        if n!=50:raise ValueError(f"{cat}: {n}")
    assert len(seen)==len(rows)==400
    return rows

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source",type=Path);p.add_argument("pack",type=Path);p.add_argument("inputs",type=Path)
    args=p.parse_args();rows=build(args.source)
    with args.pack.open("x",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys(),delimiter="\t");w.writeheader();w.writerows(rows)
    with args.inputs.open("x",encoding="utf8") as f:
        for i,row in enumerate(rows,1):
            for arm in ("missing","complete"):
                prompt=row["missing_question"]+(" "+row["added_evidence"] if arm=="complete" else "")
                print(json.dumps(dict(id=f"a-formal-{i:03}-{arm}",prompt=prompt)),file=f)
