"""
真正的多Agent职责分离架构 - ProDR_Writer

核心原则：
1. 每个Agent只有单一职责
2. 数据生成Agent不参与输出生成
3. 评审Agent不参与文档生成
4. WriterAgent是唯一的文档输出点

Agent职责矩阵：
┌─────────────────┬──────────────────────────────────────┐
│ Agent           │ 职责                                  │
├─────────────────┼──────────────────────────────────────┤
│ RequirementAnalyst │ 输出: BIA JSON + Infrastructure JSON │
│ DRArchitect       │ 输出: Strategy JSON + Architecture JSON │
│ CriticAgent       │ 输出: Score JSON + Issues JSON      │
│ OptimizerAgent   │ 输出: Optimized Architecture JSON    │
│ WriterAgent      │ 输出: Word文档路径                   │
└─────────────────┴──────────────────────────────────────┘

Task绑定：
1. bia_task           → RequirementAnalyst
2. infrastructure_task → RequirementAnalyst
3. strategy_task     → DRArchitect
4. architecture_task → DRArchitect
5. critic_task       → CriticAgent
6. optimization_task  → OptimizerAgent
7. document_task      → WriterAgent ← 唯一的文档生成Task
"""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


# ============ Agent 定义 ============

@dataclass
class AgentDefinition:
    """Agent定义"""
    name: str
    role: str
    goal: str
    backstory: str
    output_type: str  # JSON/Word/Score
    participates_in_output: bool  # 是否参与最终输出


# Agent职责定义表
AGENTS = {
    "requirement_analyst": AgentDefinition(
        name="requirement_analyst",
        role="业务需求分析师",
        goal="准确提取和结构化业务需求，不写任何描述性文档",
        backstory="资深需求分析师，精通BCM标准和RTO/RPO计算，只输出结构化JSON",
        output_type="JSON",
        participates_in_output=False
    ),
    
    "dr_architect": AgentDefinition(
        name="dr_architect",
        role="灾备架构设计师",
        goal="设计满足RTO/RPO要求的灾备架构，不写Word内容",
        backstory="15年灾备行业经验，精通各类灾备技术，只输出架构JSON",
        output_type="JSON",
        participates_in_output=False
    ),
    
    "critic": AgentDefinition(
        name="critic",
        role="方案评审专家",
        goal="严格评审架构，输出评分和问题清单，不参与文档生成",
        backstory="资深评审专家，只做评分和验收，不生成内容",
        output_type="Score",
        participates_in_output=False
    ),
    
    "optimizer": AgentDefinition(
        name="optimizer",
        role="架构优化专家",
        goal="根据评审意见修复问题，不写文档",
        backstory="擅长架构优化，只输出优化后的架构JSON",
        output_type="JSON",
        participates_in_output=False
    ),
    
    "writer": AgentDefinition(
        name="writer",
        role="技术文档工程师",
        goal="将结构化JSON转换为专业投标Word文档",
        backstory="专业文档工程师，唯一被允许生成Word文档的Agent",
        output_type="Word",
        participates_in_output=True  # 唯一的文档输出点
    ),
}


# ============ Task定义 ============

@dataclass
class TaskDefinition:
    """Task定义"""
    name: str
    agent: str  # 绑定的Agent
    input_from: List[str]  # 依赖的Task
    output_format: str  # JSON/Score/Word
    description: str


TASKS = {
    "bia_task": TaskDefinition(
        name="bia_task",
        agent="requirement_analyst",
        input_from=[],  # 依赖用户输入
        output_format="JSON",
        description="进行业务影响分析，输出结构化BIA数据"
    ),
    
    "infrastructure_task": TaskDefinition(
        name="infrastructure_task",
        agent="requirement_analyst",
        input_from=["bia_task"],
        output_format="JSON",
        description="进行现状评估，输出基础设施和差距分析JSON"
    ),
    
    "strategy_task": TaskDefinition(
        name="strategy_task",
        agent="dr_architect",
        input_from=["bia_task"],
        output_format="JSON",
        description="基于BIA设计灾备策略，输出策略JSON"
    ),
    
    "architecture_task": TaskDefinition(
        name="architecture_task",
        agent="dr_architect",
        input_from=["bia_task", "infrastructure_task", "strategy_task"],
        output_format="JSON",
        description="设计完整灾备架构，输出架构JSON"
    ),
    
    "critic_task": TaskDefinition(
        name="critic_task",
        agent="critic",
        input_from=["bia_task", "architecture_task", "strategy_task"],
        output_format="Score",
        description="严格评审架构，输出评分和fatal_issues"
    ),
    
    "optimization_task": TaskDefinition(
        name="optimization_task",
        agent="optimizer",
        input_from=["architecture_task", "critic_task"],
        output_format="JSON",
        description="根据评审意见优化架构，输出优化后的架构JSON"
    ),
    
    "document_task": TaskDefinition(
        name="document_task",
        agent="writer",
        input_from=["bia_task", "architecture_task", "strategy_task", "critic_task"],  # critic_task只读
        output_format="Word",
        description="将结构化JSON转换为Word文档"
    ),
}


# ============ 数据流定义 ============

DATA_FLOW = """
【数据流图】

用户输入 ──→ [bia_task] ──→ BIA JSON ──┬──→ [infrastructure_task]
                                         │
                                         ├──→ [strategy_task] ──→ Strategy JSON
                                         │                               │
                                         │                               ▼
                                         └──→ [architecture_task] ──→ Architecture JSON
                                                                          │
                    ┌─────────────────────────────────────────┴─────────────────┐
                    ▼                                                             ▼
              [critic_task]                                               [document_task]
              输出: Score JSON                                               输出: Word文档
                    │
                    ▼ (if FAIL)
           [optimization_task] ──→ Architecture(JSON) ──→ [critic_task] (循环，最多3次)
"""


# ============ 验证函数 ============

def validate_agent_task_binding():
    """验证Agent-Task绑定的正确性"""
    errors = []
    
    for task_name, task in TASKS.items():
        agent = AGENTS.get(task.agent)
        if not agent:
            errors.append(f"Task {task_name} 绑定的Agent {task.agent} 不存在")
            continue
        
        # 检查输出格式是否匹配
        if task.output_format == "JSON" and agent.output_type != "JSON":
            errors.append(f"Task {task_name} 输出JSON但Agent {agent.name} 不输出JSON")
        if task.output_format == "Score" and agent.output_type != "Score":
            errors.append(f"Task {task_name} 输出Score但Agent {agent.name} 不输出Score")
        if task.output_format == "Word" and agent.output_type != "Word":
            errors.append(f"Task {task_name} 输出Word但Agent {agent.name} 不输出Word")
    
    # 检查只有writer参与最终输出
    output_agents = [a.name for a in AGENTS.values() if a.participates_in_output]
    if len(output_agents) != 1 or output_agents[0] != "writer":
        errors.append(f"必须有且只有writer参与最终输出，当前: {output_agents}")
    
    return errors


def get_agent_prompt(agent_name: str) -> str:
    """获取Agent的系统提示词"""
    agent = AGENTS.get(agent_name)
    if not agent:
        return ""
    
    base_prompt = f"""
你是{agent.role}。

目标：{agent.goal}

背景：{agent.backstory}

【强制规则】
1. 你只输出{agent.output_type}格式
2. 禁止输出其他格式
3. 禁止参与文档生成（除非你是writer）
4. 禁止参与评审（除非你是critic）
"""
    
    if agent_name == "requirement_analyst":
        base_prompt += """
输出格式（必须JSON）：
{
  "status": "success",
  "data": {
    "business_systems": [...],
    "summary": {...}
  }
}
"""
    
    elif agent_name == "dr_architect":
        base_prompt += """
输出格式（必须JSON）：
{
  "status": "success",
  "data": {
    "dr_strategy": {...},
    "architecture": {...},
    "cost_estimate": {...}
  }
}
"""
    
    elif agent_name == "critic":
        base_prompt += """
【重要】你只做评分和问题识别，不生成任何内容。

输出格式（必须JSON）：
{
  "score": 0-100,
  "rule_check": [...],
  "fatal_issues": [...],
  "warnings": [...],
  "can_proceed": true/false
}
"""
    
    elif agent_name == "optimizer":
        base_prompt += """
【重要】你只修改架构JSON，不写任何文档。

输出格式（必须JSON）：
{
  "status": "success",
  "optimized_architecture": {...},
  "changes_made": [...],
  "improvement_summary": "..."
}
"""
    
    elif agent_name == "writer":
        base_prompt += """
【重要】你是唯一被允许生成Word文档的Agent。

你接收的结构化数据：
- BIA JSON
- Architecture JSON
- Strategy JSON
- Critic Score JSON

你的任务是将这些JSON转换为专业的Word投标文档。

输出格式（必须JSON）：
{
  "status": "success",
  "data": {
    "document_path": "outputs/灾备技术方案.docx",
    "page_count": 50,
    "chapters": [...]
  }
}
"""
    
    return base_prompt


# ============ 架构验证 ============

def print_architecture():
    """打印架构图"""
    print("\n" + "="*70)
    print("真正的多Agent职责分离架构")
    print("="*70)
    
    print("\n┌─────────────────┬──────────────────────────────────────┐")
    print("│ Agent           │ 职责                                  │")
    print("├─────────────────┼──────────────────────────────────────┤")
    for agent in AGENTS.values():
        output_icon = "📄" if agent.output_type == "Word" else "📊" if agent.output_type == "Score" else "📋"
        print(f"│ {output_icon} {agent.name:<14} │ {agent.goal:<36} │")
    print("└─────────────────┴──────────────────────────────────────┘")
    
    print("\nTask绑定：")
    for task_name, task in TASKS.items():
        print(f"  {task_name:25} → {task.agent}")
    
    print("\n" + DATA_FLOW)
    
    # 验证
    errors = validate_agent_task_binding()
    if errors:
        print("\n⚠️ 架构验证失败：")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\n✅ 架构验证通过")


if __name__ == "__main__":
    print_architecture()
