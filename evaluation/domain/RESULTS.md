# English checkpoint results

| Endpoint | Raw Qwen | Final LoRA | Gain in pp [97.5% CI] | Gains / regressions |
| --- | ---: | ---: | ---: | ---: |
| A · Business scenario pair | 0/400 (0.00%) | 1/400 (0.25%) | +0.25 [+0.00, +1.00] | 1 / 0 |
| B · Business SQL | 29/480 (6.04%) | 88/480 (18.33%) | +12.29 [+8.75, +16.04] | 77 / 18 |
| External · Spider dev | 53/1034 (5.13%) | 208/1034 (20.12%) | +14.99 [+10.73, +20.03] | 180 / 25 |

Business decisions **did not meet both criteria**. Business SQL **met both criteria**. The registered thresholds were a gain of at least ten percentage points and a positive lower confidence bound. A gain or regression is the same question changing from fail to pass or pass to fail.

### Business decisions

| Arm | Raw Qwen | Final LoRA |
| --- | ---: | ---: |
| Request the necessary input | 13/400 | 11/400 |
| Calculate with all inputs | 0/400 | 18/400 |

The exploratory classifier agreed with direct masked review on 25/40 answers, including 11/23 complete-input answers. The table below counts classifier flags. Agreement was too low to draw conclusions about the prevalence of either error.

| Exploratory error label | Raw Qwen flags | Final LoRA flags |
| --- | ---: | ---: |
| Unsupported numerical result on a missing-input prompt | 399/400 | 383/400 |
| Unnecessary request on a complete-input prompt | 360/400 | 20/400 |

Blind agreement before adjudication was 1536/1600 (96.0%), Cohen’s κ = 0.44. Codex used numeric and request-language screening with direct review of candidate answers. The second AI reviewer was a local Qwen3-4B model. Codex resolved conflicting judgments against the original prompt before the identity key was opened. The answer-level error indicators use separate machine-coded rules and a local AI classifier. They agreed with a direct masked review on 25/40 hash-selected answers. These rates are exploratory. [Calibration and review](REVIEW.md) · [Diagnostic audit](results/issue-audit.json)

| Task family (50 scenarios each) | Raw pairs passed | LoRA pairs passed |
| --- | ---: | ---: |
| change | 0 | 0 |
| coverage | 0 | 0 |
| distribution | 0 | 0 |
| duration | 0 | 1 |
| finance | 0 | 0 |
| rank | 0 | 0 |
| rate | 0 | 0 |
| weighted | 0 | 0 |

Using only the first reviewer's votes gives 0 raw and 1 tuned passes out of 400 pairs. Using only the second gives 1 and 3. Both fall below the prespecified improvement threshold. Most answers failed under both reviews. [Scores by reviewer](results/reviewer-sensitivity.json)

[All scenarios](results/business-scenarios.csv) · [Both answers and verdicts](results/business-answers.jsonl)

### Business SQL

| Task family (80 queries each) | Raw Qwen | Final LoRA |
| --- | ---: | ---: |
| aggregate | 0 | 4 |
| date | 0 | 27 |
| distinct | 6 | 7 |
| filter | 8 | 44 |
| join | 15 | 6 |
| zero | 0 | 0 |

Individual task families are exploratory. Each database contributed one query per family. The 80 schemas exercise 19 recurring SQL structures. [All answers](results/confirm-b-answers.jsonl) · [All grades](results/confirm-b-grades.csv)

Across 480 queries, 71 raw answers and 209 tuned answers could execute on all three fixtures. Of 45 questions where both queries executed, raw Qwen returned the right rows on 19 and LoRA on 23. This post hoc subset is selected on model output. [Execution diagnostic](results/sql-execution-diagnostic.json)

Raw Qwen reached the 128-token cap on 480/480 business SQL answers, compared with 1/480 for the tuned model. A correct extracted statement could still pass if trailing prose was truncated. Shorter, more directly executable output contributes to the gain.

### What changes with a longer answer budget?

The original 128-token run used the entire Spider dev split. A post hoc diagnostic selected 100 of those same questions by a fixed hash, with representation from all 20 databases. Both checkpoints reran the selected prompts at both 128 and 512 output tokens in the same order and batches of four. Decoding settings and the official execution scorer otherwise matched. Every 128-token response was an exact text prefix of the corresponding 512-token response for both models. The scorer also passed a gold-query control on each of the 20 databases.

| Same 100 Spider questions | Raw Qwen | Final LoRA |
| --- | ---: | ---: |
| 128 output tokens | 6/100 | 22/100 |
| 512 output tokens | 9/100 | 22/100 |

In the full 128-token run, 1031 raw and 0 tuned answers reached the cap. In the 512-token diagnostic the corresponding counts were 9 and 0 of 100. Length-limited answers can still pass when they contain a complete correct query. [Full public benchmark](results/spider-grades.csv) · [Matched 128-token answers](results/spider-short-answers.jsonl) · [512-token answers](results/spider-long-answers.jsonl)

### Examples selected by ID

**First improved business pair · `a-formal-019`**

**Missing prompt**

> The reporting worksheet tracks "Accrued rent". The review closed on 2019-12-31. How many calendar days elapsed from opening to closing?

Raw Qwen

> To calculate how many **calendar days** elapsed between two dates, we need to subtract the start date from the end date. Since you mentioned the review closed on **December 31, 2018**, this is a specific historical date (not a future date), so we can use standard date arithmetic.
>
> ### Step-by-step Calculation:
>
> 1.  **Identify the Start Date:** December 31, **2018**.
>     *   In a 365-day year, this is exactly one full year.
>     *   However, since it is the last day of the year

Final LoRA

> Please share the start date in YYYY-MM-DD format.

**Complete prompt**

> The reporting worksheet tracks "Accrued rent". The review closed on 2019-12-31. How many calendar days elapsed from opening to closing? The review opened on 2018-12-31.

Raw Qwen

> To calculate how many **calendar days** elapsed between two dates, we need to subtract the start date from the end date. Since you provided both dates as strings (e.g., `2019`), I will assume they are in **YYYY-MM-DD format**.
>
> ### Step-by-step Calculation:
>
> 1.  **Identify the Start Date:**
>     *   Opening: 2016-12-01 (Note: You mentioned "opening on 2024-12-25" in your prompt, but then asked about a review closed on 12/31

Final LoRA

> It was 365 calendar days.

**First improved business SQL query · `db-aircraft-2`**

> How many different known Winning_Pilot values are in match among rows with Location equal to 'v1'? The declared relationship is match.Winning_Pilot to pilot.Pilot_Id.

Raw Qwen

> To find the number of unique `Winning_Pilot` values where `Location` equals `'v1'`, we need to join the tables on the foreign key relationship (`match.Winning_Pilot` → `pilot.Pilot_Id`) and filter for the specific location.
>
> Here is the SQL query:
>
> ```sql
> SELECT COUNT(DISTINCT m.Winning_Pilot)
> FROM match m
> JOIN pilot p ON m.Winning_P Pilot_Id = p.Pilot_Id
> WHERE m.Location = 'v1';
> ```
>
> **Explanation:**
> *   **`COUNT(DISTINCT ...)`**: Counts the number

Final LoRA

> SELECT COUNT(DISTINCT winning_pilot) FROM match WHERE location='v1';

### Regression index

Business pairs (0): None

Business SQL (18): `db-cinema-2`, `db-college_1-2`, `db-college_2-2`, `db-college_2-4`, `db-cre_Drama_Workshop_Groups-4`, `db-csu_1-4`, `db-customers_and_products_contacts-4`, `db-department_store-4`, `db-insurance_and_eClaims-4`, `db-insurance_fnol-4`, `db-local_govt_and_lot-2`, `db-network_2-1`, `db-news_report-4`, `db-pilot_record-4`, `db-program_share-4`, `db-railway-4`, `db-school_player-4`, `db-twitter_1-4`

Spider dev (25): `spider-0001`, `spider-0209`, `spider-0224`, `spider-0252`, `spider-0254`, `spider-0305`, `spider-0306`, `spider-0307`, `spider-0308`, `spider-0323`, `spider-0324`, `spider-0339`, `spider-0355`, `spider-0409`, `spider-0421`, `spider-0518`, `spider-0577`, `spider-0902`, `spider-0906`, `spider-0907`, `spider-0913`, `spider-0952`, `spider-0953`, `spider-0979`, `spider-1021`

Only the raw and final checkpoints met the file-identity requirement for this comparison. The intermediate stage has no score on these new sets. [Checkpoint provenance](CHECKPOINTS.md) · [Protocol](PROTOCOL.md) · [Reproduction guide](README.md)
