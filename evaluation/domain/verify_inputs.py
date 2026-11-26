"""Check materialized packs and answer receipt counts against semantic or exact file hashes."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

def canonical(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        if path.suffix=='.jsonl': records=[json.loads(line) for line in f if line.strip()]
        elif path.suffix=='.tsv':records=list(csv.DictReader(f,delimiter='\t'))
        else:records=json.load(f)
    return hashlib.sha256(json.dumps(records,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);p.add_argument('--record',action='store_true')
    a=p.parse_args();here=Path(__file__).resolve().parent;target=here/'input-record-hashes.json'
    names=['confirm-a.tsv','confirm-a.jsonl','confirm-db.json','confirm-b.jsonl','spider.jsonl','spider-long.jsonl']
    hashes={n:canonical(a.work/n) for n in names}
    if a.record:
        with target.open('x',encoding='utf8') as f:json.dump(hashes,f,indent=2)
    elif hashes!=json.loads(target.read_text(encoding='utf8')):raise ValueError('Question or fixture content differs')
    print(f'Verified {len(hashes)} question and fixture record sets')
