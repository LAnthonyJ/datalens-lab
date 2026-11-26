"""Build a byte-traceable copy of the frozen runner for the 512-token sensitivity test."""
from pathlib import Path
import hashlib
import json
import runpy
import sys
import tempfile

source=Path(__file__).with_name("infer.py")
record=json.loads(source.with_name("freeze.json").read_text(encoding="utf-8-sig"))
if hashlib.sha256(source.read_bytes()).hexdigest()!=record["code"]["infer.py"]:
    raise ValueError("The frozen runner differs from the registered version")
# Change only the budget in the manifest, generation call and termination metadata.
text=source.read_text(encoding="utf-8-sig")
if text.count("max_new_tokens=128")!=2 or text.count("limit==128")!=1:
    raise ValueError("Unexpected generation settings")
text=text.replace("max_new_tokens=128","max_new_tokens=512").replace("limit==128","limit==512")
with tempfile.TemporaryDirectory() as temp:
    script=Path(temp)/"infer_512.py"
    script.write_bytes(text.encode("utf8"))
    runpy.run_path(str(script),run_name="__main__")
