# Business-answer review

Each reviewer saw an anonymous, randomly ordered packet and the criterion for each question. Codex used numerical checks and request-language screening to identify candidate answers for direct assessment. The first verdict file was sealed before comparing decisions with the local Qwen3-4B reviewer. Length and writing style remained visible.

The local reviewer's model blob was `sha256:3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f`. The single-verdict format passed all eight known-answer controls. On the separate pilot, the Vulkan and CPU implementations agreed on 155 of 160 answers, above the advance threshold of 152. The complete second formal review used Vulkan. Of 739 formal answers independently scored on both processors, 734 had the same judgment.

The two independent formal reviewers agreed on 1536/1600 answers before adjudication. Codex resolved the differences with model names masked. The released files preserve the first verdicts, final decisions and rationales. [First verdicts](results/business-reviewer1.jsonl) · [Adjudication](results/business-adjudication.jsonl) · [Reviewer sensitivity](results/reviewer-sensitivity.json)

Secondary error labels use rules and a separate local AI classification. All 16 calibration examples passed. On 40 masked study answers selected by a fixed hash of the anonymous ID, 25 of the labels matched direct Codex review. Treat the reported error frequencies as estimates. [Controls](results/issue-controls.json) · [Audit](results/issue-audit.json)
