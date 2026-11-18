"""Train and validate a DataLens text model on local Arrow or JSONL splits."""
import argparse
import math
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from demo import ROOT, local_paths


def tokenize(dataset, tokenizer, length):
    def encode(row):
        text = tokenizer.apply_chat_template(row["trajectory"], tokenize=False)
        enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True,
                        truncation=True, max_length=length)
        labels = [-100] * len(enc.input_ids)
        for match in re.finditer(r"<\|im_start\|>assistant\n(.*?<\|im_end\|>)", text, re.S):
            for i, (start, end) in enumerate(enc.offset_mapping):
                if match.start(1) <= start < end <= match.end(1):
                    labels[i] = enc.input_ids[i]
        return {"input_ids": enc.input_ids, "labels": labels}
    encoded = dataset.map(encode, remove_columns=dataset.column_names)
    valid = encoded.filter(lambda row: any(x != -100 for x in row["labels"][1:]))
    print(f"Kept {len(valid)}/{len(dataset)} rows; dropped {len(dataset)-len(valid)} without shifted targets.")
    if not len(valid):
        raise ValueError("Split has no supervised tokens after truncation")
    return valid


def train_func(cfg):
    import torch
    from datasets import load_from_disk
    from ray import train
    from ray.train import Checkpoint
    from ray.train.torch import prepare_model, prepare_data_loader
    from torch.utils.data import DataLoader
    from transformers import (AutoConfig, AutoModelForCausalLM, AutoTokenizer,
                              DataCollatorForSeq2Seq, get_linear_schedule_with_warmup)

    torch.manual_seed(42)
    smoke = cfg["smoke"]
    tok = AutoTokenizer.from_pretrained(cfg["model"], local_files_only=True)
    tok.pad_token = tok.pad_token or tok.eos_token
    splits = load_from_disk(cfg["tokens"])
    if smoke:
        conf = AutoConfig.from_pretrained(cfg["model"]).get_text_config()
        conf.hidden_size, conf.intermediate_size = 32, 64
        conf.num_attention_heads, conf.num_key_value_heads, conf.head_dim = 2, 1, 16
        conf.layer_types = ["linear_attention", "full_attention"]
        conf.num_hidden_layers = 2
        conf.linear_num_key_heads = conf.linear_num_value_heads = 2
        conf.linear_key_head_dim = conf.linear_value_head_dim = 16
        model = AutoModelForCausalLM.from_config(conf)
    else:
        model = AutoModelForCausalLM.from_pretrained(cfg["model"], dtype=torch.bfloat16)
        model.gradient_checkpointing_enable()
    model.config.use_cache = False
    collate = DataCollatorForSeq2Seq(tok, return_tensors="pt")
    def loader(split, shuffle):
        return prepare_data_loader(DataLoader(splits[split], batch_size=1 if smoke else 4,
                                              shuffle=shuffle, collate_fn=collate))
    batches, val = loader("train", True), loader("validation", False)
    model = prepare_model(model)
    opt = torch.optim.AdamW(model.parameters(), lr=5e-5, weight_decay=0.01)
    accum = 4
    steps = math.ceil(len(batches) / accum)
    sched = get_linear_schedule_with_warmup(opt, max(1, int(steps * 0.05)), steps)
    model.train()
    updates = 0
    for index, batch in enumerate(batches):
        group = min(accum, len(batches) - index // accum * accum)
        loss = model(**batch).loss
        if not torch.isfinite(loss):
            raise ValueError("Non-finite training loss")
        (loss / group).backward()
        if (index + 1) % accum == 0 or index + 1 == len(batches):
            opt.step()
            sched.step()
            opt.zero_grad()
            updates += 1
    model.eval()
    score = count = 0
    with torch.inference_mode():
        for batch in val:
            targets = int((batch["labels"][:, 1:] != -100).sum())
            score += float(model(**batch).loss) * targets
            count += targets
    val_loss = score / count
    if not math.isfinite(val_loss):
        raise ValueError("Non-finite validation loss")
    with TemporaryDirectory() as tmp:
        core = getattr(model, "module", model)
        torch.save(core.state_dict(), Path(tmp) / "model.pt")
        core.config.save_pretrained(tmp)
        tok.save_pretrained(tmp)
        if smoke:
            restored = AutoModelForCausalLM.from_config(core.config)
            restored.load_state_dict(torch.load(Path(tmp) / "model.pt", weights_only=True, map_location="cpu"), strict=True)
        train.report({"validation_loss": val_loss, "global_step": updates}, checkpoint=Checkpoint.from_directory(tmp))


def main(argv=None):
    from datasets import DatasetDict, load_dataset, load_from_disk
    import ray
    from ray.train import CheckpointConfig, RunConfig, ScalingConfig
    from ray.train.torch import TorchTrainer
    from transformers import AutoTokenizer
    import uuid

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "runs" / "prepared")
    parser.add_argument("--train-jsonl", type=Path)
    parser.add_argument("--val-jsonl", type=Path)
    parser.add_argument("--model-dir")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs" / "training")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if bool(args.train_jsonl) != bool(args.val_jsonl):
        parser.error("Supply both JSONL splits")
    splits = (load_dataset("json", data_files={"train": str(args.train_jsonl), "validation": str(args.val_jsonl)})
              if args.train_jsonl else load_from_disk(str(args.data_dir)))
    base, _ = local_paths(args.model_dir, base_only=True)
    tok = AutoTokenizer.from_pretrained(base)
    result_dir = args.output_dir.resolve() / uuid.uuid4().hex[:12]
    token_dir = result_dir / "tokens"
    encoded = {}
    for split in ("train", "validation"):
        ds = splits[split]
        if args.smoke:
            ds = ds.select(range(min(128, len(ds))))
        ds = tokenize(ds, tok, 1024)
        if args.smoke:
            ds = ds.select(range(5 if split == "train" else 2))
            def short_span(row):
                first = next(i for i, target in enumerate(row["labels"][1:], 1) if target != -100)
                start = max(0, first - 16)
                return {key: row[key][start:start + 48] for key in ("input_ids", "labels")}
            ds = ds.map(short_span)
        encoded[split] = ds
    DatasetDict(encoded).save_to_disk(str(token_dir))
    ray.init(include_dashboard=False, num_cpus=2 if args.smoke else None,
             **({"object_store_memory": 80 * 1024**2} if args.smoke else {}))
    try:
        result = TorchTrainer(train_func, train_loop_config={"model": str(base.resolve()), "tokens": str(token_dir), "smoke": args.smoke},
            scaling_config=ScalingConfig(num_workers=1, use_gpu=not args.smoke),
            run_config=RunConfig(storage_path=str(result_dir), name="qwen-datamind",
                checkpoint_config=CheckpointConfig(num_to_keep=1, checkpoint_score_attribute="validation_loss", checkpoint_score_order="min"))).fit()
        print(result.metrics, result.checkpoint)
    finally:
        ray.shutdown()


if __name__ == "__main__":
    main()
