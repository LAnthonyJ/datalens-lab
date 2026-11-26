"""Paired, two-sided percentile bootstrap. One equally weighted unit per scenario/database."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
from statistics import NormalDist, stdev
import math


def paired(rows):
    groups=defaultdict(list)
    for r in rows:
        groups[r['cluster']].append(int(r['lora'])-int(r['base']))
    sizes={len(v) for v in groups.values()}
    if len(sizes)!=1:raise ValueError("Unequal cluster sizes need a question-weighted estimator")
    effects=np.array([np.mean(v) for _,v in sorted(groups.items())])
    rng=np.random.default_rng(20261126)
    reps=rng.choice(effects,size=(20000,len(effects)),replace=True).mean(axis=1)
    lower,upper=np.quantile(reps,[.0125,.9875])
    delta=float(np.mean(effects))
    discord=[r for r in rows if r['base']!=r['lora']]
    return dict(items=len(rows),clusters=len(groups),base=sum(r['base'] for r in rows),
                lora=sum(r['lora'] for r in rows),delta_pp=100*delta,ci97_5_pp=[100*lower,100*upper],
                improved=sum(r['lora'] for r in discord),regressed=sum(r['base'] for r in discord),
                meets_threshold=bool(delta>=.10-1e-12 and lower>0),cluster_sd=stdev(effects))

def power(sd,n):
    # For the superiority test at true delta .10, not the additional observed-size criterion.
    z=NormalDist().inv_cdf(.9875); mu=.10*math.sqrt(n)/sd if sd else float("inf")
    return NormalDist().cdf(mu-z)+NormalDist().cdf(-mu-z)

def load_file(path):
    return list(map(json.loads,Path(path).read_text(encoding='utf-8-sig').splitlines()))

def business_rows(key,grades):
    m={r['token']:r['passed'] for r in grades}
    if len(m)!=len(grades) or set(m)!={r['token'] for r in key}:raise ValueError('Missing or duplicate verdicts')
    grouped=defaultdict(dict)
    for r in key:
        case,arm=r['id'].rsplit('-',1)
        for label in r['models']:
            model='base' if label=='baseline' else label
            if (model,arm) in grouped[case]:raise ValueError('Repeated answer')
            grouped[case][model,arm]=m[r['token']]
    return [dict(id=k,cluster=k,**{model:all([v[model,'missing'],v[model,'complete']]) for model in ('base','lora')}) for k,v in sorted(grouped.items())]

def sql_rows(base,lora):
    b={r['id']:r for r in base};l={r['id']:r for r in lora}
    if b.keys()!=l.keys() or len(b)!=len(base) or len(l)!=len(lora):raise ValueError('Unpaired inputs')
    return [dict(id=k,cluster=b[k]['database'],base=b[k]['passed'],lora=l[k]['passed']) for k in sorted(b)]

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('type',choices=['business','sql']);p.add_argument('left');p.add_argument('right');p.add_argument('--expected',type=int,required=True)
    a=p.parse_args();left,right=map(load_file,(a.left,a.right))
    rows=business_rows(left,right) if a.type=='business' else sql_rows(left,right)
    if len(rows)!=a.expected:raise ValueError('Incomplete denominator')
    print(json.dumps(paired(rows),indent=2))

