"""
Data Preparation: Convert selected DataMind-12K data to Qwen training format.

This script:
1. Loads train_2k.json and val_500.json
2. Renames "messages" → "trajectory" (as expected by ray_train_exercise.ipynb)
3. Creates HuggingFace Datasets compatible with Qwen's apply_chat_template
4. Saves to disk for use with ray_train_exercise.ipynb
"""

import json
import os

from datasets import Dataset, DatasetDict


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_to_dataset(samples):
    """
    Convert samples from DataMind-12K format to a HuggingFace Dataset
    compatible with the preprocess_dataset function in ray_train_exercise.ipynb.

    Input format per sample:
      {"id": ..., "messages": [...], "level": ..., "filename": ...}

    Output Dataset columns:
      trajectory: list of {"role": ..., "content": ...} dicts
      id: str
      level: str
      filename: str
    """
    trajectories = []
    ids = []
    levels = []
    filenames = []

    for sample in samples:
        # Rename "messages" → "trajectory" for compatibility with notebook
        trajectories.append(sample["messages"])
        ids.append(sample.get("id", ""))
        levels.append(sample.get("level", "N/A"))
        filenames.append(sample.get("filename", ""))

    dataset = Dataset.from_dict({
        "trajectory": trajectories,
        "id": ids,
        "level": levels,
        "filename": filenames,
    })

    return dataset


def main():
    base_dir = r"h:\数据科学与大数据技术\大数据软件与应用\project2"

    # Load selected data
    print("[1/3] Loading selected data...")
    train_data = load_json(os.path.join(base_dir, "train_2k.json"))
    val_data = load_json(os.path.join(base_dir, "val_500.json"))
    print(f"  Train samples: {len(train_data)}")
    print(f"  Val   samples: {len(val_data)}")

    # Convert to HuggingFace Datasets
    print("[2/3] Converting to HuggingFace Dataset format...")
    train_dataset = convert_to_dataset(train_data)
    val_dataset = convert_to_dataset(val_data)

    print(f"  Train dataset: {train_dataset}")
    print(f"  Val   dataset: {val_dataset}")

    # Verify a sample trajectory - check it can be used with Qwen chat template
    sample_traj = train_dataset[0]["trajectory"]
    roles = [m["role"] for m in sample_traj]
    print(f"  Sample trajectory roles: {roles}")
    print(f"  Sample trajectory length (messages): {len(sample_traj)}")

    # Create DatasetDict and save
    print("[3/3] Saving datasets...")
    dataset_dict = DatasetDict({
        "train": train_dataset,
        "validation": val_dataset,
    })

    output_dir = os.path.join(base_dir, "datamind_selected")
    dataset_dict.save_to_disk(output_dir)
    print(f"  Saved to: {output_dir}")

    # Also save as separate train/val directories for more flexibility
    train_dir = os.path.join(base_dir, "datamind_train")
    val_dir = os.path.join(base_dir, "datamind_val")
    train_dataset.save_to_disk(train_dir)
    val_dataset.save_to_disk(val_dir)
    print(f"  Train only saved to: {train_dir}")
    print(f"  Val   only saved to: {val_dir}")

    # Quick sanity check: load back and verify
    print("\n[Sanity Check] Reloading datasets...")
    reloaded = DatasetDict.load_from_disk(output_dir)
    print(f"  Train: {reloaded['train']}")
    print(f"  Val:   {reloaded['validation']}")
    print(f"  Train[0] id: {reloaded['train'][0]['id']}")
    print(f"  Train[0] trajectory has {len(reloaded['train'][0]['trajectory'])} messages")

    print("\nDone! Data is ready for ray_train_exercise.ipynb.")


if __name__ == "__main__":
    main()
