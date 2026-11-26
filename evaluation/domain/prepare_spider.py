"""Extract the Spider development fixture directories and check supplied input hashes."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("work",type=Path);a=p.parse_args()
    w=a.work;freeze=json.loads((Path(__file__).with_name('freeze.json')).read_text(encoding='utf-8-sig'))
    for n in ("spider-original.zip","spider-suites-official.download","tatqa-train.json"):
        with (w/n).open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=freeze['data'][n]:raise ValueError(n)
    with zipfile.ZipFile(w/'spider-original.zip') as src:
        dev=json.loads(src.read('spider_data/dev.json')); tables=json.loads(src.read('spider_data/tables.json'))
    (w/'tables.json').write_text(json.dumps(tables),encoding='utf8')
    dbs={q['db_id'] for q in dev};counts={n:0 for n in dbs}
    with zipfile.ZipFile(w/'spider-suites-official.download') as suite:
        for name in suite.namelist():
            parts=PurePosixPath(name).parts
            if len(parts)!=3 or parts[0]!='database' or parts[1] not in dbs or not parts[2].endswith('.sqlite'):continue
            dst=w/'official-suite'/parts[1]/parts[2];dst.parent.mkdir(parents=True,exist_ok=True)
            if dst.is_file() and dst.stat().st_size!=suite.getinfo(name).file_size:raise ValueError(dst)
            if not dst.exists():
                with suite.open(name) as src,dst.open('xb') as f:shutil.copyfileobj(src,f)
            counts[parts[1]]+=1
    if len(counts)!=20 or sum(counts.values())!=695:raise ValueError(counts)
    import pyarrow as pa
    import pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist([{k:q[k] for k in ('db_id','question','query')} for q in dev]),w/'dev.parquet')
if __name__=='__main__':main()
