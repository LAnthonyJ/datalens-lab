"""Numerical cross-check used to flag answers for blind adjudication, never to award credit by token match."""
from math import isclose
import re

NUMBER = re.compile(r'(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][-+]?\d+)?')
WORDS = dict(zip("zero one two three four five six seven eight nine ten".split(), range(11)))

def supported(answer, target, unit):
    text=answer.replace("−","-").replace("\\%","%")
    values=[float(m.group().replace(",","")) for m in NUMBER.finditer(text)]
    values.extend(v for word,v in WORDS.items() if re.search(r"\b"+word+r"\b",text,re.I))
    if unit in ("%","percentage points"):
        values.extend(100*float(n) for n in re.findall(r"\b(0\.\d+)\b",text) if unit=="%")
    # Accept round-to-two-decimals or 0.1% relative error at the stated scale.
    return any(isclose(x,target,rel_tol=.001,abs_tol=.00500001) for x in values)
