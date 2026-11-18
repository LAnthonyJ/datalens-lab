# Project 2 汇报 PPT 大纲：Data Agent 系统与创业计划

> 时长：10 分钟 | 幻灯片：14 页 | 重点：挑战 & 解决方案

---

## Slide 1: 封面 (20s)

**Project 2: Data Agent System & LLM Startup Business Plan**

大数据软件与应用 | 2026 年 6 月

演讲者：[姓名] | 学号：XXXXXXXX

---

## Slide 2: 项目总览 (30s)

**两大模块：**

| 模块 | 内容 | 分值 |
|------|------|------|
| Q1: Data Agent System | 数据筛选 → 模型微调 → Web Demo | 10 pts |
| Q2: Startup Plan | 商业计划书 + 系统架构设计 | 6 pts |

**核心逻辑链：**

```
数据筛选 (Q1.1-Q1.2) → 微调 Qwen3.5-0.8B (Q1.3) → Web Demo (Q1.4) → 创业落地 (Q2)
```

---

## Slide 3: Q1.1 三种数据筛选方法 (40s)

**目标**：从 11,707 条 DataMind-12K 中精选 2,000 条高质量训练数据

| 方法 | 核心思想 | 解决的问题 |
|------|---------|-----------|
| Complexity Filtering | 保留复杂 SQL、多表 JOIN、嵌套查询 | 模型能处理真实企业场景 |
| Quality Filtering (CLEAR) | 过滤 SQL 语法错误、逻辑矛盾样本 | 生产环境可靠性 |
| Diversity Selection (DEITA) | TF-IDF + 余弦相似度去重 | 覆盖财务/销售/运营/HR 多领域 |

**评分公式**：$C(s) \times Q(s)$，相似度阈值 0.85 去重

---

## Slide 4: Q1.2 数据处理 Pipeline (30s)

```
11,707 条 → 评分排序 → 过滤低质量 (15%) → 多样性去重 → 2,000 train + 500 val
```

**关键数字**：
- 训练集 Complexity 从 0.35 → 0.52
- 训练集 Quality 从 0.65 → 0.78
- Train/Val 零重叠
- 输出格式：Qwen Chat Template (`messages` → `trajectory`)

---

## Slide 5: 挑战 1 — NaN Loss 问题 (1min)

**现象**：训练开始后 loss 立即变成 NaN

**排查过程**：
1. 检查数据格式 → 正常
2. 检查 tokenizer → 发现问题：Qwen2.5 用 `"的助理"` 作为 assistant 标记，Qwen3.5 用 `<|im_start|>assistant\n`
3. 使用 `apply_chat_template` 渲染一条样本，确认 Qwen3.5 的真正格式

**根因**：预处理函数用了 Qwen2.5 的模板去匹配 Qwen3.5 的输出

**解决**：重写 `preprocess_dataset`，使用 `<|im_start|>assistant\n` 字符级偏移映射定位 assistant token span，并自动跳过无有效 assistant 的样本

**教训**：不同版本模型 chat template 差异很大，不能直接套用

---

## Slide 6: 挑战 2 — 过拟合 (1min)

**现象**：微调后模型无论问什么都回复 `get_db_info()` 相关重复内容

**分析**：
- 仅 2,000 条训练数据
- 初始设置：3 epochs, lr=2e-4, 无正则化
- 模型在少量数据上快速记忆而非泛化

**解决**：

| 参数 | 修改前 | 修改后 |
|------|--------|--------|
| Epochs | 3 | 1 |
| Learning Rate | 2e-4 | 5e-5 |
| Weight Decay | 0 | 0.01 |

**验证**：base-only 模式回复正常 → 确认是微调阶段过拟合

---

## Slide 7: 挑战 3 — GPU 环境迁移 & OOM (1min)

**经历了三种 GPU 环境**：

| 环境 | GPU | 显存 | 遇到的问题 |
|------|-----|------|-----------|
| Colab | T4 | 15GB | OOM（12GB 系统 RAM 不足） |
| AutoDL | RTX 5090 | 32GB | pip 网络卡顿、路径不兼容 |
| 学校服务器 | NVIDIA L20 | 48GB | 另一进程占用 7.78GB 显存 |

**OOM 解决方案**：
- 预 tokenization 在 Ray workers 外完成（减少 Ray object store 压力）
- batch_size 8→4, gradient_accumulation=4
- 启用 `gradient_checkpointing`
- 限制 `max_seq_length=1024`

**最终**：L20 上 125 步 ~8 分钟完成训练，loss=0.098

---

## Slide 8: 挑战 4 — Qwen3.5 Chat Template 适配 (40s)

**Qwen3.5 的特殊性**：
- 助手回复中自动注入 `<think>...</think>` 推理块
- 不能用简单截断去找 assistant token 位置

**解决方案**：
1. 用 `tokenizer.apply_chat_template(tokenize=False)` 获取渲染文本
2. 在文本中搜索 `<|im_start|>assistant\n` 标记位置
3. 建字符→token 偏移映射 (`offset_mapping`)
4. 精确找到 assistant token 的起止位置用于 loss 计算
5. 跳过找不到 assistant 的异常样本

---

## Slide 9: Q1.4 Web Demo + 挑战 5 (1min)

**Demo 功能**：
- 自然语言输入 → 流式生成回复
- 5 个预设数据分析示例
- 防重复：`repetition_penalty=1.2`, `no_repeat_ngram_size=4`

**挑战 5：模型下载 & Gradio 兼容性**

| 问题 | 解决 |
|------|------|
| HuggingFace/HF-Mirror SSL 错误 | 改用 ModelScope (`modelscope.snapshot_download`) |
| Gradio 版本 `type` 参数不支持 | 适配旧版 API 格式 |
| CPU 推理 30-90s/回复太慢 | 说明可在 GPU 上 2-5s，提供 `--cpu-only` 选项 |
| 模型输出格式异常 | 添加 System Prompt 引导自然语言回复 |

---

## Slide 10: 最终训练结果 (30s)

**【截图：训练终端输出】**

| 指标 | 数值 |
|------|------|
| 最终 Loss | 0.098 |
| 训练步数 | 125 |
| 有效 Batch Size | 16 |
| 训练时间 | ~8 分钟 (L20) |
| 模型大小 | Qwen3.5-0.8B (~3GB) |

**【截图：Demo 界面】**

---

## Slide 11: Q2 — 创业计划 & 架构设计 (40s)

**DataLens AI**：用自然语言查询企业数据的 SaaS 平台

**Q1 数据筛选 → 创业技术壁垒**：

| 筛选方法 | 商业价值 |
|---------|---------|
| Complexity Filtering | 处理复杂企业查询（多表 JOIN） |
| Quality Filtering | SQL 正确率 >95%，生产可用 |
| Diversity Selection | 覆盖财务/销售/运营/HR 全业务 |

**系统架构亮点**：支持 10 万并发，vLLM + Kafka + Redis + K8s，月成本 ~¥6 万

---

## Slide 12: 技术栈总结 (30s)

```
数据层：DataMind-12K → 三阶段筛选 → Qwen 格式
训练层：Ray Train + PyTorch + L20 GPU
推理层：vLLM / Transformers + TextIteratorStreamer
前端层：Gradio Chatbot
架构层：Nginx → Kong → Kafka → vLLM → Redis → K8s
```

---

## Slide 13: 关键收获 (30s)

1. **数据质量 > 数据数量**：2,000 条精选数据 + 正确模板 = 可用模型
2. **调试需要系统性**：NaN loss → 排查模板格式 → 发现版本差异 → 修复
3. **过拟合不仅是 epoch 问题**：lr + weight_decay + 数据量综合作用
4. **环境兼容性很重要**：三种 GPU 环境、两种模型下载源、Gradio 版本差异
5. **LLM 应用 = 模型 + 工程**：训练只是起点，部署、架构、商业模式缺一不可

---

## Slide 14: 谢谢！Q&A (20s)

**交付物清单**：

| 类别 | 文件 |
|------|------|
| 数据筛选 | `data_selection.py`, `prepare_qwen_data.py` |
| 模型训练 | `ray_train_exercise.ipynb` |
| Web Demo | `demo.py` |
| 商业计划 | `Q2_business_plan.md` |
| 架构设计 | `Q2_architecture.md` |
| 路演 PPT | `Q2_roadshow_outline.md` |
| 实验报告 | `report.tex` |

联系方式：[邮箱] | GitHub：[链接]

---

*本文档使用 Claude (Anthropic) 辅助撰写。*
