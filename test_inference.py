"""
Quick inference test — verify the fine-tuned model loads and works.
Downloads base model from ModelScope (国内满速).
"""

import os
import sys

from modelscope import snapshot_download

# ─── Download base model from ModelScope ─────────────────────────────────────

MODEL_NAME = "Qwen/Qwen3.5-0.8B"
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCAL_DIR = os.path.join(_SCRIPT_DIR, "qwen_model")

_model_subdir = os.path.normpath(os.path.join(_LOCAL_DIR, MODEL_NAME))
if not os.path.isdir(_model_subdir):
    print(f"Downloading {MODEL_NAME} from ModelScope (first time, ~3GB)...")
    _model_subdir = os.path.normpath(snapshot_download(MODEL_NAME, cache_dir=_LOCAL_DIR))
BASE_MODEL = _model_subdir
print(f"Base model: {BASE_MODEL}")

# ─── Checkpoint paths ────────────────────────────────────────────────────────

_LOCAL_CKPT = os.path.join(_SCRIPT_DIR, "ray results", "qwen-datamind-full")
_SERVER_CKPT = "/root/ray_results/qwen-datamind-full"
RESULTS_DIR = _LOCAL_CKPT if os.path.isdir(_LOCAL_CKPT) else _SERVER_CKPT

_ckpt_candidates = [
    d for d in os.listdir(RESULTS_DIR)
    if d.startswith("checkpoint_") and os.path.isdir(os.path.join(RESULTS_DIR, d))
]
CHECKPOINT_DIR = os.path.join(RESULTS_DIR, sorted(_ckpt_candidates)[-1])
print(f"Checkpoint: {CHECKPOINT_DIR}")

# ─── Imports ─────────────────────────────────────────────────────────────────

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32
print(f"Device: {DEVICE}")

# ─── Load ────────────────────────────────────────────────────────────────────

print("[1/3] Tokenizer from checkpoint...")
tokenizer = AutoTokenizer.from_pretrained(CHECKPOINT_DIR, padding_side="left")
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
print("  OK")

print("[2/3] Base model...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, torch_dtype=DTYPE,
    device_map=DEVICE if DEVICE == "cuda" else None,
)
if DEVICE == "cpu":
    model = model.to(DEVICE)
print("  OK")

print("[3/3] Fine-tuned weights...")
ckpt_path = os.path.join(CHECKPOINT_DIR, "model.pt")
state_dict = torch.load(ckpt_path, map_location=DEVICE, weights_only=True)
missing, unexpected = model.load_state_dict(state_dict, strict=False)
print(f"  Missing: {len(missing)}, Unexpected: {len(unexpected)}")
print("  OK")

# ─── Test inference ──────────────────────────────────────────────────────────

print("\nRunning test inference...")
messages = [
    {"role": "system", "content": "You are a helpful data analysis assistant."},
    {"role": "user", "content": "请用一句话介绍你自己。"},
]
text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
inputs = tokenizer(text, return_tensors="pt").to(model.device)

with torch.no_grad():
    outputs = model.generate(
        **inputs, max_new_tokens=200,
        temperature=0.7, top_p=0.9, do_sample=True,
        pad_token_id=tokenizer.pad_token_id,
    )

response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
print(f"\n  Response: {response}\n")
print("=" * 60)
print("All checks passed! Run: python demo.py")
