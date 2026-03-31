# ProDR_Writer

基于 CrewAI 的高质量灾备技术方案 Word 文档自动生成工具。

## 功能特点

- 🤖 多 Agent 协作：需求分析、架构设计、风险评估、投资估算、文档生成
- 🔄 评审优化循环：自动多轮评审打分，不达标自动优化
- 📄 高质量 Word 文档：符合国家标准的格式规范
- 📊 完整内容：RTO/RPO 分析、差距分析、风险矩阵、报价清单
- ⚙️ 决策控制引擎：基于规则自动判断架构可行性

## 项目结构

```
ProDR_Writer/
├── main.py                        # 主程序入口（v1.0）
├── requirements.txt               # 依赖
├── README.md                     # 本文件
├── outputs/                      # 输出目录（构建产物，不上传）
└── src/ProDR_Writer/
    ├── __init__.py
    ├── crew_v3_final.py         # CrewAI Crew 定义（核心执行引擎）
    ├── architecture/             # 架构模块
    │   └── agent_architecture.py
    ├── config/                   # Agent / Task 配置
    │   ├── agents.yaml
    │   └── tasks.yaml
    ├── control/                  # 决策控制引擎
    │   ├── decision_controller.py
    │   └── rule_engine.py
    └── tools/
        └── doc_writer.py         # Word 文档生成工具
```

## 安装

### 方式一：Conda（推荐）

```bash
cd ProDR_Writer

# 创建并激活环境
conda env create -f environment.yml
conda activate prodr_writer

# 运行
python main.py --project "XX集团数据中心灾备项目"
```

### 方式二：Virtual Environment

```bash
cd ProDR_Writer

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py --project "XX集团数据中心灾备项目"
```

### 方式三：pip

```bash
cd ProDR_Writer
pip install -r requirements.txt
python main.py --project "XX集团数据中心灾备项目"
```

## 配置

1. 设置 API Key：
```bash
export MINIMAX_API_KEY=your_minimax_api_key
```

2. 可选：设置模型和端点：
```bash
export MINIMAX_MODEL=MiniMax-M2.5
export MINIMAX_API_BASE=https://api.minimax.io/v1
```

## 使用方法

### 交互式运行

```bash
python main.py --interactive
```

### 直接运行（使用默认项目信息）

```bash
python main.py
```

### 指定项目名称

```bash
python main.py --project "XX医院数据中心灾备项目"
```

## 工作流程

```
输入项目信息
    │
    ▼
┌─────────────────┐
│ 1. BIA 需求分析  │ ← Requirement Analyst Agent
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. 现状评估      │ ← Requirement Analyst Agent
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. 灾备策略设计  │ ← DR Architect Agent
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. 架构设计      │ ← DR Architect Agent
└────────┬────────┘
         ▼
    ┌─────────┐
    │ 5. 评审  │ ← Critic Agent（≤3 轮）
    └───┬─────┘
        │ 未达标
        ▼
┌─────────────────┐
│ 6. 架构优化      │ ← Optimizer Agent
└────────┬────────┘
         │ 达标
         ▼
┌─────────────────┐
│ 7. 生成 Word    │ ← Writer Agent + doc_writer tool
└─────────────────┘
```

## 生成文档内容

| 章节 | 内容 |
|------|------|
| 封面 | 项目名称、投标单位、日期 |
| 目录 | 自动生成 |
| 执行摘要 | 项目概述、核心指标 |
| 项目概述 | 背景、目标、范围 |
| 需求分析 | BIA、现状评估、差距分析 |
| 灾备方案设计 | 架构、技术选型、实施计划 |
| 投资估算 | 分项报价、总预算 |
| 风险评估 | 风险矩阵、应急预案 |
| 附录 | 资质、案例 |

## 自定义

### 修改 Agent 配置

编辑 `src/ProDR_Writer/config/agents.yaml`：

```yaml
dr_architect:
  role: 你的角色
  goal: 你的目标
  backstory: 你的背景
```

### 修改 Task 配置

编辑 `src/ProDR_Writer/config/tasks.yaml`：

```yaml
task_name:
  description: 任务描述
  expected_output: 期望输出
  agent: 对应的agent
```

### 修改文档格式

编辑 `src/ProDR_Writer/tools/doc_writer.py` 中的格式设置。

### 修改决策规则

编辑 `src/ProDR_Writer/control/rule_engine.py` 中的规则。

## 注意事项

1. 确保 MiniMax API Key 有效
2. 首次运行需要较长时间（Agent 初始化）
3. 确保网络连接正常
4. 输出目录需要有写入权限

## License

MIT
