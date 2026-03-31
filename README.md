# ProDR_Writer

> AI驱动的灾备技术方案 Word 文档自动生成工具

基于 CrewAI 多Agent协作框架，自动完成业务影响分析（BIA）、现状评估、灾备架构设计、方案评审（8维度）和高质量投标文档生成。支持泰国 OIC / PDPA 保险行业合规要求。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v1.0-blue.svg)]()

---

## 🎯 功能特点

| 特性 | 说明 |
|------|------|
| 🤖 多Agent协作 | 5个专业角色分工：需求分析师、架构设计师、评审专家、优化专家、文档工程师 |
| 🔄 评审优化循环 | 8维度严格评审（OIC/PDPA合规、安全、成本等），最多3轮优化，不达标强制升级 |
| 📊 自动图表 | 灾备架构图、网络拓扑图、产品选型图全部自动生成并嵌入 Word |
| 📄 专业投标文档 | 7章节完整内容、8张数据表格、3张架构图、页眉页脚、封面 |
| 🏛️ 行业合规 | 内置泰国 OIC 监管要求（异地灾备、RTO≤4h、RPO≤1h）和 PDPA 数据保护合规 |
| ⚙️ 分层约束引擎 | P0→RPO=0/RTO<30min、P1→RPO≤1min/RTO<1h …… 规则自动校验 |
| 🔌 模型无关 | 通过LiteLLM桥接MiniMax / OpenAI / Azure OpenAI，所有OpenAI兼容接口 |

---

## 📁 项目结构

```
ProDR_Writer/
├── main.py                          # 程序入口（单命令模式）
├── requirements.txt                  # pip 依赖
├── environment.yml                   # Conda 环境配置（推荐）
├── run_test.py                      # 快速测试脚本
├── LICENSE                          # MIT 许可证
├── README.md                        # 本文件
├── outputs/                        # 生成文档输出目录
└── src/
    ├── __init__.py
    └── ProDR_Writer/
        ├── __init__.py
        ├── crew_v3_final.py         # 核心执行引擎（5 Agent 协作）
        ├── architecture/
        │   └── agent_architecture.py # Agent 职责定义表
        ├── config/
        │   ├── agents.yaml           # Agent 角色配置
        │   ├── tasks.yaml           # Task 任务定义
        │   └── data_schema.py       # 数据结构定义
        ├── control/
        │   ├── decision_controller.py # 决策控制器
        │   └── rule_engine.py       # 规则引擎（RTO/RPO 约束）
        └── tools/
            ├── __init__.py
            └── doc_writer.py        # Word 文档生成工具（含图表生成）
```

---

## 🛠️ 安装

### 前提条件

- Python 3.10+
- MiniMax API Key（或其他兼容 OpenAI 接口的 LLM API）
- matplotlib（图表自动生成用）

### 方式一：Conda（推荐）

```bash
git clone https://github.com/ilysom0611/ProDR_Writer.git
cd ProDR_Writer

conda env create -f environment.yml
conda activate prodr_writer

export MINIMAX_API_KEY="your_api_key_here"
export MINIMAX_MODEL="MiniMax-M2.5"

python main.py --project "XX集团数据中心灾备项目"
```

### 方式二：pip + venv

```bash
git clone https://github.com/ilysom0611/ProDR_Writer.git
cd ProDR_Writer

python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate        # Windows

pip install -r requirements.txt

export MINIMAX_API_KEY="your_api_key_here"
python main.py --project "XX集团数据中心灾备项目"
```

---

## 🚀 使用方法

```bash
# 指定项目名称运行（推荐）
python main.py --project "XX集团数据中心灾备项目"

# 交互式运行（自定义所有参数）
python main.py --interactive

# 直接运行（使用默认参数）
python main.py

# 查看系统信息
python main.py info
```

---

## ⚙️ 环境变量配置

| 变量名 | 必须 | 默认值 | 说明 |
|--------|------|--------|------|
| `MINIMAX_API_KEY` | ✅ | — | MiniMax API Key |
| `MINIMAX_MODEL` | ❌ | `MiniMax-M2.5` | 模型名称 |
| `MINIMAX_API_BASE` | ❌ | `https://api.minimax.io/v1` | API 端点 |

---

## 🔄 执行流程

```
输入项目信息
    │
    ▼
┌─────────────────────────────────────┐
│  Step 1: BIA 业务影响分析            │
│  Requirement Analyst                   │
│  → P0-P3 系统分层、RTO/RPO 要求     │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 2: 现状评估与差距分析          │
│  Requirement Analyst                   │
│  → 8项差距分析（高/中/低风险）      │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 3: 灾备策略设计                │
│  DR Architect                        │
│  → P0双活 / P1热备 / P2温备 / P3冷备│
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 4: 灾备架构设计                │
│  DR Architect                        │
│  → 网络/存储/计算/自动化完整架构      │
└─────────────────┬───────────────────┘
                  ▼
         ┌────────────────┐
         │ Step 5: 评审   │ ← Critic Agent（≤3轮，8维度）
         └───┬────────────┘
             │ score≥90?
      ┌──────┴──────┐
      ▼             ▼
   ✅ 通过        ❌ 优化
      │    ┌─────────────────┐
      │    │ Optimizer Agent │ ← 修复问题
      │    └────────┬────────┘
      └──────←──────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 6: 生成 Word 文档              │
│  7章节 + 8表格 + 3张自动生成图表    │
│  → outputs/灾备技术方案.docx        │
└─────────────────────────────────────┘
```

---

## 📄 生成文档内容

| 章节 | 内容 |
|------|------|
| 封面 | 项目名称、投标单位、行业、日期、密级 |
| 目录 | 7章完整目录 |
| 第一章 执行摘要 | 业务背景、P0-P3分层概览、OIC/PDPA合规概览 |
| 第二章 项目概述 | 背景、建设目标、项目范围 |
| 第三章 需求分析 | BIA分析（系统列表+RTO/RPO表格）、现状评估、差距分析表（9项） |
| 第四章 灾备方案设计 | 分层策略表、**架构图**、**网络拓扑图**、存储/计算/切换设计、**产品选型图** |
| 第五章 投资估算 | 估算比例表、5大类投资分配 |
| 第六章 风险评估 | 评审问题清单表（阻塞/严重/一般）、风险矩阵 |
| 第七章 附录 | 资质证明、案例、培训计划 |

> **文档输出规格**：约 350KB，包含封面、7章节正文、8张数据表格、3张架构/网络/产品 PNG 图片。

---

## 🏛️ 行业合规内置

系统内置以下监管知识，可直接用于保险、金融、政府等行业投标：

| 监管框架 | 关键要求 |
|----------|----------|
| 泰国 OIC | 核心系统 RTO≤4h、RPO≤1h，异地灾备，年度演练 |
| 泰国 PDPA | 数据本地化，跨境传输需加密+同意机制，保留≥7年 |
| 中国等保2.0 | 三级及以上系统需灾备，RTO/RPO有明确要求 |
| ISO 22301 | 业务连续性管理体系认证标准 |

---

## 🔧 自定义配置

### 修改评审维度与阈值

编辑 `src/ProDR_Writer/crew_v3_final.py` 中 `_run_critic_loop` 的评审 prompt，调整维度权重或 `score >= 90` 阈值。

### 修改文档格式

编辑 `src/ProDR_Writer/tools/doc_writer.py` 中的：
- `_add_page_number()` — 页眉页脚格式
- `_set_cell_shading()` — 表头颜色
- `_build_chapters()` — 各章节内容模板

### 修改规则约束

编辑 `src/ProDR_Writer/control/rule_engine.py` 中的规则定义。

---

## ⚠️ 常见问题

**Q: 提示 `MINIMAX_API_KEY` 未设置？**
```bash
export MINIMAX_API_KEY="your_api_key_here"
```

**Q: 文档中图片中文显示为方块？**
系统服务器无中文字体，图表标签使用英文。Word 正文中的中文描述正常显示，不影响阅读。安装中文字体（如 `Noto Sans CJK`）后可解决。

**Q: 如何更换为 OpenAI GPT-4？**
```bash
export OPENAI_API_KEY="sk-..."
export MINIMAX_MODEL="gpt-4"
export MINIMAX_API_BASE="https://api.openai.com/v1"
```
然后修改 `crew_v3_final.py` 中 `get_llm()` 的 `model=` 参数。

**Q: 评审分数达不到90分？**
系统默认要求≥90分才算通过。可将 `score >= 90` 调整为 `score >= 60` 以降低标准，或在 `src/ProDR_Writer/crew_v3_final.py` 中强化 Architect Agent 的 prompt。

**Q: conda 环境创建失败？**
```bash
conda env create -f environment.yml
# 如失败，手动创建：
conda create -n prodr_writer python=3.10 -y
conda activate prodr_writer
pip install -r requirements.txt
```

---

## 📝 License

MIT License - 详见 [LICENSE](LICENSE) 文件。
