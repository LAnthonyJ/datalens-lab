"""Bind human-readable protocol, programs, question packs and references before inference."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import argparse

def sha(p):
    with p.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("work",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();code=Path(__file__).resolve().parent
    files=[*sorted(code.glob("*.py")),code/"PROTOCOL.md",code/"pilot-business.tsv",code/"pilot-db.json"]
    references=["confirm-a.tsv","confirm-a.jsonl","confirm-db.json","confirm-b.jsonl","overlap.json","spider.jsonl","tatqa-train.json","spider-original.zip","spider-suites-official.download"]
    with a.out.open("x",encoding="utf8") as f:
        json.dump(dict(utc=datetime.now(timezone.utc).isoformat(),code={v.name:sha(v) for v in files},
                       data={n:sha(a.work/n) for n in references}),f,indent=2)
if __name__=="__main__":main()
