# ProDR_Writer

> AI驱动的灾备技术方案 Word 文档自动生成工具

基于 CrewAI 多Agent协作框架，自动完成业务影响分析（BIA）、现状评估、灾备架构设计、方案评审和高质量投标文档生成。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

---

## 🎯 功能特点

| 特性 | 说明 |
|------|------|
| 🤖 多Agent协作 | 5个专业角色分工明确：需求分析师、架构设计师、评审专家、优化专家、文档工程师 |
| 🔄 评审优化循环 | 自动多轮评审（最多3轮），不达标自动优化架构 |
| 📄 专业Word文档 | 封面、目录、章节、表格、页眉页脚，符合投标文件规范 |
| 📊 全流程覆盖 | BIA分析 → 现状评估 → 策略设计 → 架构设计 → 评审 → 文档生成 |
| ⚙️ 规则约束引擎 | 内置RTO/RPO/P0禁止备份恢复等硬约束，自动校验架构合规性 |
| 🔌 模型无关 | 通过LiteLLM桥接MiniMax API，支持所有OpenAI兼容接口 |

---

## 📁 项目结构

```
ProDR_Writer/
├── main.py                          # 程序入口
├── requirements.txt                  # pip 依赖
├── environment.yml                  # Conda 环境配置（推荐）
├── LICENSE                          # MIT 许可证
├── README.md                        # 本文件
└── src/ProDR_Writer/
    ├── __init__.py
    ├── crew_v3_final.py             # 核心执行引擎（5 Agent 协作）
    ├── architecture/
    │   └── agent_architecture.py    # Agent 职责定义表
    ├── config/
    │   ├── agents.yaml              # Agent 角色配置
    │   ├── tasks.yaml               # Task 任务定义
    │   └── data_schema.py           # 数据结构定义
    ├── control/
    │   ├── decision_controller.py   # 决策控制器
    │   └── rule_engine.py           # 规则引擎（RTO/RPO 约束）
    └── tools/
        └── doc_writer.py            # Word 文档生成工具
```

---

## 🛠️ 安装

### 前提条件

- Python 3.10+
- MiniMax API Key（或其他兼容 OpenAI 接口的 LLM API）

### 方式一：Conda（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/ilysom0611/ProDR_Writer.git
cd ProDR_Writer

# 2. 创建并激活环境
conda env create -f environment.yml
conda activate prodr_writer

# 3. 配置 API Key
export MINIMAX_API_KEY="your_api_key_here"
export MINIMAX_MODEL="MiniMax-M2.5"

# 4. 运行
python main.py --project "XX集团数据中心灾备项目"
```

### 方式二：pip + venv

```bash
git clone https://github.com/ilysom0611/ProDR_Writer.git
cd ProDR_Writer

python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

pip install -r requirements.txt

export MINIMAX_API_KEY="your_api_key_here"
export MINIMAX_MODEL="MiniMax-M2.5"

python main.py --project "XX集团数据中心灾备项目"
```

### 方式三：pip 直接安装

```bash
git clone https://github.com/ilysom0611/ProDR_Writer.git
cd ProDR_Writer
pip install -r requirements.txt
python main.py
```

---

## 🚀 使用方法

### 指定项目名称运行

```bash
python main.py --project "XX集团数据中心灾备项目"
```

### 交互式运行（自定义所有参数）

```bash
python main.py --interactive
```

### 直接运行（使用默认参数）

```bash
python main.py
```

### 查看系统信息

```bash
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
│  Requirement Analyst Agent           │
│  输入: 项目基本信息                  │
│  输出: P0-P3 系统分层、RTO/RPO       │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 2: 现状评估与差距分析          │
│  Requirement Analyst Agent           │
│  输入: BIA + 项目信息                │
│  输出: 8项差距分析、高/中/低风险     │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 3: 灾备策略设计                │
│  DR Architect Agent                 │
│  输入: BIA + 差距分析                │
│  输出: P0双活 / P1热备 / P2温备 /   │
│        P3冷备 分层策略               │
└─────────────────┬───────────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 4: 灾备架构设计               │
│  DR Architect Agent                 │
│  输入: 策略 + BIA                    │
│  输出: 网络/存储/计算/自动化完整架构 │
└─────────────────┬───────────────────┘
                  ▼
         ┌────────────────┐
         │ Step 5: 评审   │ ← Critic Agent（≤3轮）
         └───┬────────────┘
             │ can_proceed = true?
      ┌──────┴──────┐
      ▼             ▼
   ✅ 通过         ❌ 未通过
      │             ▼
      │    ┌─────────────────┐
      │    │ Step 6: 架构优化  │
      │    │ Optimizer Agent │
      │    └────────┬────────┘
      │             │ 回到评审
      └─────────────┘
                  ▼
┌─────────────────────────────────────┐
│  Step 7: 生成 Word 文档             │
│  Writer Agent + doc_writer tool     │
│  输入: 所有上游分析数据              │
│  输出: outputs/灾备技术方案.docx     │
└─────────────────────────────────────┘
```

---

## 📄 生成文档内容

| 章节 | 说明 |
|------|------|
| 封面 | 项目名称、投标单位、日期、密级 |
| 目录 | 自动生成 |
| 执行摘要 | 项目概述、核心指标一览 |
| 项目概述 | 背景、目标、范围 |
| 需求分析 | BIA分析、现状评估、差距分析表 |
| 灾备方案设计 | 架构设计、技术选型、分层策略 |
| 投资估算 | 分项报价表、总预算 |
| 风险评估 | 风险矩阵、应急预案 |
| 附录 | 资质证明、成功案例 |

---

## 🔧 自定义配置

### 修改 Agent 角色

编辑 `src/ProDR_Writer/config/agents.yaml`：

```yaml
dr_architect:
  role: 灾备架构设计师
  goal: 设计满足RTO/RPO要求的灾备架构
  backstory: 15年灾备行业经验，精通各类灾备技术
```

### 修改任务定义

编辑 `src/ProDR_Writer/config/tasks.yaml`：

```yaml
task_name:
  description: 任务描述
  expected_output: 期望输出格式
  agent: 对应的agent名称
```

### 修改文档格式

编辑 `src/ProDR_Writer/tools/doc_writer.py` 中的格式设置（字体、颜色、表格样式等）。

### 修改规则引擎约束

编辑 `src/ProDR_Writer/control/rule_engine.py` 中的规则：

| 规则ID | 约束条件 |
|--------|----------|
| RPO-001 | RPO=0 → 必须同步复制 |
| RTO-001 | RTO<30min → 必须自动切换 |
| CRIT-001 | P0系统 → 禁止备份恢复 |
| TECH-001 | 同步复制 → 距离≤100km |

---

## ⚠️ 常见问题

**Q: 提示 `MINIMAX_API_KEY` 未设置？**

```bash
export MINIMAX_API_KEY="your_api_key_here"
```

**Q: 文档生成失败，显示工具调用错误？**

检查 MiniMax API Key 是否有效，以及网络连接是否正常。

**Q: 架构评审不通过，循环次数过多？**

可以调整 `src/ProDR_Writer/crew_v3_final.py` 中的 `max_retries=3` 参数，或在 `_run_critic_loop` 中降低 `can_proceed` 的分数阈值。

**Q: 如何更换其他 LLM 模型？**

修改 `src/ProDR_Writer/crew_v3_final.py` 中的 `get_llm()` 函数，替换为 OpenAI 或其他兼容模型。

---

## 📝 License

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

## 🔗 相关链接

- GitHub 仓库：https://github.com/ilysom0611/ProDR_Writer
- CrewAI 文档：https://docs.crewai.com/
- LiteLLM 文档：https://docs.litellm.ai/
