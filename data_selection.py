"""
Data Selection Pipeline for DataMind-12K → Qwen Fine-tuning
===========================================================
Implements three complementary data selection methods:
  1. Complexity-based filtering (LP/IFD-inspired)
  2. Quality-based filtering (CLEAR-inspired)
  3. DEITA-style Score-First, Diversity-Aware selection

Selects 2000 training + 500 validation samples from datamind_12k.json
"""

import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import random

random.seed(42)
np.random.seed(42)

# ─── Load Data ───────────────────────────────────────────────────────────────

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_data(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[Loaded] {len(data)} samples from {filepath}")
    return data

# ─── Method 1: Complexity-based Scoring ──────────────────────────────────────

def compute_complexity_score(sample):
    """
    Compute a complexity score based on:
      - level field (pre-labeled difficulty)
      - Number of conversation turns
      - Total instruction/user content length
      - Presence of code blocks
      - Ratio of assistant thinking to code

    Returns score in [0, 1], higher = more complex.
    """

    level_map = {
        'easy':           0.10,
        'Simple':         0.20,
        'Moderate':       0.50,
        'Complex':        0.70,
        'Highly Complex': 0.95,
        'N/A':            0.35,  # unknown default, slightly below average
    }

    level = sample.get('level', 'N/A')
    level_score = level_map.get(level, 0.35)

    messages = sample.get('messages', [])
    user_content   = [m['content'] for m in messages if m['role'] == 'user']
    asst_content   = [m['content'] for m in messages if m['role'] == 'assistant']
    system_content = [m['content'] for m in messages if m['role'] == 'system']

    # Turn count (normalize: 5-turns → 0.5, 10-turns → 0.8, max 12+)
    num_turns = sum(1 for m in messages if m['role'] == 'assistant')
    turn_score = min(num_turns / 10.0, 1.0)

    # User content length (longer questions tend to be more complex)
    total_user_len = sum(len(c) for c in user_content)
    len_score = min(total_user_len / 4000.0, 1.0)

    # Number of code blocks (0 → 0.0, 1-2 → 0.5, 3+ → 1.0)
    all_text = ' '.join(user_content + asst_content)
    code_blocks = len(re.findall(r'```python|```sql|<code>', all_text))
    code_score = min(code_blocks / 4.0, 1.0)

    # Ratio of thinking vs direct answer (more thinking → more reasoning)
    think_len = sum(len(re.findall(r'<think>(.*?)</think>', c, re.DOTALL))
                    for c in asst_content)
    answer_len = sum(len(re.findall(r'<answer>(.*?)</answer>', c, re.DOTALL))
                     for c in asst_content)
    total_tag_len = think_len + answer_len
    if total_tag_len > 0:
        think_ratio = think_len / total_tag_len
    else:
        think_ratio = 0.5

    # Weighted combination
    complexity = (
        0.30 * level_score +
        0.20 * turn_score +
        0.15 * len_score +
        0.20 * code_score +
        0.15 * think_ratio
    )
    return complexity

# ─── Method 2: Quality-based Scoring ─────────────────────────────────────────

def compute_quality_score(sample):
    """
    Compute a quality score based on:
      - Proper structure (has <think>, <code>, <answer> tags)
      - Sufficient response length
      - Consistency (non-empty responses, well-formed messages)
      - System prompt completeness
      - Multi-turn coherence

    Returns score in [0, 1], higher = better quality.
    """

    messages = sample.get('messages', [])
    asst_content = [m['content'] for m in messages if m['role'] == 'assistant']

    if len(asst_content) == 0:
        return 0.0

    # Tag completeness: each assistant msg should have proper structure
    tag_scores = []
    for c in asst_content:
        has_think  = '<think>' in c and '</think>' in c
        has_code   = ('<code>' in c and '</code>' in c) or ('```python' in c) or ('```sql' in c)
        has_answer = '<answer>' in c and '</answer>' in c

        # A well-formed response has think + (code or answer)
        if has_think and (has_code or has_answer):
            tag_scores.append(1.0)
        elif has_think:
            tag_scores.append(0.6)
        elif has_answer:
            tag_scores.append(0.5)
        else:
            tag_scores.append(0.1)

    tag_quality = np.mean(tag_scores) if tag_scores else 0.0

    # Response completeness: check for empty/truncated responses
    min_asst_len = min(len(c) for c in asst_content) if asst_content else 0
    len_quality = min(min_asst_len / 200.0, 1.0)  # at least 200 chars per response

    # System message quality (should be detailed)
    system_msgs = [m['content'] for m in messages if m['role'] == 'system']
    sys_quality = min(len(system_msgs[0]) / 2000.0, 1.0) if system_msgs else 0.0

    # Multi-turn coherence: messages should alternate correctly
    roles = [m['role'] for m in messages]
    valid_pattern = True
    for i in range(1, len(roles)):
        if roles[i] == roles[i-1]:
            valid_pattern = False
            break
    coh_quality = 1.0 if valid_pattern else 0.3

    # Weighted combination
    quality = (
        0.35 * tag_quality +
        0.20 * len_quality +
        0.15 * sys_quality +
        0.30 * coh_quality
    )
    return quality

# ─── Method 3: DEITA-style Diversity-Aware Selection ─────────────────────────

def build_text_representation(sample):
    """
    Build a text representation of the sample for embedding.
    Concatenate system prompt + all user questions.
    """
    messages = sample.get('messages', [])
    parts = []
    for m in messages:
        if m['role'] in ('system', 'user'):
            # Truncate very long content for embedding purposes
            content = m['content']
            if len(content) > 2000:
                content = content[:2000]
            parts.append(content)
    return ' '.join(parts)

def compute_embeddings(samples):
    """
    Compute TF-IDF embeddings for all samples.
    """
    texts = [build_text_representation(s) for s in samples]
    vectorizer = TfidfVectorizer(
        max_features=5000,
        stop_words='english',
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    embeddings = vectorizer.fit_transform(texts)
    print(f"[Embeddings] Shape: {embeddings.shape}, features: {len(vectorizer.get_feature_names_out())}")
    return embeddings, vectorizer

def deita_selection(samples, scores, embeddings, budget, diversity_threshold=0.85):
    """
    Score-First, Diversity-Aware selection (DEITA Repr Filter).

    1. Sort samples by combined score descending
    2. Iteratively add samples that are sufficiently different from already-selected ones
    3. Continue until budget is reached

    Returns selected indices.
    """
    n = len(samples)
    order = np.argsort(scores)[::-1]  # descending score

    selected_indices = []
    eligible = np.ones(n, dtype=bool)
    columns = embeddings.T.tocsr()
    for idx in order:
        if eligible[idx]:
            selected_indices.append(idx)
            if len(selected_indices) >= budget:
                break
            similar = embeddings[idx] @ columns
            eligible[similar.indices[similar.data >= diversity_threshold]] = False

    return selected_indices

def kmeans_cluster_selection(samples, scores, embeddings, budget, n_clusters=50):
    """
    Alternative: K-means clustering + within-cluster complexity selection.
    Ensures diversity by picking top samples from each cluster proportional
    to cluster size.
    """
    from sklearn.cluster import KMeans

    emb_dense = embeddings.toarray()
    n_clusters = min(n_clusters, budget, len(samples))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(emb_dense)

    cluster_counts = Counter(labels)
    total = len(samples)

    selected = []
    for cluster_id in range(n_clusters):
        cluster_indices = [i for i, l in enumerate(labels) if l == cluster_id]
        cluster_size = len(cluster_indices)

        # Proportional allocation
        alloc = max(1, int(budget * cluster_size / total))

        # Select top-scoring samples from this cluster
        cluster_scores = [(i, scores[i]) for i in cluster_indices]
        cluster_scores.sort(key=lambda x: x[1], reverse=True)
        selected.extend([i for i, _ in cluster_scores[:alloc]])

    # Trim to exact budget
    selected = selected[:budget]
    return selected

# ─── Main Pipeline ───────────────────────────────────────────────────────────

def run_selection_pipeline(data_path, train_budget=2000, val_budget=500, output_dir=ROOT / "runs" / "selection"):
    """
    Full data selection pipeline:
      1. Load data
      2. Compute complexity & quality scores
      3. Filter low-quality samples
      4. Apply DEITA diversity-aware selection → train set
      5. Select validation set from remaining
      6. Save selected data
    """
    # 1. Load
    data = load_data(data_path)

    # 2. Compute scores
    print("\n[Step 1] Computing complexity scores (Method 1)...")
    complexity_scores = np.array([compute_complexity_score(s) for s in data])

    print("[Step 2] Computing quality scores (Method 2)...")
    quality_scores = np.array([compute_quality_score(s) for s in data])

    # Combined score: c * q (DEITA formulation)
    combined_scores = complexity_scores * quality_scores

    print(f"\n[Score Stats]")
    print(f"  Complexity: mean={complexity_scores.mean():.3f}, std={complexity_scores.std():.3f}")
    print(f"  Quality:    mean={quality_scores.mean():.3f}, std={quality_scores.std():.3f}")
    print(f"  Combined:   mean={combined_scores.mean():.3f}, std={combined_scores.std():.3f}")

    # Print top/bottom examples
    top_idx = np.argsort(combined_scores)[-5:][::-1]
    bot_idx = np.argsort(combined_scores)[:5]
    print("\n  Top-5 samples (high complexity * quality):")
    for i, idx in enumerate(top_idx):
        print(f"    {i+1}. id={data[idx]['id']}, level={data[idx].get('level','?')}, "
              f"c={complexity_scores[idx]:.3f}, q={quality_scores[idx]:.3f}, combined={combined_scores[idx]:.3f}")
    print("  Bottom-5 samples:")
    for i, idx in enumerate(bot_idx):
        print(f"    {i+1}. id={data[idx]['id']}, level={data[idx].get('level','?')}, "
              f"c={complexity_scores[idx]:.3f}, q={quality_scores[idx]:.3f}, combined={combined_scores[idx]:.3f}")

    # 3. Filter low-quality samples (bottom 15% by quality score)
    print("\n[Step 3] Filtering low-quality samples (CLEAR Auto-Filter)...")
    quality_threshold = np.percentile(quality_scores, 15)
    quality_mask = quality_scores >= quality_threshold
    n_filtered_out = (~quality_mask).sum()
    print(f"  Quality threshold (15th percentile): {quality_threshold:.3f}")
    print(f"  Filtered out: {n_filtered_out} low-quality samples")
    print(f"  Remaining: {quality_mask.sum()} samples")

    # Apply filter
    filtered_indices = [i for i, keep in enumerate(quality_mask) if keep]
    seen = set()
    unique = []
    for i in filtered_indices:
        messages = [(m["role"], " ".join(m["content"].split())) for m in data[i]["messages"]]
        digest = hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).digest()
        if digest not in seen:
            unique.append(i)
            seen.add(digest)
    filtered_indices = unique
    filtered_data = [data[i] for i in filtered_indices]
    filtered_complexity = complexity_scores[quality_mask]
    filtered_quality = quality_scores[quality_mask]
    filtered_combined = combined_scores[filtered_indices]

    # 4. Compute embeddings for filtered data
    print("\n[Step 4] Computing TF-IDF embeddings for diversity selection...")
    embeddings, vectorizer = compute_embeddings(filtered_data)

    # 5. DEITA selection for training set
    print(f"\n[Step 5] DEITA diversity-aware selection → {train_budget} training samples...")
    train_local_indices = deita_selection(
        filtered_data,
        filtered_combined,
        embeddings,
        budget=train_budget,
        diversity_threshold=0.85,
    )

    train_selected = [filtered_data[i] for i in train_local_indices]
    train_global_indices = [filtered_indices[i] for i in train_local_indices]

    print(f"  Selected {len(train_selected)} training samples")

    # Report training set stats
    train_levels = Counter(s.get('level', 'N/A') for s in train_selected)
    print(f"  Level distribution: {dict(train_levels)}")

    # 6. Select validation set from remaining samples (stratified by level)
    print(f"\n[Step 6] Selecting {val_budget} validation samples (stratified by level)...")
    train_set = set(train_global_indices)
    train_ids = {s['id'] for s in train_selected if s.get('id')}

    # Build remaining list with global index tracking
    remaining_entries = []  # (local_idx, global_idx, data_item, combined_score)
    for local_i, global_i in enumerate(filtered_indices):
        if global_i not in train_set and data[global_i].get('id') not in train_ids:
            remaining_entries.append({
                'local': local_i,
                'global': global_i,
                'data': filtered_data[local_i],
                'score': filtered_combined[local_i],
            })

    # Stratified sampling: proportional allocation per level
    level_to_entries = {}
    for entry in remaining_entries:
        lvl = entry['data'].get('level', 'N/A')
        level_to_entries.setdefault(lvl, []).append(entry)

    total_remaining = len(remaining_entries)
    if total_remaining < val_budget or len(train_selected) != train_budget:
        raise ValueError("Insufficient distinct samples for the requested split sizes")
    for level, entries in level_to_entries.items():
        quota = val_budget * len(entries) / total_remaining
        level_to_entries[level] = {"entries": entries, "alloc": int(quota), "fraction": quota % 1}
    left = val_budget - sum(info["alloc"] for info in level_to_entries.values())
    for info in sorted(level_to_entries.values(), key=lambda item: -item["fraction"])[:left]:
        info["alloc"] += 1

    # Select top-scoring samples from each level
    val_global_indices = []
    val_selected = []
    for lvl, info in level_to_entries.items():
        entries = info['entries']
        entries.sort(key=lambda e: e['score'], reverse=True)
        for e in entries[:info['alloc']]:
            val_selected.append(e['data'])
            val_global_indices.append(e['global'])

    val_levels = Counter(s.get('level', 'N/A') for s in val_selected)
    print(f"  Selected {len(val_selected)} validation samples")
    print(f"  Level distribution: {dict(val_levels)}")

    # Verify no overlap
    overlap = set(train_global_indices) & set(val_global_indices)
    print(f"  Train/Val overlap check: {len(overlap)} overlapping samples (should be 0)")

    # 7. Save results
    print("\n[Step 7] Saving selected data...")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_path = output_dir / "train_2k.json"
    val_path = output_dir / "val_500.json"
    with open(train_path, 'w', encoding='utf-8') as f:
        json.dump(train_selected, f, ensure_ascii=False, indent=2)
    print(f"  Training data saved to: {train_path}")

    with open(val_path, 'w', encoding='utf-8') as f:
        json.dump(val_selected, f, ensure_ascii=False, indent=2)
    print(f"  Validation data saved to: {val_path}")

    # Also save the indices and scores for reference
    meta = {
        'train_global_indices': [int(i) for i in train_global_indices],
        'val_global_indices': [int(i) for i in val_global_indices],
        'total_samples': int(len(data)),
        'filtered_out': int(n_filtered_out),
        'complexity_mean': float(complexity_scores.mean()),
        'quality_mean': float(quality_scores.mean()),
    }
    meta_path = output_dir / "selection_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  Metadata saved to: {meta_path}")

    return train_selected, val_selected

# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "datamind_12k.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs" / "selection")
    args = parser.parse_args()
    run_selection_pipeline(args.input, output_dir=args.output_dir)
