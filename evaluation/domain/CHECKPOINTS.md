# Scope of the checkpoint comparison

The raw Qwen and final merged candidate were verified by SHA-256 before inference. The final candidate includes both the English adaptation and the subsequent 600-example LoRA training. Their difference measures the combined training pipeline. It cannot isolate the contribution of the last LoRA stage.

The recorded starting weight for the last 600 examples is `b818266a964e846ef7741752f0bf977a9ac96ce8f453ce5db69560412ac70b96`. A local reconstruction from the preserved adapter and original base yielded a different file hash, `f691db8f8b26907387ddf872a7f5029464d37fc2127db7bcb4a0391902a1a1a6`. Different serialization can also change a file hash. The reconstruction was excluded from the three-way attribution comparison. The historic first-stage scores remain available on their original regression sets.

The local Gradio demo continues to use its documented demo checkpoint. The experimental candidate is a separate model. The English benchmark uses one training seed and one decoding configuration at each tested budget. The task families recur across different source tables and schemas.

### Pilot checks

The two model checkpoints each answered 80 business prompts and 48 SQL prompts. In the adjudicated pilot, the raw model passed both versions on 3 of 40 business scenarios and the final candidate on 1 of 40. On the 48 SQL prompts their execution scores were 1 and 3. These small pilot groups informed design and power planning and contribute no formal test cases.

The two independent AI judgments agreed on 141 of 160 masked pilot answers (88.1%). The first reviewer had previously encountered one of the pilot scenarios during setup. Model identities remained masked for the formal business review. [Pilot answers and adjudication](results/pilot-business-review.jsonl) · [Pilot model key](results/pilot-business-key.jsonl)
