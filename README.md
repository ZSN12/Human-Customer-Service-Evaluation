# 📦 AI-Powered Service Auditor: 电商人工客服全量质检中台

> **“从 5% 盲抽到 100% 审计，让每一份服务质量都具备可追溯的业务洞察。”**

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![Framework](https://img.shields.io/badge/framework-Streamlit-FF4B4B)
![AI-Engine](https://img.shields.io/badge/AI-DeepSeek--V3-lightgrid)

本项目是一款基于 **“规则引擎 + 大模型 (LLM)”** 混合架构的智能质检系统。专为跨境/本土电商环境设计，旨在解决传统人工质检中“成本高、覆盖低、标准主观”的痛点，实现客服对话的像素级合规审计与服务质量量化诊断。

---

## 🌟 核心产品特性 (Core Features)

### 1. 🧠 专家级管理洞察 (Expert Executive Summary)
系统在批量质检完成后，会自动模拟资深主管视角，输出结构化的诊断报告：
* **核心问题诊断**：自动提炼团队表现最薄弱的业务环节。
* **团队风险预警**：针对高危违规（如言语辱骂、引导私下交易）进行红色预警。
* **管理优化建议**：提供可落地的培训方案和话术优化方向。

### 2. 🛡️ 五维量化评分模型 (5-Dimension Scoring Logic)
摒弃传统笼统的主观评价，将感性服务拆解为五个机器可计算的客观维度：

| 维度 | 考核重点 | 权重（基础扣分） |
| :--- | :--- | :--- |
| **对话逻辑合规性** | 语境连贯性、答非所问检测、逃避问题审计 | 重度 (-40) |
| **信息准确性** | 商品参数、订单状态、售后政策描述的精确度 | 重度 (-40) |
| **平台合规红线** | 隐私保护、言语规范、严禁引导站外交易 | **极高 (-50)** |
| **服务质量评价** | 同理心表达、响应效率、解决方案有效性 | 中度 (-20) |
| **销售转化能力** | 营销机会捕捉、主动推荐话术、下单引导技巧 | 轻度 (-10) |

### 3. 💰 极致的成本管控与高可用 (ROI & High Availability)
* **智能降本**：内置“语义聚类与长文本动态截断”预处理策略，精准剔除无效 Token，**综合调用成本下降约 70%**。
* **动态降级**：具备完善的 Fallback 机制，当 LLM 接口超时或异常时，系统自动无缝降级为纯规则引擎审计，保障工业级系统的高可用性（SLA）。

### 4. 🔒 企业级隐私合规 (GDPR Compliance)
* **网关层脱敏**：在数据流转至大模型前，系统会通过正则匹配，自动对对话中的手机号、地址、订单号等敏感数据进行 `[PHONE]`、`[ORDER_ID]` 等占位符替换，严格保障跨境业务的隐私合规。

### 5. 🔍 证据链闭环 (Evidence-Based Tracking)
* **原文追溯**：每个扣分项均锁定 `evidence_quote`（违规原文），彻底消除 AI 判定的“黑盒感”。

---

## 🛠️ 技术底座 (Tech Stack)

* **产品前端**：Streamlit (Dashboard & 交互式数据可视化)
* **中台接口**：FastAPI (支持与 ERP/OA 系统低成本对接)
* **AI 引擎**：DeepSeek / OpenAI (Prompt Engineering)
* **数据层**：SQLite (开启 WAL 模式以支撑多线程并发读写)
* **数据处理**：Pandas, Plotly (数据清洗与雷达图/错误分布图构建)

---

## 🎥 演示视频与架构图 (Demo & Architecture)

### 视频演示
https://github.com/user-attachments/assets/5f0a44a4-2768-475f-8d24-3fc3d6aef404

### 系统流转架构

<img width="800" height="1000" alt="Welcome to FigJam" src="https://github.com/user-attachments/assets/98ad0889-eb36-486b-beca-a761c31d0b9a" />
---
* **指标看板**：展示总会话数、平均得分、合格率、满分率等全局指标。
* **诊断中心**：展示 AI 自动生成的【专家诊断建议】卡片。
* **交互式报告**：点击会话 ID，支持下钻查看每一句对话的扣分依据与优化操作。

---

## 🔐 履约声明与交流邀请 (Compliance & Let's Talk)

> ⚠️ **合规声明 (Disclaimer)**
> 本项目为实习期间深度参与的商业化落地项目。基于职业素养与保密协议（NDA），本仓库**仅作产品架构、策略逻辑与脱敏界面的展示，暂不开源核心业务代码、Prompt 指令集及真实生产数据**。演示视频中的分析内容均为随机生成的 Mock Data。
