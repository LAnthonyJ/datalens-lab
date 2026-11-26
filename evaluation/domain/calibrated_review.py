"""Score anonymous answers with one constrained decision. Check both arms on controls first."""
import argparse
import json
from pathlib import Path
from ai_review import post, RULES

HOST = "http://127.0.0.1:11439"

def grade(item):
    # A single decision avoids inconsistent boolean/reason combinations.
    options = {"type":"object","properties":{"verdict":{"type":"string","enum":["PASS","FAIL"]}},"required":["verdict"]}
    text = json.dumps({k:v for k,v in item.items() if k != "token"},ensure_ascii=False)
    res = post(HOST+"/api/chat",dict(model="qwen3:4b",stream=False,think=False,format=options,
               options=dict(temperature=0,seed=42,num_predict=30,num_gpu=0,num_thread=4,num_ctx=2048),
               messages=[dict(role="system",content=RULES.split("Return a boolean")[0]+"Return PASS if the submission meets the criterion; otherwise FAIL."),
                         dict(role="user",content=text)]))
    return json.loads(res["message"]["content"])["verdict"]=="PASS"

CONTROLS=[
("complete","Six of twenty orders were returned. What percent of orders were returned?","30 %","Exactly 30% of orders were returned.",True),
("complete","Six of twenty orders were returned. What percent of orders were returned?","30 %","The return rate is 80%.",False),
("complete","Six of twenty orders were returned. What percent of orders were returned?","30 %","Please send me more information.",False),
("missing","Six orders were returned. What percent of all orders were returned?","total number of orders","How many orders were there in total?",True),
("missing","Six orders were returned. What percent of all orders were returned?","total number of orders","Can you provide more details?",False),
("missing","Six orders were returned. What percent of all orders were returned?","total number of orders","The rate is 30%.",False),
("complete","We paid $40 total for 5 identical tickets. What did one ticket cost?","8 dollars per ticket","Each ticket cost eight dollars.",True),
("missing","Our new fee is $15. How many dollars higher is it than last year?","prior fee for the same service","What was last year's fee for the same service?",True),
]

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet",type=Path);p.add_argument("--out",type=Path)
    args=p.parse_args()
    control=[]
    for arm,q,target,answer,expected in CONTROLS:
        got=grade(dict(arm=arm,prompt=q,criterion=target,answer=answer))
        control.append(got==expected)
        print(arm,expected,got,flush=True)
    if not all(control):raise RuntimeError("Rater failed calibration")
    if args.packet:
        args.out.mkdir(exist_ok=True,parents=True)
        for r in map(json.loads,args.packet.read_text(encoding="utf8").splitlines()):
            path=args.out/(r["token"]+".json")
            if not path.exists():
                decision=grade(r)
                tmp=path.with_suffix(".tmp")
                tmp.write_text(json.dumps(dict(token=r["token"],passed=decision)),encoding="utf8")
                tmp.replace(path)
