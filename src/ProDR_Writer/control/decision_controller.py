"""
决策控制模块 - ProDR_Writer
基于Critic评分的循环优化系统

流程控制逻辑：
Requirement → BIA → Architecture → Critic
                            ↓
                    score < 80?
                    ↓ fail     ↓ pass
              Optimization    Writer
                    ↓
            Architecture(重跑)
                    ↓
                  Critic(再评审)
                   ...
最多3轮优化
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class DecisionResult(Enum):
    """决策结果枚举"""
    PASS = "pass"
    FAIL = "fail"
    MAX_RETRIES = "max_retries"


@dataclass
class CriticScore:
    """评审评分结果"""
    score: int  # 0-100
    fatal_issues: List[Dict[str, str]] = field(default_factory=list)
    can_proceed: bool = False
    summary: str = ""
    
    def __post_init__(self):
        self.can_proceed = self.score >= 80 and len(self.fatal_issues) == 0
    
    def to_json(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "fatal_issues": self.fatal_issues,
            "can_proceed": self.can_proceed,
            "summary": self.summary
        }


class DecisionController:
    """
    决策控制器
    
    核心逻辑：
    1. 收集所有Agent输出
    2. 调用Critic评分
    3. 根据评分决定下一步
    """
    
    MAX_OPTIMIZATION_ROUNDS = 3
    
    def __init__(self):
        self.current_round = 0
        self.optimization_history: List[Dict[str, Any]] = []
        self.last_critic_score: Optional[CriticScore] = None
    
    def should_optimize(self) -> bool:
        """判断是否需要优化"""
        if self.last_critic_score is None:
            return True
        if self.current_round >= self.MAX_OPTIMIZATION_ROUNDS:
            return False
        return not self.last_critic_score.can_proceed
    
    def record_round(self, architecture_output: Dict, critic_score: CriticScore):
        """记录当前轮次"""
        self.current_round += 1
        self.optimization_history.append({
            "round": self.current_round,
            "architecture_output": architecture_output,
            "critic_score": critic_score.to_json()
        })
        self.last_critic_score = critic_score
    
    def get_optimization_prompt(self) -> str:
        """生成优化提示词"""
        if not self.last_critic_score:
            return ""
        
        issues_str = "\n".join([
            f"- [{issue['severity']}] {issue['location']}: {issue['description']}"
            for issue in self.last_critic_score.fatal_issues
        ])
        
        return f"""
【优化要求 - 第{self.current_round + 1}轮】

上一轮评审发现以下问题，请根据这些问题优化架构设计：

{issues_str}

评审分数：{self.last_critic_score.score}/100

要求：
1. 只修改需要优化的部分，保留正确的部分
2. 确保优化后满足所有业务需求（RTO/RPO）
3. 输出优化后的完整架构设计JSON
"""
    
    def get_decision(self) -> DecisionResult:
        """获取当前决策"""
        if self.last_critic_score is None:
            return DecisionResult.FAIL
        
        if self.last_critic_score.can_proceed:
            return DecisionResult.PASS
        
        if self.current_round >= self.MAX_OPTIMIZATION_ROUNDS:
            return DecisionResult.MAX_RETRIES
        
        return DecisionResult.FAIL


# ============ Critic Agent 提示词 ============

CRITIC_SYSTEM_PROMPT = """
你是灾备方案资深评审专家。

你的职责：
1. 验证架构设计是否满足业务需求
2. 识别致命问题
3. 给出0-100的评分

评分标准（总分100）：
- RTO满足度：25分
- RPO满足度：25分
- 预算匹配度：20分
- 技术可行性：15分
- 风险可控性：15分

致命问题（任意一项直接判定FAIL）：
1. RTO架构设计 > 业务需求RTO
2. RPO架构设计 > 业务需求RPO
3. 总成本 > 预算上限×1.2
4. 关键技术缺失（如同步复制但无CDP保护）

输出格式（必须JSON）：
{
  "score": 0-100整数,
  "fatal_issues": [
    {
      "severity": "critical|major|minor",
      "location": "具体位置",
      "description": "问题描述",
      "suggestion": "修复建议"
    }
  ],
  "summary": "评审总结"
}
"""

CRITIC_TASK_DESCRIPTION = """
评审架构设计输出，判断是否可以进入文档生成阶段。

【输入数据】
- 业务需求（来自BIA）：RTO、RPO要求
- 架构设计（来自DR Architect）：RTO/RPO保证值、成本
- 灾备策略：复制模式、切换模式
- 投资估算：总成本

【评审内容】
1. 验证RTO满足度：架构保证RTO <= 业务需求RTO
2. 验证RPO满足度：架构保证RPO <= 业务需求RPO
3. 验证预算：总成本 <= 预算×1.2
4. 验证技术一致性：复制模式与RPO匹配
5. 评估风险等级

【输出】
返回CriticScore JSON

【注意】
- 必须严格评审，不得放水
- 评分低于80或存在致命问题不得进入下一阶段
"""


# ============ Optimization Agent 提示词 ============

OPTIMIZATION_SYSTEM_PROMPT = """
你是灾备方案优化专家。

你的职责：
1. 根据Critic评审意见优化架构
2. 修复致命问题
3. 保持原有正确的部分

优化原则：
1. 最小改动：只改需要优化的部分
2. 满足约束：RTO/RPO必须满足业务需求
3. 预算控制：尽量不超预算
4. 技术可行：选择的方案必须有实际产品支撑

输出格式（必须JSON）：
{
  "status": "success",
  "optimized_architecture": { ...完整的架构JSON... },
  "changes_made": ["变更1", "变更2", ...],
  "improvement_summary": "优化说明"
}
"""


def parse_critic_score(json_str: str) -> CriticScore:
    """解析Critic评分输出"""
    try:
        data = json.loads(json_str)
        return CriticScore(
            score=int(data.get("score", 0)),
            fatal_issues=data.get("fatal_issues", []),
            summary=data.get("summary", "")
        )
    except json.JSONDecodeError:
        return CriticScore(
            score=0,
            fatal_issues=[{
                "severity": "critical",
                "location": "JSON解析",
                "description": f"无法解析Critic输出: {json_str[:100]}",
                "suggestion": "请重新评审"
            }],
            summary="JSON解析失败"
        )
