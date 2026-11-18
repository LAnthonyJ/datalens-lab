# 豆包 PPT 生成 Prompt

将以下内容直接复制给豆包即可：

---

请帮我生成一份 PPT，要求如下：

**风格**：简约专业，白色背景，深蓝色标题，每页内容精炼不堆砌，适合技术答辩。

**页数**：14 页

**语言**：中文为主，技术术语保留英文

---

以下是每页的具体内容和排版要求：

**第 1 页：封面**
- 标题：Project 2: Data Agent System & LLM Startup Business Plan
- 副标题：大数据软件与应用 | 2026 年 6 月
- 底部：演讲者姓名 + 学号

**第 2 页：项目总览**
- 标题：项目总览
- 内容要点：
  - Q1: Data Agent System (10pts) — 数据筛选 → 模型微调 → Web Demo
  - Q2: Startup Business Plan (6pts) — 商业计划书 + 系统架构设计
  - 核心逻辑链：数据筛选 → 微调 Qwen3.5-0.8B → Web Demo → 创业落地

**第 3 页：三种数据筛选方法**
- 标题：Q1.1 三种数据筛选方法
- 用三列表格展示：

| 方法 | 核心思想 | 解决的问题 |
|------|---------|-----------|
| Complexity Filtering | 保留复杂 SQL、多表 JOIN、嵌套查询 | 模型能处理真实企业场景 |
| Quality Filtering (CLEAR) | 过滤 SQL 语法错误、逻辑矛盾 | 生产环境可靠性 |
| Diversity Selection (DEITA) | TF-IDF + 余弦相似度去重 | 覆盖多领域业务 |

- 底部备注：从 11,707 条数据中精选 2,000 条训练 + 500 条验证

**第 4 页：数据处理 Pipeline**
- 标题：Q1.2 数据处理 Pipeline
- 流程图：11,707 条 → 评分排序 → 过滤低质量 15% → 多样性去重 → 2,000 train + 500 val
- 关键数字（用卡片展示）：
  - Complexity: 0.35 → 0.52
  - Quality: 0.65 → 0.78
  - Train/Val 零重叠
  - 输出格式：Qwen Chat Template

**第 5 页：挑战 1 — NaN Loss**
- 标题：挑战 1：NaN Loss 问题
- 左侧：现象与排查
  - 训练开始后 loss 立即变成 NaN
  - 排查方向：数据格式 → tokenizer → chat template
- 右侧：根因与解决
  - 根因：Qwen2.5 用 "的助理" 标记，Qwen3.5 用 `<|im_start|>assistant\n`
  - 解决：字符级偏移映射精确定位 assistant token
  - 教训：不同版本模型模板差异大，不能套用

**第 6 页：挑战 2 — 过拟合**
- 标题：挑战 2：过拟合
- 问题：模型无论问什么都回复 `get_db_info()` 相关重复内容
- 原因：2,000 样本 × 3 epoch × lr=2e-4 × 无正则化 = 快速记忆而非泛化
- 解决（对比表）：

| 参数 | 修改前 | 修改后 |
|------|--------|--------|
| Epochs | 3 | 1 |
| Learning Rate | 2e-4 | 5e-5 |
| Weight Decay | 0 | 0.01 |

**第 7 页：挑战 3 — GPU 迁移与 OOM**
- 标题：挑战 3：GPU 环境迁移与 OOM
- 三种环境对比表：

| 环境 | GPU | 显存 | 问题 |
|------|-----|------|------|
| Colab | T4 | 15GB | OOM |
| AutoDL | RTX 5090 | 32GB | pip 网络、路径问题 |
| 学校服务器 | L20 | 48GB | 显存被其他进程占用 |

- OOM 解决方案（要点列表）：
  - 预 tokenization 在 Ray workers 外完成
  - batch_size: 8 → 4, gradient_accumulation: 4
  - 启用 gradient checkpointing
  - max_seq_length 限制为 1024

**第 8 页：挑战 4 — Qwen3.5 Chat Template**
- 标题：挑战 4：Qwen3.5 Chat Template 适配
- 问题：Qwen3.5 在助手回复中自动注入 `<think>...</think>` 推理块，简单截断无法定位 assistant token
- 解决方案（4 步）：
  1. `apply_chat_template(tokenize=False)` 获取渲染文本
  2. 搜索 `<|im_start|>assistant\n` 标记位置
  3. 建立字符→token 偏移映射
  4. 跳过异常样本避免 NaN

**第 9 页：Web Demo + 部署挑战**
- 标题：Q1.4 Web Demo 与部署挑战
- Demo 功能：自然语言输入 → 流式生成 → 交互式数据分析
- 遇到的挑战（三列）：
  - HuggingFace SSL 错误 → 改用 ModelScope 下载模型
  - Gradio 版本兼容 → 适配旧版 API
  - CPU 推理 30-90s 太慢 → 提供 GPU 选项
  - 输出格式异常 → System Prompt 引导

**第 10 页：最终训练结果**
- 标题：Q1.3 最终训练结果
- 指标卡片：
  - 最终 Loss: 0.098
  - 训练步数: 125
  - 有效 Batch Size: 16
  - 训练时间: ~8 分钟 (L20)
  - 模型: Qwen3.5-0.8B
- 底部放两张截图占位：
  - [训练终端输出截图]
  - [Demo 界面截图]

**第 11 页：Q2 — 创业计划与架构**
- 标题：Q2: DataLens AI 创业计划
- 产品定位：让非技术用户用自然语言查询企业数据
- Q1 数据筛选 → 创业技术壁垒（三行对照）：
  - Complexity → 处理复杂企业查询
  - Quality → SQL 正确率 >95%
  - Diversity → 覆盖全业务线
- 架构亮点：支持 10 万并发，vLLM + Kafka + Redis + K8s

**第 12 页：技术栈总览**
- 标题：技术栈总览
- 分层展示：
  - 数据层：DataMind-12K → 三阶段筛选 → Qwen 格式
  - 训练层：Ray Train + PyTorch + L20 GPU
  - 推理层：vLLM / Transformers + TextIteratorStreamer
  - 前端层：Gradio Chatbot
  - 架构层：Nginx → Kong → Kafka → vLLM → Redis → K8s

**第 13 页：关键收获**
- 标题：关键收获
- 5 条总结：
  1. 数据质量 > 数据数量：2,000 条精选数据 + 正确模板 = 可用模型
  2. 调试需要系统性：NaN loss → 排查模板 → 发现版本差异 → 修复
  3. 过拟合是综合问题：epoch + lr + weight_decay + 数据量
  4. 环境兼容性很重要：三种 GPU、两种下载源、Gradio 版本差异
  5. LLM 应用 = 模型 + 工程：训练、部署、架构、商业模式缺一不可

**第 14 页：谢谢！Q&A**
- 中央大字：谢谢！欢迎提问
- 底部：联系方式 + 交付物文件清单（data_selection.py, ray_train_exercise.ipynb, demo.py, Q2_business_plan.md, Q2_architecture.md, report.tex）

---

**额外要求**：
- 代码片段用等宽字体高亮
- 表格用交替行颜色（斑马条纹）
- 挑战类页面用"问题→根因→解决"三段式布局
- 每页标题加一个图标 emoji 点缀
- 前后章节之间加过渡标签（如"Part 1: Data Agent" / "Part 2: Startup Plan"）
