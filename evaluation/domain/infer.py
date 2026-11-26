"""Greedy, first-attempt evaluation. Each saved row is an atomic resumable receipt."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter

SYSTEM = ("You teach statistics and help with data analysis. Reply in the user's language. "
          "Explain concepts in plain language. Give code when requested. Ask for missing "
          "information before interpreting unseen data. Only report results supported by the conversation.")


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def write_atomic(path, row):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf8")
    os.replace(tmp, path)


def main():
    import torch
    from accelerate import init_empty_weights
    from transformers import AutoTokenizer, AutoConfig, AutoModelForCausalLM
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("base", "inputs", "out"):
        p.add_argument("--"+key, type=Path, required=True)
    p.add_argument("--checkpoint", type=Path)
    p.add_argument("--weight-sha", required=True)
    p.add_argument("--device", choices=["cuda","cpu"], default="cuda")
    p.add_argument("--batch", type=int, default=4)
    args=p.parse_args()
    weights = args.checkpoint if args.checkpoint else next(args.base.glob("*.safetensors"))
    if digest(weights) != args.weight_sha:
        raise ValueError("Unexpected checkpoint hash")
    rows=[json.loads(s) for s in args.inputs.read_text(encoding="utf-8-sig").splitlines()]
    assert len(set(r["id"] for r in rows)) == len(rows)
    import re
    assert all(re.fullmatch(r"[a-zA-Z0-9_-]+",r["id"]) for r in rows)
    args.out.mkdir(parents=True, exist_ok=True)
    tok=AutoTokenizer.from_pretrained(args.base, local_files_only=True, padding_side="left")
    tok.pad_token = tok.eos_token if tok.pad_token is None else tok.pad_token
    dtype=torch.bfloat16 if args.device=="cuda" else torch.float32
    protocol=dict(inputs=digest(args.inputs),weight=args.weight_sha,source=digest(Path(__file__)),
                  tokenizer=digest(args.base/"tokenizer.json"),template=digest(args.base/"chat_template.jinja"),
                  config=digest(args.base/"config.json"),device=args.device,batch=args.batch,dtype=str(dtype),
                  transformers=__import__("transformers").__version__,torch=str(torch.__version__),
                  prompt=SYSTEM,max_new_tokens=128,context_budget=4096,do_sample=False)
    manifest=args.out/"manifest.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf8"))!=protocol:
        raise ValueError("Resume settings differ")
    write_atomic(manifest,protocol)
    if args.checkpoint:
        config=AutoConfig.from_pretrained(args.base).get_text_config()
        with init_empty_weights():
            model=AutoModelForCausalLM.from_config(config,dtype=dtype)
        state=torch.load(weights,map_location="cpu",mmap=True,weights_only=True)
        model.load_state_dict(state,strict=True,assign=True)
        del state
        model.tie_weights()
        model=model.to(device=args.device,dtype=dtype)
    else:
        model=AutoModelForCausalLM.from_pretrained(args.base,dtype=dtype,device_map={"":args.device},local_files_only=True)
    model.eval()
    def prompt(r):
        return tok.apply_chat_template([{"role":"system","content":SYSTEM},{"role":"user","content":r["prompt"]}],
                   tokenize=False,add_generation_prompt=True,enable_thinking=False)
    for offset in range(0,len(rows),args.batch):
        group=rows[offset:offset+args.batch]
        if all((args.out/(r["id"]+".json")).exists() for r in group):
            continue
        start=perf_counter()
        items=[tok(prompt(r),add_special_tokens=False)["input_ids"] for r in group]
        valid=[]
        for r,ids in zip(group,items):
            if len(ids)>4096:
                write_atomic(args.out/(r["id"]+".json"),dict(id=r["id"],answer="",status="input_limit",input_tokens=len(ids)))
            else:
                valid.append((r,ids))
        if not valid: continue
        batch=tok.pad([{"input_ids":ids} for _,ids in valid],padding=True,return_tensors="pt").to(args.device)
        with torch.inference_mode():
            end_ids = model.generation_config.eos_token_id
            stops = sorted(set([tok.eos_token_id]+(end_ids if isinstance(end_ids,list) else [end_ids]))-{None})
            output=model.generate(**batch,max_new_tokens=128,do_sample=False,repetition_penalty=1.08,
                        no_repeat_ngram_size=5,eos_token_id=stops,pad_token_id=tok.pad_token_id)
        for (r,ids),seq in zip(valid,output[:,batch.input_ids.shape[1]:].tolist()):
            limit=next((j for j,x in enumerate(seq) if x in stops),len(seq))
            dst=args.out/(r["id"]+".json")
            if not dst.exists():
                write_atomic(dst,dict(id=r["id"],answer=tok.decode(seq[:limit],skip_special_tokens=True),
                    status="length" if limit==128 else "ok",input_tokens=len(ids),output_tokens=limit))
        print(f"{offset+len(group)}/{len(rows)} {perf_counter()-start:.1f}s",flush=True)


if __name__=="__main__":
    main()
