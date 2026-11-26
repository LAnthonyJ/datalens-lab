"""Select the length-budget diagnostic by hashed ID, five questions per Spider dev DB."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import zipfile

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);a=p.parse_args();w=a.work
    with zipfile.ZipFile(w/'spider-original.zip') as z:dev=json.loads(z.read('spider_data/dev.json'))
    source=list(map(json.loads,(w/'spider.jsonl').read_text(encoding='utf8').splitlines()))
    groups=defaultdict(list)
    for q,item in zip(dev,source,strict=True):groups[q['db_id']].append(item)
    order=lambda v:hashlib.sha256(('datalens-length-512-v1:'+v['id']).encode()).hexdigest()
    sample=sorted((v for group in groups.values() for v in sorted(group,key=order)[:5]),key=lambda v:v['id'])
    selected={v['id'] for v in sample}
    remainder=sorted((v for v in source if v['id'] not in selected),key=order)
    sample=sorted(sample+remainder[:100-len(sample)],key=lambda v:v['id'])
    assert len(sample)==100
    with (w/'spider-long.jsonl').open('x',encoding='utf8') as f:
        for v in sample:print(json.dumps(v),file=f)

