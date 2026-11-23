"""Offline DataLens Lab demo. Use --check for a real generation before launch."""
import argparse
import gc
import logging
import mmap
import warnings
import os
import socket
from pathlib import Path
from queue import Empty
from threading import Event, Lock, Thread
from time import monotonic

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
ROOT = Path(__file__).resolve().parent
PIN = "checkpoint_2026-05-24_06-08-05.338158"
SYSTEM = "You are a data analysis assistant. Answer the user's question directly and concisely. For SQL requests return only SQL unless an explanation is requested."


def local_paths(model_dir=None, checkpoint_dir=None, base_only=False):
    base = ROOT / "qwen_model" / "Qwen"
    candidates = [Path(model_dir)] if model_dir else [base / name for name in ("Qwen3.5-0.8B", "Qwen3___5-0___8B")]
    model = next((p for p in candidates if (p / "config.json").is_file()), None)
    if model is None:
        raise FileNotFoundError(f"Missing config.json in {candidates}. Supply --model-dir.")
    if base_only:
        return model, None
    ckpt = Path(checkpoint_dir) if checkpoint_dir else ROOT / "ray results" / "qwen-datamind-full" / PIN
    for name in ("model.pt", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja"):
        if not (ckpt / name).is_file():
            raise FileNotFoundError(f"Missing {ckpt / name}. Supply --checkpoint-dir.")
    return model, ckpt


def load_weights(path):
    import torch
    if os.name != "nt":
        return torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    # On Windows torch's private mmap reserves the entire checkpoint in the
    # commit budget. Map its verified tensor layout read-only for inference.
    from torch._subclasses.fake_tensor import FakeTensorMode
    with FakeTensorMode():
        layout = torch.load(path, map_location="cpu", weights_only=True, mmap=True)
    with path.open("rb") as file:
        backing = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
    result = {}
    for key, tensor in layout.items():
        storage = tensor.untyped_storage()
        offset = storage._checkpoint_offset
        if tensor.numel() == 0:
            result[key] = torch.empty_like(tensor, device="cpu")
            continue
        count = 1 + tensor.storage_offset() + sum((n - 1) * stride for n, stride in zip(tensor.shape, tensor.stride()))
        if offset is None or offset < 0 or offset + count * tensor.element_size() > len(backing):
            raise ValueError(f"Invalid archive offset for {key}")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="The given buffer is not writable")
            view = torch.frombuffer(backing, dtype=tensor.dtype, offset=offset,
                                    count=count)
        result[key] = view.as_strided(tensor.shape, tensor.stride(), tensor.storage_offset())
    return result


def cpu_weights(state, checkpoint):
    """Cache lossless FP32 views on disk to keep Windows commit usage bounded."""
    import hashlib
    import tempfile
    import numpy as np
    import torch
    with checkpoint.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    root = ROOT / "runs" / "cpu-weights" / digest
    root.mkdir(parents=True, exist_ok=True)
    converted = {}
    aliases = {}
    for name, tensor in state.items():
        if tensor.dtype != torch.bfloat16:
            converted[name] = tensor
            continue
        key = (tensor.data_ptr(), tuple(tensor.shape), tuple(tensor.stride()))
        if key not in aliases:
            path = root / (hashlib.sha256(name.encode()).hexdigest() + ".npy")
            if not path.exists():
                with tempfile.NamedTemporaryFile(dir=root, delete=False) as file:
                    tmp = Path(file.name)
                try:
                    target = np.lib.format.open_memmap(tmp, mode="w+", dtype="float32", shape=tuple(tensor.shape))
                    flat = tensor.reshape(-1)
                    for start in range(0, flat.numel(), 1024 * 1024):
                        chunk = flat[start:start + 1024 * 1024].float()
                        target.reshape(-1)[start:start + chunk.numel()] = chunk.numpy()
                    del target
                    try:
                        os.replace(tmp, path)
                    except PermissionError:
                        if not path.is_file():
                            raise
                finally:
                    tmp.unlink(missing_ok=True)
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="The given NumPy array is not writable")
                aliases[key] = torch.from_numpy(np.load(path, mmap_mode="r"))
        converted[name] = aliases[key]
    return converted


class Assistant:
    def __init__(self, args):
        import torch
        from accelerate import init_empty_weights
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

        base, checkpoint = local_paths(args.model_dir, args.checkpoint_dir, args.base_only)
        self.generation_lock = Lock()
        self.device = args.device
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if self.device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA unavailable. Start with run-demo.cmd and check the NVIDIA driver.")
        dtype = torch.float32 if self.device == "cpu" else (torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16)
        if self.device == "cpu":
            torch.set_num_threads(min(4, torch.get_num_threads()))
        self.tokenizer = AutoTokenizer.from_pretrained(checkpoint or base, local_files_only=True)
        if checkpoint:
            config = AutoConfig.from_pretrained(base, local_files_only=True)
            with init_empty_weights(include_buffers=False):
                model = AutoModelForCausalLM.from_config(config, dtype=dtype)
            state = load_weights(checkpoint / "model.pt")
            if self.device == "cpu":
                state = cpu_weights(state, checkpoint / "model.pt")
            model.load_state_dict(state, strict=True, assign=True)
            del state
            model.tie_weights()
        else:
            model = AutoModelForCausalLM.from_pretrained(base, dtype=dtype, local_files_only=True)
        self.model = model.to(device=self.device, dtype=dtype).eval()
        self.model.tie_weights()
        logging.info("device=%s dtype=%s model=%s checkpoint=%s", self.device, dtype, base, checkpoint)

    def prompt(self, message, history):
        if not message.strip():
            raise ValueError("Enter a question.")
        turns = []
        for item in history:
            content = item["content"]
            if isinstance(content, list):
                content = "".join(part["text"] for part in content if part.get("type") == "text")
            turns.append({"role": item["role"], "content": content})
        while True:
            messages = [{"role": "system", "content": SYSTEM}, *turns, {"role": "user", "content": message}]
            inputs = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, enable_thinking=False,
                                                        tokenize=True, return_tensors="pt", return_dict=True)
            if inputs["input_ids"].shape[1] <= 1024:
                return inputs.to(self.device)
            if not turns:
                raise ValueError("Question exceeds the 1,024-token context. Shorten the question.")
            turns.pop(0)
            while turns and turns[0]["role"] != "user":
                turns.pop(0)

    def generate(self, message, history, limit=128):
        with self.generation_lock:
            yield from self._stream(message, history, limit)

    def _stream(self, message, history, limit):
        import torch
        from transformers import TextIteratorStreamer
        inputs = self.prompt(message, history)
        if self.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        input_tokens = inputs["input_ids"].shape[-1]
        stop = Event()
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=0.5)
        errors = []
        def worker():
            try:
                with torch.inference_mode():
                    self.model.generate(**inputs, streamer=streamer, max_new_tokens=limit, do_sample=False,
                                        repetition_penalty=1.08, no_repeat_ngram_size=5,
                                        stopping_criteria=[lambda ids, scores, **kw: stop.is_set()],
                                        pad_token_id=self.tokenizer.eos_token_id)
            except Exception as exc:
                errors.append("Generation ran out of memory. Retry with a shorter question."
                              if isinstance(exc, (MemoryError, torch.OutOfMemoryError)) else str(exc))
                logging.error("Generation failed: %s", errors[-1])
                streamer.end()
        started = monotonic()
        thread = Thread(target=worker, daemon=True)
        thread.start()
        answer = ""
        try:
            while True:
                try:
                    part = next(streamer)
                except Empty:
                    continue
                except StopIteration:
                    break
                if part:
                    if not answer:
                        logging.info("first text %.2fs", monotonic() - started)
                    answer += part
                    yield answer
            if errors:
                raise RuntimeError(errors[0])
            if not answer.strip():
                raise RuntimeError("The model returned an empty answer.")
        finally:
            stop.set()
            thread.join()
            del inputs
            if errors:
                gc.collect()
                if self.device == "cuda":
                    torch.cuda.empty_cache()
            peak = torch.cuda.max_memory_allocated() // (1024 ** 2) if self.device == "cuda" else 0
            logging.info("elapsed=%.2fs input_tokens=%d output_chars=%d peak_cuda_MiB=%d",
                         monotonic() - started, input_tokens, len(answer), peak)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir")
    parser.add_argument("--checkpoint-dir")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--cpu-only", dest="device", action="store_const", const="cpu")
    parser.add_argument("--base-only", action="store_true")
    parser.add_argument("--port", "--server-port", type=int, default=7860)
    parser.add_argument("--server-name", choices=["localhost", "127.0.0.1"], default="127.0.0.1")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not args.check:
        try:
            with socket.socket() as probe:
                probe.bind((args.server_name, args.port))
        except OSError as exc:
            parser.exit(2, f"Cannot listen on {args.server_name}:{args.port}: {exc}. Choose another --port.\n")
    assistant = Assistant(args)
    answer = list(assistant.generate("Write a SQL query to count all rows in the sales table.", [], 48))[-1]
    print("Warm-up:", answer, flush=True)
    if args.check:
        return
    import gradio as gr
    def chat(message, history):
        try:
            yield from assistant.generate(message, history)
        except (ValueError, RuntimeError) as exc:
            raise gr.Error(str(exc)) from exc
    ui = gr.ChatInterface(chat, title="DataLens Lab", description="An offline data analysis assistant.",
                          examples=["Write a SQL query to count rows in sales.", "How should I handle missing values in a dataset?"],
                          concurrency_limit=1, cache_examples=False, api_name="chat")
    ui.queue(max_size=4).launch(server_name=args.server_name, server_port=args.port, share=False)


if __name__ == "__main__":
    main()
