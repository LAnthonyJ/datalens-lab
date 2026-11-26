"""Mask model identities before scoring. Reuse one grade for byte-identical answers."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
import secrets


def blind(pack, models, out):
    book=list(csv.DictReader(pack.open(encoding="utf-8-sig"),delimiter="\t"))
    answers={}
    for label, folder in models:
        for path in sorted(Path(folder).glob("*.json")):
            if path.name=="manifest.json":continue
            r=json.loads(path.read_text(encoding="utf8"))
            group,arm=r["id"].rsplit("-",1)
            i=int(group.rsplit("-",1)[-1])-1
            q=book[i]
            prompt=q["missing_question"]+(" "+q["added_evidence"] if arm=="complete" else "")
            target=q["required_information"] if arm=="missing" else q["expected"]+" "+q["unit"]
            k=(r["id"],r["answer"])
            if k not in answers:
                answers[k]=dict(prompt=prompt,arm=arm,criterion=target,answer=r["answer"],models=[])
            answers[k]["models"].append(label)
    if len(answers)==0:raise ValueError("Empty packet")
    order=list(answers)
    random.SystemRandom().shuffle(order)
    out.mkdir(parents=True,exist_ok=False)
    with (out/"packet.jsonl").open("x",encoding="utf8") as f,(out/"key.jsonl").open("x",encoding="utf8") as key:
        for k in order:
            v=answers[k].copy()
            labels=v.pop("models")
            token=secrets.token_hex(6)
            print(json.dumps(dict(token=token,**v)),file=f)
            print(json.dumps(dict(token=token,id=k[0],models=labels)),file=key)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("pack",type=Path)
    p.add_argument("out",type=Path)
    p.add_argument("--model",nargs=2,action="append",required=True)
    args=p.parse_args()
    blind(args.pack,args.model,args.out)
