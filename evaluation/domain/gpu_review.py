"""Optional GPU replication of the same masked verdict using the same local model."""
import argparse
import os
import re
import json
from pathlib import Path
import time
from urllib.error import HTTPError,URLError
from ai_review import post, RULES
from calibrated_review import CONTROLS

PORT=int(os.environ.get("DATALENS_REVIEW_PORT","11440"))
URL=f"http://127.0.0.1:{PORT}/api/chat"
def ask(system,item,labels,field):
    schema={"type":"object","properties":{field:{"type":"string","enum":labels}},"required":[field]}
    payload=dict(model="qwen3:4b",stream=False,think=False,format=schema,
        options=dict(temperature=0,seed=42,num_predict=30,num_gpu=99,num_thread=4,num_ctx=2048),
        messages=[dict(role="system",content=system),dict(role="user",content=json.dumps({k:v for k,v in item.items() if k!='token'},ensure_ascii=False))])
    for n in range(5):
        try:
            return json.loads(post(URL,payload)["message"]["content"])[field]
        except (HTTPError,URLError,KeyError,ValueError):
            if n==4:raise
            time.sleep(2**n)

def verdict(item):
    return ask(RULES.split("Return a boolean")[0]+"Return PASS if the submission meets the criterion; otherwise FAIL.",item,["PASS","FAIL"],"verdict")=="PASS"

def issue(item):
    answer=item['answer'].strip()
    if item["arm"]=="missing":
        if re.match(r'^(?:for example[, :]*)?(?:if|suppose|for illustration)\b',answer,re.I) and '?' in answer and len(answer)<240:
            return False
        if not re.search(r'\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|half|double|twice|all|none)\b',answer,re.I):
            return False
        if len(answer)<180 and re.match(r"^(?:what|which|when|how|can you|could you|would you|please)\b",answer,re.I) and not re.search(r'[.=]\s*(?:the result|therefore|so the|that means)',answer,re.I):
            return False
        if len(answer)<180 and re.search(r'\d',answer) and not re.search(r'\?|\b(?:if|suppose|hypothetical|provided|would|could|unknown|need|please|without|missing|cannot|incomplete|unavailable)\b',answer,re.I):
            if re.search(r'\b(?:rate|equals?|was|were|is|are|amounted|totaled|percent|rank|position|elapsed)\b|[=%]',answer,re.I):
                return True
    if item["arm"]=="complete":
        direct = re.match(r'^(?:(?:could|can|would) you\s+|please\s+)(?:share|tell|give|send|provide|supply|clarify|confirm)\b',answer,re.I)
        if direct and len(answer)<160 and not re.search(r'(?:otherwise|already|optional|if you like)',answer,re.I):
            return True
        if not re.search(r'\?|\b(?:please|tell|provide|share|clarify|require|need|missing|unknown|unable|insufficient|without|cannot|supply|confirm|unclear|not|lack)\w*\b',answer,re.I):
            return False
    if item["arm"]=="missing":
        rule="Does this submitted answer present a numerical result for the requested metric without sufficient evidence? An invented unconditional value, including a made-up intermediate value used to answer, qualifies. Do not flag copied givens, an explicitly hypothetical example, an unevaluated formula, or merely the absence of the correct question. Return YES if it asserts an unsupported numerical result and NO otherwise."
    else:
        rule="The supplied question already contains all information needed for the target. Does this answer ask the user for additional data as a condition of solving it? Count explicit solicitations or a statement that missing inputs prevent a result. Do not count rhetorical headings, restating the user's question, worked examples, or an optional offer following a correct answer. Return YES if it unnecessarily requests data, NO otherwise."
    examples = ("A response like 'it is 20%' when the denominator is withheld is YES. 'What is the denominator?' or 'if there were 100, the rate would be 20%' is NO."
                if item["arm"]=="missing" else
                "A response like 'Please send the old balance' when the old balance is in the question is YES. A wrong calculation with no request, or 'here is the calculation', is NO.")
    return ask(rule+" "+examples,{"prompt":item["prompt"],"submitted_answer":answer},["YES","NO"],"label")=="YES"

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("mode",choices=["verdict","issue"]);p.add_argument("packet",type=Path);p.add_argument("out",type=Path)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    fn=verdict if a.mode=="verdict" else issue
    for arm,q,criterion,answer,expected in CONTROLS:
        item=dict(arm=arm,prompt=q,criterion=criterion,answer=answer)
        if a.mode=="issue":expected=(answer in ("The rate is 30%.","Please send me more information."))
        if fn(item)!=expected:raise ValueError(f"Calibration failure for {arm}: {answer}")
    for row in map(json.loads,a.packet.read_text(encoding="utf8").splitlines()):
        path=a.out/(row["token"]+".json")
        if not path.exists():
            got=fn(row);t=path.with_suffix('.tmp')
            t.write_text(json.dumps(dict(token=row["token"],value=got)),encoding="utf8");t.replace(path)
