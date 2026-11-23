# DataLens AI business plan

This course proposal explores a subscription analytics assistant for business teams. A sales manager could ask “Which five products generated the most revenue in East China last month?” The proposed service would generate SQL, query the company's database, and return a chart and a written explanation.

## 1. Executive summary

The intended customers are Chinese small and medium-sized enterprises (SMEs) that use ERP, CRM or financial systems and have limited access to analysts. The proposal assumes a market of more than 52 million SMEs. Three features distinguish the product: a Qwen3.5-0.8B model fine-tuned on 2,000 selected DataMind-12K examples, a natural-language interface for people unfamiliar with SQL or Python, and private deployment within the customer's network.

The proposed angel round is RMB 5 million. The high-level allocation is 40% for development, 30% for marketing and 30% for staff and operations. The plan targets break-even in month 18.

## 2. Project history

| Milestone | Status in the course project |
| --- | --- |
| Study and implement three data selection methods | Completed in Q1.1–Q1.2 |
| Fine-tune Qwen3.5-0.8B | Completed in Q1.3. Historical run reported a final loss of 0.098 |
| Build the local conversational demo | Completed in Q1.4 |
| Develop the MVP | Planned for months 1–6 |
| Test with early users | Planned for months 7–9 |
| Launch | Planned for months 10–12 |

The selection pipeline reduced 11,707 conversations to 2,000 training examples using complexity, quality and diversity. The local demo answers questions about SQL, Python and statistics. The following product, market and financial sections describe the proposal.

## 3. Product and services

The service would translate questions into SQL, execute queries and aggregate statistics, flag anomalies, and export chart-based HTML or PDF reports. Follow-up questions would allow users to drill down or compare results. Plain-language explanations would cover questions such as “What does a p-value of 0.03 mean?”

The design draws on *A Survey on Data Selection for Language Models*. Complexity filtering retains multi-table joins, nested queries and window functions. Quality filtering aims to reduce examples with invalid SQL or contradictory reasoning. Diversity selection broadens coverage across finance, sales, operations and HR. The DataMind-12K reasoning format informs the proposed explanations. Private deployment is described in the [architecture](Q2_architecture.md).

The proposal identifies three potential competitive advantages: the selection pipeline, the accumulation of domain examples as customers use the product, and connectors to ERP, CRM and finance software.

## 4. Customers and competitors

The original plan uses the following market assumptions: 52 million Chinese SMEs, a Chinese BI market of approximately RMB 12 billion in 2025, global NLP growth of about 25% per year in 2025–2030, and annual growth above 40% in AI-native SaaS. It cites a Gartner forecast that more than 50% of BI queries would begin in natural language by 2028.

| Segment | Use case | Distribution |
| --- | --- | --- |
| Online retail | Sales, inventory turnover and repeat purchases | E-commerce SaaS integrations |
| Financial services | Risk reports, compliance audits and performance | Partners |
| Manufacturing | Production efficiency, quality and supply chains | Trade shows and direct sales |
| Restaurant chains | Sales per unit of floor area, foot traffic and costs | Restaurant SaaS integrations |

The course comparison describes ThoughtSpot as an established enterprise product with fees above USD 50,000 per year and targets roughly one twentieth of that price. Tableau GPT offers an established BI ecosystem with a higher learning cost. AskYourDatabase focuses on SQL generation. ERNIE Bot and Qwen address general language tasks. In-house development offers control and requires specialist staff. The proposed SME offering emphasizes low prices, guided reporting and a one-day deployment target.

## 5. Pricing and distribution

| Plan | Monthly price | Proposed features |
| --- | ---: | --- |
| Starter | RMB 499 | One database, five users, basic analysis |
| Professional | RMB 1,999 | Five databases, 20 users, advanced reports and export |
| Enterprise | RMB 4,999 | Unlimited databases, private deployment, SSO and an SLA |

The proposal compares the RMB 5,988 annual Starter subscription with assumed BI costs of RMB 10,000–50,000 per user per year and analyst salaries of RMB 150,000–300,000 per year. Its illustrative cost comparison puts the subscription at 20% of an analyst's monthly salary.

Acquisition channels include a 14-day self-service trial, tutorials and case studies, a user community, and integrations with Kingdee, Yonyou, DingTalk and Feishu. Founders would sell to pilot customers, the website would handle smaller subscriptions, and ERP or BI resellers would receive a share of sales.

## 6. Operations

The design combines vLLM and the fine-tuned model for inference, Ray Train and PyTorch for training, PostgreSQL and ClickHouse for storage, Redis for sessions and frequent queries, Kafka for background work, and Nginx and Kong at the gateway. Docker and Kubernetes handle deployment. Prometheus, Grafana and the ELK stack provide monitoring. The architecture targets 100,000 concurrent connections with queued inference.

Quality monitoring would track SQL syntax and execution success, compare model updates on a small share of traffic, and collect feedback on generated answers.

## 7. Team and milestones

The proposed CEO owns product, fundraising and partnerships. The CTO leads model training, distributed systems and development. The COO handles SaaS operations and customer success. A sales lead would build direct and reseller channels.

| Period | Staffing or business target |
| --- | --- |
| Months 1–3 | Founder and two engineers build the MVP |
| Months 4–6 | Hire three people across frontend, backend and operations |
| Months 7–12 | Grow to 10–15 staff |
| Months 13–18 | Grow to 25–30 staff |
| Month 12 | 50 paying customers and RMB 50,000 monthly recurring revenue |
| Month 24 | 500+ paying customers and RMB 500,000 monthly recurring revenue |
| Month 48 | Target annual revenue above RMB 50 million and consider a Series A |

## 8. Financial assumptions and projections

The plan assumes RMB 1,200 in monthly revenue per customer, a 24-month customer lifetime and an 85% gross margin at scale. It models customer acquisition cost falling from RMB 3,000 to RMB 1,500 and monthly churn falling from 5% to 3%.

All monetary entries in the following table are in **RMB 10,000**.

| Metric | Year 1 | Year 2 | Year 3 |
| --- | ---: | ---: | ---: |
| Paying customers (count) | 50 | 500 | 2,000 |
| Revenue | 72 | 720 | 2,880 |
| Operating costs | 50 | 200 | 500 |
| Gross profit | 22 | 520 | 2,380 |
| Personnel | 120 | 300 | 600 |
| Marketing | 80 | 200 | 400 |
| Other expenses | 30 | 80 | 150 |
| Net profit | -208 | -60 | +1,230 |
| Financing | 500 (angel round) | — | Optional Series A |

The detailed angel budget allocates RMB 2 million (40%) to development, RMB 1.5 million (30%) to marketing, RMB 1 million (20%) to compensation and RMB 500,000 (10%) to operations and other costs.

## 9. Risks and exit scenarios

The plan pairs five risks with proposed responses: continued domain specialization as general models improve, a focus on SME customers if major vendors offer free products, private deployment and encryption for data security, employee equity to recruit specialists, and a free entry tier if conversion is weak.

The illustrative investment scenario assumes a 5–10× return by a year-three Series A. Exit possibilities include acquisition by a BI or cloud vendor, a STAR Market or Hong Kong listing if annual revenue exceeds RMB 100 million with sustained profits, or a founder buyback when cash flow permits.

## Project methods and attribution

The Q1 methods behind the proposal are complexity-based filtering for advanced queries, CLEAR-inspired quality filtering for correctness, and DEITA-inspired diversity selection for domain coverage.

The original course document was drafted with assistance from Claude (Anthropic). Its prompts requested a business plan for an enterprise analytics assistant, a natural-language-to-SQL competitor analysis, an explanation of the Q1 selection methods as a technical advantage, and a three-year SaaS financial model.

