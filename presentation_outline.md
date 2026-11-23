# Project 2 presentation outline

A 14-slide course presentation for a ten-minute technical defense, focused on the five engineering challenges.

## Slide 1. Project 2: Data Agent System and LLM Startup Business Plan (20 s)

Open with the course title, Big Data Software and Applications, June 2026, the speaker's name and student ID.

## Slide 2. Project overview (30 s)

Q1 (10 points) moves from data selection to fine-tuning Qwen3.5-0.8B and a web demo. Q2 (6 points) uses the experiment as the basis for a business plan and a deployment architecture.

## Slide 3. Three selection methods (40 s)

Present a three-column table of method, rationale and use case. Complexity filtering favors multi-table joins and nested SQL. CLEAR-inspired quality filtering reduces malformed and contradictory examples. DEITA-inspired diversity selection uses TF-IDF cosine similarity. Rank examples by complexity × quality and use a similarity threshold of 0.85.

## Slide 4. Processing DataMind-12K (30 s)

Diagram the 11,707 conversations, ranking, the 15th-percentile quality cutoff and diversity selection. Show 2,000 training and 500 validation examples with zero shared IDs. Mean complexity rises from 0.35 to 0.52 and mean quality from 0.65 to 0.78. Convert messages to the trajectory format used by the Qwen chat template.

## Slide 5. Diagnosing NaN loss (1 min)

Training loss immediately became NaN. Inspect the dataset, tokenizer and rendered conversation in order. The preprocessing code looked for an assistant marker from a different model version. Render a sample with apply_chat_template, locate the Qwen3.5 assistant marker and skip examples without trainable assistant tokens.

## Slide 6. Overfitting on 2,000 examples (1 min)

The fine-tuned model repeatedly returned get_db_info() regardless of the question. The base-only check produced normal replies. Compare three epochs with one, learning rates of 2e-4 and 5e-5, and weight decay of 0 and 0.01. Explain how these changes reduce memorization.

## Slide 7. GPU migration and out-of-memory errors (1 min)

Compare Colab's T4 (15 GB VRAM, 12 GB host RAM), AutoDL's RTX 5090 (32 GB, package download and path issues), and the university L20 (48 GB, with 7.78 GB in use by another process). Tokenize outside Ray workers, reduce batch size from eight to four, accumulate four batches, enable gradient checkpointing and cap sequences at 1,024 tokens.

## Slide 8. Finding the assistant tokens (40 s)

Qwen3.5 can include thinking blocks. Render with tokenizer.apply_chat_template(tokenize=False), locate the <|im_start|>assistant marker followed by a newline and map character offsets to tokens with offset_mapping. Compute loss over assistant tokens and skip examples without a usable span.

## Slide 9. Web demo and compatibility (1 min)

Show streaming responses to five preset prompts. The historical demo used repetition_penalty=1.2 and no_repeat_ngram_size=4. ModelScope provided a download fallback after Hugging Face mirror SSL errors. The demo adapted to the older Gradio API, added a system prompt and offered --cpu-only. Historical timing estimates were 30–90 seconds per CPU response and 2–5 seconds on GPU.

## Slide 10. Training results (30 s)

Insert terminal output and a demo screenshot. The original L20 run reported 125 steps, an effective batch size of 16, about eight minutes of training, final loss of 0.098 and roughly 3 GB for the Qwen3.5-0.8B model.

## Slide 11. DataLens AI business proposal (40 s)

Connect the three selection methods to complex enterprise queries, a proposed SQL correctness target above 95%, and coverage across finance, sales, operations and HR. The architecture targets 100,000 concurrent connections using vLLM, Kafka, Redis and Kubernetes, with an estimated monthly cost of RMB 60,000.

## Slide 12. Technology stack (30 s)

Show the layers: DataMind-12K and the Qwen format for data, Ray Train and PyTorch on the L20 for training, vLLM or Transformers with TextIteratorStreamer for serving, Gradio for chat, and Nginx, Kong, Kafka, vLLM, Redis and Kubernetes in the proposed deployment.

## Slide 13. Lessons learned (30 s)

Cover data selection and correct templates, systematic debugging of NaN loss, interactions between sample count and optimization settings, compatibility across hardware and libraries, and the engineering and business decisions that follow model training.

## Slide 14. Questions and deliverables (20 s)

Close with contact details and links to data_selection.py, prepare_qwen_data.py, raytrain.ipynb, demo.py, Q2_business_plan.md, Q2_architecture.md, Q2_roadshow_outline.md and report.tex.

The original outline was drafted with assistance from Claude (Anthropic).
