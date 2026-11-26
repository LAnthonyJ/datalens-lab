# English domain evaluation protocol

**Primary comparison.** Raw Qwen3.5-0.8B against the fixed-learning-rate rank-16 LoRA candidate. The 20 historical clarification questions compare two already adapted checkpoints. The intermediate checkpoint is eligible only if its saved weight hash matches the recorded training start.

| Weights | SHA-256 |
| --- | --- |
| Raw Qwen | `04b1c301231dd422b8860db31311ab2721511346a32cb1e079c4c4e5f1fe4696` |
| Final merged LoRA | `42eb9a799888a582eae0c2135026e2f4eaf6e8ae89471ec2d12dab9f3c2ecef7` |
| Intermediate checkpoint required for attribution | `b818266a964e846ef7741752f0bf977a9ac96ce8f453ce5db69560412ac70b96` |

### A · Ask when information is missing, calculate when it is supplied

400 distinct company-report tables from the TAT-QA source pool supply the amounts, labels and dates for new worksheet scenarios. Only one table per scenario is used. The project writes its own questions. Planning weights, staffing policies and audit samples are stipulated assumptions. Eight categories have 50 scenarios each and six recurring calculation forms each. The 400 tables provide different contexts for those 48 forms. The sample covers English reporting worksheets. Companies and pretraining exposure cannot be identified reliably. [TAT-QA source](https://github.com/NExTplusplus/TAT-QA)

The assistant sees each version in a fresh conversation. Credit for the missing version requires a request for the particular withheld field, or equivalent information sufficient to answer. Generic requests, unsupported conclusions and unrelated blocking requirements fail. For the complete version, require the final result and interpretable units, with no contradiction or unnecessary request. Accept correct unit conversions and clear contextual units. For decimal results accept the larger of 0.005 worksheet units and 0.1% relative error. For ranks, years and integer counts require the exact integer. Explicitly equivalent fractions, expressions with a stated numerical result and appropriate verbal equivalents are acceptable. A matching number in copied inputs or intermediate work alone earns no credit.

Record the first answer from each model. Shuffle and blind the answers. Two AI reviewers score against the same recorded target independently. Review differences while IDs are still masked and retain disagreements and reasons. The numeric scanner flags discrepancies for inspection. The primary score is the number of scenarios for which both versions pass. Separately report missing/complete accuracy, unsupported numbers and unnecessary requests, with the respective answer-level denominators.

### B · Return the correct SQL result on unfamiliar schemas

80 distinct projections of Spider training-side schemas, disjoint from Spider dev, each with six original analytical queries. Only synthetic data are used. Questions cover filters, distinct counts, grouped aggregates, joins, date boundaries and retaining groups with no matches. Standard operators and the six families recur. The project checks source names and questions against its own training history. It cannot establish that the foundation model never saw Spider. [Spider data and attribution](https://yale-lily.github.io/spider)

Verify reference SQL against separately calculated expected rows on the first fixture. Score the same generated query against the reference on all three fixtures. Fixtures vary nulls, duplicates, unmatched keys and date boundaries. Preserve duplicate rows. A single closed SQL block or a bare statement is eligible. Queries that are missing, invalid, exceed execution limits or yield the wrong relation fail. Record truncation separately, including truncated prose following a complete, correct query.

### External cross-check · Spider 1.0 dev

All 1,034 questions on 20 databases. Use the authors' test suites and evaluator at `e97acc546ecbee8fa27fa8dbf025ef61493a876c`, with original constants, default DISTINCT handling and read-only SQLite connections. Compare complete test-suite denotations. Keep this result separate from the two confirmatory hypotheses. [Official evaluator](https://github.com/taoyds/test-suite-sql-eval) · [Test-suite methodology](https://aclanthology.org/2020.emnlp-main.29/)

### Inference, uncertainty and reporting

Both checkpoints share the tokenizer, template, system instruction, GPU precision, greedy generation, 128-token response budget, repetition penalty 1.08, no-repeat five-grams and 4,096-token prompt cap. All question IDs stay in the denominator, including input limits, empty answers and truncated answers. The length budget is the one used for this demo comparison and can penalize verbose answers.

Each primary endpoint requires an observed improvement of at least ten percentage points and a positive lower bound on a two-sided 97.5% paired percentile-bootstrap interval. Use 20,000 resamples, seed 20261126, resampling scenarios for A and whole six-question databases for B. Report both directions of change. Category and question-form summaries are exploratory. Select the first improved case in ID order and list all regressions. Publish negative findings under the same rules.

Power planning uses the standard deviation of paired cluster differences in the separate pilot. For conservatism, use at least 0.55 for business pairs and 0.25 for database scores. At 400 and 80 units, approximate two-sided power for rejecting zero when the true difference is ten percentage points is 92% and 91%, respectively, using these floors. The additional observed-size threshold also applies when deciding the wording of a claim. Pilot results are excluded from the formal scores.
