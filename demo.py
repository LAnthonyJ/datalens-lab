"""
Q1.4 — Data Agent Demo Website (Gradio)
========================================
Downloads base model from ModelScope (国内满速).
Supports both CPU (local) and GPU (server).

Usage:
    pip install gradio modelscope torch transformers
    python demo.py
    Open http://localhost:7860
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
if not _ckpt_candidates:
    raise FileNotFoundError(f"No checkpoint found in {RESULTS_DIR}")
CHECKPOINT_DIR = os.path.join(RESULTS_DIR, sorted(_ckpt_candidates)[-1])
print(f"Checkpoint: {CHECKPOINT_DIR}")

# ─── Imports ─────────────────────────────────────────────────────────────────

import gradio as gr
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32
print(f"Device: {DEVICE}, dtype: {DTYPE}")

SYSTEM_PROMPT = (
    "You are a helpful data analysis assistant. You can help users with:\n"
    "- Data cleaning and preprocessing\n"
    "- Statistical analysis and hypothesis testing\n"
    "- Data visualization recommendations\n"
    "- SQL and Python code for data tasks\n"
    "- Machine learning model selection and evaluation\n\n"
    "Please provide clear, step-by-step guidance with code examples."
)

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
print("  OK ✓")

# ─── Chat function ───────────────────────────────────────────────────────────

def chat(message: str, history: list, max_new_tokens: int = 256):
    print(f"\n[Chat] Received: {message[:80]}...")
    if not message.strip():
        return "Please enter a message."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history:
        if isinstance(turn, dict):
            messages.append(turn)
        elif isinstance(turn, (list, tuple)):
            if len(turn) >= 1 and turn[0]:
                messages.append({"role": "user", "content": str(turn[0])})
            if len(turn) >= 2 and turn[1]:
                messages.append({"role": "assistant", "content": str(turn[1])})
        else:
            messages.append({"role": "user", "content": str(turn)})
    messages.append({"role": "user", "content": message})

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)
    print(f"[Chat] Input tokens: {inputs['input_ids'].shape[1]}, generating...")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )
    print(f"[Chat] Generated {outputs[0].shape[0] - inputs['input_ids'].shape[1]} tokens")
    print(f"[Chat] Response: {response[:120]}...")
    return response

# ─── Gradio UI ───────────────────────────────────────────────────────────────

demo = gr.ChatInterface(
    fn=chat,
    title="Data Agent — Qwen3.5-0.8B Fine-tuned (DataMind-12K)",
    description=(
        "Fine-tuned on 2,000 high-quality data analysis conversations. "
        "Ask me anything about data science, statistics, SQL, Python, or ML!"
    ),
    examples=[
        "请帮我分析一个包含缺失值的数据集，应该怎么处理？",
        "Write a SQL query to find the top 10 customers by total purchase amount.",
        "如何判断两个变量之间是否存在显著的相关性？",
        "Explain the difference between L1 and L2 regularization.",
        "我想用Python画一个热力图来展示相关性矩阵，请给我代码。",
    ],
)

if __name__ == "__main__":
    print("\nStarting Gradio on http://localhost:7860 ...")
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
    )
