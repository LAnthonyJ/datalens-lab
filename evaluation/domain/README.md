# Reproduce the English comparison

Read the [frozen scoring protocol](PROTOCOL.md), [original manifest](freeze.json) and [SQL amendment](sql-amendment.json). The SQL amendment records the replacement of 180 overlapping query structures before SQL inference. The distributed [business cases](confirm-a.tsv) and [SQL fixtures](confirm-db.json) contain the final prompts, targets and source identifiers.

### Check the released answers without model weights

Run the following commands from this directory with Python and NumPy. The SQL replay executes all 960 saved model answers against the three fixtures and verifies every flag. The business replay recomputes the paired score and confidence interval from the published adjudicated answers.

```sh
python replay.py sql
python replay.py business
```

For a fresh Spider score from the saved model outputs, run `python replay.py export-spider --out work/spider-replay` and pass its `base` and `lora` folders to the official-scoring command below. Use `export-long` for the 100-question length diagnostic.

### Data and model preparation

Use Python 3.11 or newer. The inference receipts record PyTorch 2.7.1+cu118, Transformers 5.9.0, bfloat16 and a batch of four. The statistics code needs NumPy. The official SQL scorer needs tqdm and sqlparse 0.5.3. Preparing Spider from its archive also needs PyArrow. Keep the base model directory and the LoRA merged state dict outside version control. The precise weight hashes are in the protocol.

1. Download the authors' financial-report training tables as `work/tatqa-train.json`. The paired business questions use newly authored tasks and hypothetical worksheet assumptions applied to report values. TAT-QA data are by Fengbin Zhu and colleagues, released under CC BY 4.0. [Source data](https://raw.githubusercontent.com/NExTplusplus/TAT-QA/master/dataset_raw/tatqa_dataset_train.json) · [ACL paper](https://aclanthology.org/2021.acl-long.254/) · [Attribution license](https://creativecommons.org/licenses/by/4.0/)
2. Obtain the Spider 1.0 archive containing `spider_data/dev.json`, `train_spider.json` and `tables.json` as `work/spider-original.zip`. The original release is by Tao Yu and colleagues. Custom SQL uses a subset of the training-side schema definitions with new questions and synthetic rows. Spider materials retain CC BY-SA 4.0. [Original dataset](https://yale-lily.github.io/spider) · [Archive mirror](https://huggingface.co/datasets/HAL-9001/spider-databases) · [Share-alike license](https://creativecommons.org/licenses/by-sa/4.0/)
3. Download the authors' distilled test-suite databases as `work/spider-suites-official.download`. The selector verifies the archive hashes and extracts only the dev fixtures. Clone the evaluator and check out `e97acc546ecbee8fa27fa8dbf025ef61493a876c`. [Official archive](https://drive.google.com/file/d/1mkCx2GOFIqNesD4y8TDAO1yX1QZORP5w/view) · [Official scorer](https://github.com/taoyds/test-suite-sql-eval)

From this directory, with an empty output directory for each new run, build the inputs.

```sh
python confirmation_business.py work/tatqa-train.json work/confirm-a.tsv work/confirm-a.jsonl
python confirmation_sql.py work/spider-original.zip work/initial-db.json
python amend_sql.py work/initial-db.json results/sql-structure-audit.json work/confirm-db.json
python sql_cases.py --pack work/confirm-db.json --out work/confirm-b.jsonl
python prepare_spider.py work
python spider_inputs.py --dev work/dev.parquet --tables work/tables.json --out work/spider.jsonl
```

The full project history was available for the overlap check. The [overlap audit](results/overlap-summary.json) gives digests for those inputs. The [SQL structure check](results/sql-structure-audit-final.json) counts recurring operation sequences after identifiers and constants are removed. Nineteen different formal query structures span the 80 synthetic databases. Different schemas exercise the same operations repeatedly.

### Inference and scoring

Run these two commands for each input file, changing `TASK` to `confirm-a`, `confirm-b` or `spider`. Set `BASE_DIR` to the original Qwen directory and `LORA_PT` to the verified merged candidate.

```sh
python infer.py --base "$BASE_DIR" --inputs "work/$TASK.jsonl" --out "work/$TASK-base" --weight-sha 04b1c301231dd422b8860db31311ab2721511346a32cb1e079c4c4e5f1fe4696
python infer.py --base "$BASE_DIR" --checkpoint "$LORA_PT" --inputs "work/$TASK.jsonl" --out "work/$TASK-lora" --weight-sha 42eb9a799888a582eae0c2135026e2f4eaf6e8ae89471ec2d12dab9f3c2ecef7
for model in base lora; do
  python sql_cases.py --pack work/confirm-db.json --answers "work/confirm-b-$model" --out "work/confirm-b-$model-grades.jsonl"
  python spider_score.py --archive work/spider-original.zip --evaluator work/test-suite-sql-eval --fixtures work/official-suite --answers "work/spider-$model" --out "work/spider-$model-grades"
done
python paired.py sql work/confirm-b-base-grades.jsonl work/confirm-b-lora-grades.jsonl --expected 480
python blind.py work/confirm-a.tsv work/formal-blind --model base work/confirm-a-base --model lora work/confirm-a-lora
```

Distribute only `packet.jsonl` to reviewers. The key links answer IDs to model names and is used after adjudication. The local Qwen3-4B reviewer runs eight known-answer controls before scoring a packet. The initial pilot exposed conflicting boolean/reason fields in an earlier review format. Only the calibrated, single-verdict run contributes to the agreement statistics. To repeat it with Ollama serving qwen3:4b on localhost port 11439, use the named options below.

```sh
python calibrated_review.py --packet work/formal-blind/packet.jsonl --out work/formal-blind/reviewer2
python paired.py business work/formal-blind/key.jsonl work/formal-blind/adjudicated.jsonl --expected 400
```

The published second review used the calibrated GPU configuration on all 1,600 answers. With the same Ollama model served locally, set `DATALENS_REVIEW_PORT` to its port and run the commands below. The first command assigns a pass or fail. The second independently flags possible unsupported numbers and unnecessary data requests. The released adjudications also include the first reviewer's vote and a reason for the final decision. [Review procedure and agreement](REVIEW.md)

```sh
python gpu_review.py verdict work/formal-blind/packet.jsonl work/formal-blind/gpu-review
python gpu_review.py issue work/formal-blind/packet.jsonl work/formal-blind/issues
```

For the exploratory length diagnostic, `length_sample.py work` selects 100 dev question IDs by hashing. It takes up to five from each database, then fills any vacancies by the same hash order. Use `long_infer.py` with the same arguments as `infer.py` and the `spider-long` input and output directories. Also run `infer.py` on the same 100 input IDs with identical four-question batches, writing to `spider-short-base` and `spider-short-lora`. Run the official scorer on both budgets. The released [inference receipts](results/inference-receipts.json) include each input digest and the time of the first and last saved answer. This post hoc sensitivity check addresses the high baseline truncation rate. The primary questions and thresholds were fixed before the run. To verify all six regenerated input files by content across operating systems, run `python verify_inputs.py work`.
