"""
Data Agent Web Demo — local Windows version.
Loads Qwen3.5-0.8B base model + DataMind-12K fine-tuned checkpoint.

Usage:
    python web_demo.py
    Open http://127.0.0.1:7860
"""

from argparse import ArgumentParser
from threading import Thread
import os
import sys

# ─── Paths ───────────────────────────────────────────────────────────────────

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Base model (downloaded from ModelScope)
BASE_MODEL_PATH = os.path.normpath(
    os.path.join(_SCRIPT_DIR, "qwen_model", "Qwen", "Qwen3.5-0.8B")
)
if not os.path.isdir(BASE_MODEL_PATH):
    # Fallback: download from ModelScope
    print("Base model not found, downloading from ModelScope...")
    from modelscope import snapshot_download
    _cache = os.path.join(_SCRIPT_DIR, "qwen_model")
    BASE_MODEL_PATH = os.path.normpath(
        snapshot_download("Qwen/Qwen3.5-0.8B", cache_dir=_cache)
    )

# Fine-tuned checkpoint (auto-detect)
_CKPT_ROOTS = [
    os.path.join(_SCRIPT_DIR, "ray results", "qwen-datamind-full"),
    os.path.join(_SCRIPT_DIR, "ray_results", "qwen-datamind-v2"),
    os.path.join(_SCRIPT_DIR, "ray results", "qwen-datamind-v2"),
]
FINE_TUNED_CKPT = None
for root in _CKPT_ROOTS:
    if os.path.isdir(root):
        dirs = sorted([
            d for d in os.listdir(root)
            if d.startswith("checkpoint_") and os.path.isdir(os.path.join(root, d))
        ])
        if dirs:
            FINE_TUNED_CKPT = os.path.join(root, dirs[-1])
            break

print(f"Base model:     {BASE_MODEL_PATH}")
print(f"Fine-tuned ckpt: {FINE_TUNED_CKPT}")

import gradio as gr
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer


def _get_args():
    parser = ArgumentParser(description="Data Agent web demo.")
    parser.add_argument("--cpu-only", action="store_true", help="Force CPU")
    parser.add_argument("--base-only", action="store_true", help="Skip fine-tuned weights")
    parser.add_argument("--share", action="store_true", default=False)
    parser.add_argument("--server-port", type=int, default=7860)
    parser.add_argument("--server-name", type=str, default="127.0.0.1")
    return parser.parse_args()


def _load_model_tokenizer(args):
    # Tokenizer from checkpoint or base model
    tokenizer_dir = FINE_TUNED_CKPT if FINE_TUNED_CKPT else BASE_MODEL_PATH
    print(f"Loading tokenizer from: {tokenizer_dir}")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)

    # Model
    device = "cuda" if (torch.cuda.is_available() and not args.cpu_only) else "cpu"
    dtype = torch.float32 if device == "cpu" else "auto"
    print(f"Device: {device}")

    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        dtype=dtype,
        device_map=device if device == "cuda" else None,
    )
    if device == "cpu":
        model = model.to(device)

    # Apply fine-tuned weights
    if FINE_TUNED_CKPT and not args.base_only:
        ckpt_file = os.path.join(FINE_TUNED_CKPT, "model.pt")
        if os.path.exists(ckpt_file):
            print(f"Loading fine-tuned weights from: {ckpt_file}")
            state_dict = torch.load(ckpt_file, map_location=device, weights_only=True)
            missing, unexpected = model.load_state_dict(state_dict, strict=False)
            print(f"  Missing: {len(missing)}, Unexpected: {len(unexpected)}")
        else:
            print(f"[WARN] No model.pt in {FINE_TUNED_CKPT}")
    else:
        print("[INFO] Using base model only")

    model = model.eval()
    model.generation_config.max_new_tokens = 2048
    return model, tokenizer


SYSTEM_PROMPT = (
    "You are a helpful Data Agent assistant. "
    "Reply in natural, conversational language. "
    "Only use code blocks (with ```python) when the user explicitly asks for code. "
    "For general questions, answer directly with plain text — no code formatting."
)


def _chat_stream(model, tokenizer, query, history):
    conversation = [{"role": "system", "content": SYSTEM_PROMPT}]
    for query_h, response_h in history:
        conversation.append({"role": "user", "content": query_h})
        conversation.append({"role": "assistant", "content": response_h})
    conversation.append({"role": "user", "content": query})
    input_text = tokenizer.apply_chat_template(
        conversation, add_generation_prompt=True, tokenize=False,
    )
    inputs = tokenizer([input_text], return_tensors="pt").to(model.device)
    streamer = TextIteratorStreamer(
        tokenizer=tokenizer, skip_prompt=True, timeout=120.0, skip_special_tokens=True
    )
    generation_kwargs = {
        **inputs,
        "streamer": streamer,
        "max_new_tokens": 512,
        "do_sample": True,
        "temperature": 0.8,
        "top_p": 0.95,
        "repetition_penalty": 1.2,
        "no_repeat_ngram_size": 4,
        "early_stopping": True,
        "eos_token_id": tokenizer.eos_token_id,
        "pad_token_id": tokenizer.pad_token_id,
    }
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()
    for new_text in streamer:
        yield new_text


def _launch_demo(args, model, tokenizer):
    def predict(_query, _chatbot, _task_history):
        print(f"User: {_query}")
        _chatbot.append({"role": "user", "content": _query})
        _chatbot.append({"role": "assistant", "content": ""})
        for new_text in _chat_stream(model, tokenizer, _query, history=_task_history):
            _chatbot[-1]["content"] += new_text
            yield _chatbot
        _task_history.append((_query, _chatbot[-1]["content"]))
        print(f"Response: {_chatbot[-1]['content'][:200]}...")

    def regenerate(_chatbot, _task_history):
        if not _task_history:
            yield _chatbot
            return
        item = _task_history.pop(-1)
        _chatbot.pop(-1)
        _chatbot.pop(-1)
        yield from predict(item[0], _chatbot, _task_history)

    with gr.Blocks(title="Data Agent", css="footer {display: none} .contain {max-width: 900px}") as demo:
        gr.Markdown("""
# Data Analysis Agent
**Qwen3.5-0.8B** fine-tuned on **DataMind-12K** — 2,000 high-quality data analysis trajectories.

**Capabilities:** Data Cleaning | Statistical Analysis | SQL & Python | Visualization | ML
""")
        chatbot = gr.Chatbot(label="Conversation")
        query = gr.Textbox(
            lines=2, label="Your Question",
            placeholder="E.g., Write a SQL query to find duplicate records in a table...",
        )
        task_history = gr.State([])

        with gr.Row():
            empty_btn = gr.Button("Clear", variant="secondary", size="sm")
            submit_btn = gr.Button("Send", variant="primary", size="sm")
            regen_btn = gr.Button("Regenerate", variant="secondary", size="sm")

        submit_btn.click(predict, [query, chatbot, task_history], [chatbot], show_progress=True)
        empty_btn.click(lambda: ([], []), outputs=[chatbot, task_history])
        regen_btn.click(regenerate, [chatbot, task_history], [chatbot], show_progress=True)

        gr.Examples(
            examples=[
                "Write a Python script to detect and remove outliers from a dataset using the IQR method.",
                "请帮我写一段SQL代码，找出表中重复的记录并按出现次数排序。",
                "Explain the difference between L1 and L2 regularization with examples.",
                "Plot a correlation heatmap from a pandas DataFrame. Give me the Python code.",
                "什么是p-value？如何解释假设检验的结果？",
            ],
            inputs=query,
        )

    demo.queue().launch(
        share=args.share,
        server_port=args.server_port,
        server_name=args.server_name,
    )


def main():
    args = _get_args()
    model, tokenizer = _load_model_tokenizer(args)
    _launch_demo(args, model, tokenizer)


if __name__ == "__main__":
    main()
