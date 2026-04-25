# 📦 AI-Powered Service Auditor: 电商人工客服全量质检中台

> **“从 5% 盲抽到 100% 审计，让每一份服务质量都具备可追溯的业务洞察。”**

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Framework](https://img.shields.io/badge/framework-Streamlit-FF4B4B)
![AI-Engine](https://img.shields.io/badge/AI-DeepSeek--V3-lightgrid)

本项目是一款基于 **“规则引擎 + 大模型 (LLM)”** 混合架构的智能质检系统。它专为电商环境设计，旨在解决传统人工质检中“成本高、覆盖低、标准主观”的痛点，实现客服对话的像素级合规审计与服务质量诊断。

---

## 🌟 核心特性 (Core Features)

### 1. 🧠 专家级管理洞察 (Expert Executive Summary)
这是系统的“大脑”。在批量质检完成后，系统会自动模拟资深主管视角，输出结构化的诊断报告：
* **核心问题诊断**：自动提炼团队表现最薄弱的业务环节。
* **团队风险预警**：针对高危违规（如泄露隐私、引导私下交易）进行红色预警。
* **管理优化建议**：提供可执行的培训方案和话术优化方向。

### 2. 🛡️ 五维全向评分模型 (5-Dimension Logic)
系统不再是笼统的评分，而是细化为五个具体的业务维度：
| 维度 | 考核重点 | 权重 |
| :--- | :--- | :--- |
| **对话逻辑合规性** | 语境连贯性、答非所问检测、逃避问题审计 | 重度 (-40) |
| **信息准确性** | 商品参数、订单状态、售后政策描述的精确度 | 重度 (-40) |
| **平台合规红线** | 隐私保护、言语规范、严禁引导站外交易 | **极高 (-50)** |
| **服务质量评价** | 同理心表达、响应效率、解决方案有效性 | 中度 (-20) |
| **销售转化能力** | 营销机会捕捉、主动推荐话术、下单引导技巧 | 轻度 (-10) |

### 3. 🔍 证据链闭环 (Evidence-Based Tracking)
* **原文追溯**：每个扣分项都配有 `evidence_quote`（证据原文），消除 AI 判定的“黑盒感”。
* **交互弹窗**：在仪表盘中点击得分，即可查看判定逻辑与改进建议，直接赋能客服申诉与培训。

### 4. 💰 单位经济模型 (Unit Economics)
* **Cost Manager**：实时监控 Token 消耗与美元转化，算清 AI 质检的每一分钱。
* **高并发任务调度**：基于 `ThreadPoolExecutor` 的异步架构，支持大规模数据集的稳定处理。

---

## 🛠️ 技术架构 (Tech Stack)

* **前端**：Streamlit (Dashboard & Data Visualization)
* **后端**：FastAPI (RESTful API), Python 3.10+
* **AI 引擎**：DeepSeek / OpenAI (Prompt Engineering & RAG)
* **数据层**：SQLite (WAL 模式确保多线程读写安全)
* **数据分析**：Pandas, Plotly (Radar Charts, Metrics)

---

## 📊 界面预览 (Quick Preview)

> **提示**：建议在此处上传你最新的系统截图。

* **指标看板**：展示平均得分、合格率、满分率及 Token 消耗。
* **诊断中心**：展示 AI 自动提炼的【专家诊断建议】卡片。
* **多维雷达图**：直观呈现团队在 5 个维度上的能力分布。

---

## ⚙️ 快速启动 (Quick Start)

###  使用教程
```bash
github上下载相关的代码文件
pip install -r requirements.txt

在根目录创建 .env 文件：
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=[https://api.deepseek.com/v1](https://api.deepseek.com/v1)
MAX_WORKERS=5
LOG_LEVEL=INFO
# 启动 Web 可视化看板
streamlit run app.py
