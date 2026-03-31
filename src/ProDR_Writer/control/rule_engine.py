"""
规则引擎 - ProDR_Writer
灾备方案生成系统强规则约束

规则分类：
1. RTO/RPO约束 - 业务需求必须被满足
2. 技术选型约束 - 特定需求必须使用特定技术
3. 合规性约束 - 行业标准和规范
4. 成本约束 - 预算限制

使用方法：
from control.rule_engine import RuleEngine, Rule

engine = RuleEngine()
result = engine.validate(architecture_data, bia_data, dr_strategy)
"""

import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class RuleStatus(Enum):
    """规则检查结果"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class RuleResult:
    """单条规则检查结果"""
    rule_id: str
    rule_name: str
    status: RuleStatus
    message: str = ""
    location: str = ""
    suggestion: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule_name,
            "rule_id": self.rule_id,
            "status": self.status.value,
            "message": self.message,
            "location": self.location,
            "suggestion": self.suggestion
        }


@dataclass
class ValidationResult:
    """完整验证结果"""
    overall_pass: bool
    results: List[RuleResult] = field(default_factory=list)
    fatal_issues: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)
    
    def add_result(self, result: RuleResult):
        self.results.append(result)
        if result.status == RuleStatus.FAIL:
            self.fatal_issues.append(result.to_dict())
        elif result.status == RuleStatus.WARNING:
            self.warnings.append(result.to_dict())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_pass": self.overall_pass,
            "fatal_count": len(self.fatal_issues),
            "warning_count": len(self.warnings),
            "fatal_issues": self.fatal_issues,
            "warnings": self.warnings,
            "all_results": [r.to_dict() for r in self.results]
        }


# ============ 规则定义 ============

class DRRule:
    """灾备方案规则基类"""
    
    @staticmethod
    def check(architecture_data: Dict, bia_data: Dict, dr_strategy: Dict, inputs: Dict) -> List[RuleResult]:
        """检查规则，返回结果列表"""
        raise NotImplementedError


class RPOConstraintRules(DRRule):
    """
    RPO约束规则
    
    核心规则：
    - RPO=0 → 必须使用同步复制
    - RPO<15min → 推荐同步复制或CDP
    - RPO>60min → 可使用异步复制
    """
    
    @staticmethod
    def check(architecture_data: Dict, bia_data: Dict, dr_strategy: Dict, inputs: Dict) -> List[RuleResult]:
        results = []
        
        # 获取最严格的RPO需求
        strictest_rpo = None
        for sys in bia_data.get("business_systems", []):
            rpo = sys.get("rpo_minutes", 999)
            if strictest_rpo is None or rpo < strictest_rpo:
                strictest_rpo = rpo
        
        if strictest_rpo is None:
            return results
        
        replication_mode = dr_strategy.get("replication_mode", "")
        rpo_guaranteed = dr_strategy.get("rpo_guaranteed_minutes", 999)
        
        # 规则1: RPO=0 必须同步复制
        if strictest_rpo == 0:
            if "同步" not in replication_mode:
                results.append(RuleResult(
                    rule_id="RPO-001",
                    rule_name="RPO=0必须同步复制",
                    status=RuleStatus.FAIL,
                    message=f"最严格RPO需求为0（实时），但选择了'{replication_mode}'",
                    location="dr_strategy.replication_mode",
                    suggestion="选择'同步复制'模式"
                ))
            else:
                results.append(RuleResult(
                    rule_id="RPO-001",
                    rule_name="RPO=0必须同步复制",
                    status=RuleStatus.PASS,
                    message="RPO=0使用同步复制，满足要求"
                ))
        
        # 规则2: RPO<15必须CDP或同步
        elif strictest_rpo < 15 and strictest_rpo > 0:
            if "同步" not in replication_mode and "CDP" not in replication_mode:
                results.append(RuleResult(
                    rule_id="RPO-002",
                    rule_name="RPO<15分钟推荐CDP或同步",
                    status=RuleStatus.FAIL,
                    message=f"RPO需求为{strictest_rpo}分钟，但选择了'{replication_mode}'",
                    location="dr_strategy.replication_mode",
                    suggestion="选择'CDP持续数据保护'或'同步复制'"
                ))
            else:
                results.append(RuleResult(
                    rule_id="RPO-002",
                    rule_name="RPO<15分钟推荐CDP或同步",
                    status=RuleStatus.PASS,
                    message=f"RPO={strictest_rpo}分钟，使用{replication_mode}满足要求"
                ))
        
        # 规则3: 架构保证RPO必须<=需求RPO
        if rpo_guaranteed > strictest_rpo:
            results.append(RuleResult(
                rule_id="RPO-003",
                rule_name="架构RPO<=需求RPO",
                status=RuleStatus.FAIL,
                message=f"架构保证RPO={rpo_guaranteed}分钟 > 需求RPO={strictest_rpo}分钟",
                location="dr_strategy.rpo_guaranteed_minutes",
                suggestion="降低RPO保证值或升级复制技术"
            ))
        else:
            results.append(RuleResult(
                rule_id="RPO-003",
                rule_name="架构RPO<=需求RPO",
                status=RuleStatus.PASS,
                message=f"架构RPO={rpo_guaranteed}分钟 <= 需求RPO={strictest_rpo}分钟"
            ))
        
        return results


class RTOConstraintRules(DRRule):
    """
    RTO约束规则
    
    核心规则：
    - RTO<30min → 必须有自动切换机制
    - RTO<60min → 推荐自动切换
    - RTO>4hour → 可手动切换
    """
    
    @staticmethod
    def check(architecture_data: Dict, bia_data: Dict, dr_strategy: Dict, inputs: Dict) -> List[RuleResult]:
        results = []
        
        # 获取最严格的RTO需求
        strictest_rto = None
        for sys in bia_data.get("business_systems", []):
            rto = sys.get("rto_minutes", 999)
            if strictest_rto is None or rto < strictest_rto:
                strictest_rto = rto
        
        if strictest_rto is None:
            return results
        
        switch_mode = dr_strategy.get("switch_mode", "")
        rto_guaranteed = dr_strategy.get("rto_guaranteed_minutes", 999)
        
        # 规则1: RTO<30分钟必须自动切换
        if strictest_rto < 30:
            if "自动" not in switch_mode:
                results.append(RuleResult(
                    rule_id="RTO-001",
                    rule_name="RTO<30分钟必须自动切换",
                    status=RuleStatus.FAIL,
                    message=f"RTO需求为{strictest_rto}分钟，但选择了'{switch_mode}'",
                    location="dr_strategy.switch_mode",
                    suggestion="必须选择'自动切换'模式"
                ))
            else:
                results.append(RuleResult(
                    rule_id="RTO-001",
                    rule_name="RTO<30分钟必须自动切换",
                    status=RuleStatus.PASS,
                    message="使用自动切换，满足RTO要求"
                ))
        
        # 规则2: RTO<60分钟推荐自动切换
        elif strictest_rto < 60:
            if "自动" not in switch_mode:
                results.append(RuleResult(
                    rule_id="RTO-002",
                    rule_name="RTO<60分钟推荐自动切换",
                    status=RuleStatus.WARNING,
                    message=f"RTO需求为{strictest_rto}分钟，建议使用自动切换以提高恢复速度",
                    location="dr_strategy.switch_mode",
                    suggestion="考虑升级为'自动切换'"
                ))
        
        # 规则3: 架构保证RTO必须<=需求RTO
        if rto_guaranteed > strictest_rto:
            results.append(RuleResult(
                rule_id="RTO-003",
                rule_name="架构RTO<=需求RTO",
                status=RuleStatus.FAIL,
                message=f"架构保证RTO={rto_guaranteed}分钟 > 需求RTO={strictest_rto}分钟",
                location="dr_strategy.rto_guaranteed_minutes",
                suggestion="优化切换流程或增加自动化程度"
            ))
        else:
            results.append(RuleResult(
                rule_id="RTO-003",
                rule_name="架构RTO<=需求RTO",
                status=RuleStatus.PASS,
                message=f"架构RTO={rto_guaranteed}分钟 <= 需求RTO={strictest_rto}分钟"
            ))
        
        return results


class CriticalityConstraintRules(DRRule):
    """
    核心系统约束规则
    
    核心规则：
    - criticality=P0系统 → 禁止使用备份恢复方案
    - P0系统 → 必须同城双活或异地灾备
    - P0系统 → 禁止手动切换
    """
    
    @staticmethod
    def check(architecture_data: Dict, bia_data: Dict, dr_strategy: Dict, inputs: Dict) -> List[RuleResult]:
        results = []
        
        # 找出P0系统
        p0_systems = [s for s in bia_data.get("business_systems", []) if s.get("criticality") == "P0"]
        
        if not p0_systems:
            return results
        
        strategy_type = dr_strategy.get("strategy_type", "")
        switch_mode = dr_strategy.get("switch_mode", "")
        
        # 规则1: P0系统禁止备份恢复方案
        if "备份" in strategy_type or "backup" in strategy_type.lower():
            results.append(RuleResult(
                rule_id="CRIT-001",
                rule_name="P0系统禁止备份恢复方案",
                status=RuleStatus.FAIL,
                message=f"存在{len(p0_systems)}个P0核心系统，不能使用备份恢复方案",
                location="dr_strategy.strategy_type",
                suggestion="升级为'同城双活'或'异地灾备'方案"
            ))
        
        # 规则2: P0系统推荐同城双活
        if "同城" not in strategy_type and "双活" not in strategy_type:
            results.append(RuleResult(
                rule_id="CRIT-002",
                rule_name="P0系统推荐同城双活",
                status=RuleStatus.WARNING,
                message=f"存在{len(p0_systems)}个P0核心系统，建议使用同城双活方案",
                location="dr_strategy.strategy_type",
                suggestion="考虑使用'同城双活'架构"
            ))
        
        # 规则3: P0系统禁止手动切换
        if switch_mode == "手动切换":
            results.append(RuleResult(
                rule_id="CRIT-003",
                rule_name="P0系统禁止手动切换",
                status=RuleStatus.FAIL,
                message=f"存在{len(p0_systems)}个P0核心系统，不能使用手动切换",
                location="dr_strategy.switch_mode",
                suggestion="升级为'自动切换'或'半自动切换'"
            ))
        
        return results


class CostConstraintRules(DRRule):
    """
    成本约束规则
    
    核心规则：
    - 总成本 <= 预算上限×1.2
    - 硬件成本 <= 总成本×60%
    - 运维成本 >= 总成本×10%/年
    """
    
    @staticmethod
    def check(architecture_data: Dict, bia_data: Dict, dr_strategy: Dict, inputs: Dict) -> List[RuleResult]:
        results = []
        
        cost = architecture_data.get("cost_estimate", {})
        total_yi = cost.get("total_yi", 0)
        
        # 解析预算范围
        budget_range = inputs.get("budget_range", "0-99999万")
        try:
            if "-" in budget_range:
                parts = budget_range.replace("万", "").replace("亿", "0000").split("-")
                budget_min = float(parts[0].strip())
                budget_max = float(parts[1].strip()) if len(parts) > 1 else budget_min
            else:
                budget_max = float(budget_range.replace("万", "").replace("亿", "0000"))
        except:
            budget_max = 99999
        
        # 规则1: 总成本 <= 预算上限×1.2
        if total_yi > budget_max * 1.2:
            results.append(RuleResult(
                rule_id="COST-001",
                rule_name="总成本不超过预算×1.2",
                status=RuleStatus.FAIL,
                message=f"总成本{total_yi}亿 > 预算上限×1.2={budget_max*1.2}亿",
                location="cost_estimate.total_yi",
                suggestion="优化方案降低总成本"
            ))
        elif total_yi > budget_max:
            results.append(RuleResult(
                rule_id="COST-001",
                rule_name="总成本不超过预算×1.2",
                status=RuleStatus.WARNING,
                message=f"总成本{total_yi}亿超过预算{budget_max}亿，但在允许范围内"
            ))
        else:
            results.append(RuleResult(
                rule_id="COST-001",
                rule_name="总成本不超过预算×1.2",
                status=RuleStatus.PASS,
                message=f"总成本{total_yi}亿在预算{budget_max}亿范围内"
            ))
        
        return results


class TechnicalFeasibilityRules(DRRule):
    """
    技术可行性规则
    
    核心规则：
    - 同步复制距离 <= 100km
    - 异距离离 >= 100km
    - 数据库必须支持双向同步
    """
    
    @staticmethod
    def check(architecture_data: Dict, bia_data: Dict, dr_strategy: Dict, inputs: Dict) -> List[RuleResult]:
        results = []
        
        primary_site = architecture_data.get("primary_site", {})
        dr_site = architecture_data.get("dr_site", {})
        
        distance = dr_site.get("distance_km", 0)
        replication_mode = dr_strategy.get("replication_mode", "")
        strategy_type = dr_strategy.get("strategy_type", "")
        
        # 规则1: 同步复制距离 <= 100km
        if "同步" in replication_mode and distance > 100:
            results.append(RuleResult(
                rule_id="TECH-001",
                rule_name="同步复制距离<=100km",
                status=RuleStatus.FAIL,
                message=f"同步复制但站点距离{distance}km超过100km限制",
                location="dr_site.distance_km",
                suggestion="降低距离或改用异步复制"
            ))
        
        # 规则2: 异地灾备距离 >= 100km
        if "异地" in strategy_type and distance < 100:
            results.append(RuleResult(
                rule_id="TECH-002",
                rule_name="异地灾备距离>=100km",
                status=RuleStatus.FAIL,
                message=f"标称异地灾备但距离{distance}km < 100km",
                location="dr_site.distance_km",
                suggestion="选择更远的灾备站点或改用同城双活"
            ))
        
        return results


# ============ 规则引擎 ============

class RuleEngine:
    """
    规则引擎
    
    使用方法：
    engine = RuleEngine()
    result = engine.validate(
        architecture_data=arch,
        bia_data=bia,
        dr_strategy=strategy,
        inputs=project_inputs
    )
    
    if not result.overall_pass:
        # 有致命问题，不能进入下一步
    """
    
    def __init__(self):
        self.rules: List[type] = [
            RPOConstraintRules,
            RTOConstraintRules,
            CriticalityConstraintRules,
            CostConstraintRules,
            TechnicalFeasibilityRules,
        ]
    
    def validate(
        self,
        architecture_data: Dict,
        bia_data: Dict,
        dr_strategy: Dict,
        inputs: Dict
    ) -> ValidationResult:
        """
        执行所有规则检查
        """
        result = ValidationResult(overall_pass=True)
        
        for rule_class in self.rules:
            try:
                rule_results = rule_class.check(
                    architecture_data=architecture_data,
                    bia_data=bia_data,
                    dr_strategy=dr_strategy,
                    inputs=inputs
                )
                
                for rule_result in rule_results:
                    result.add_result(rule_result)
                    
            except Exception as e:
                result.results.append(RuleResult(
                    rule_id="SYSTEM",
                    rule_name="规则执行异常",
                    status=RuleStatus.WARNING,
                    message=f"规则{rule_class.__name__}执行异常: {str(e)}"
                ))
        
        # 判断overall_pass: 没有FAIL即通过
        result.overall_pass = len(result.fatal_issues) == 0
        
        return result
    
    def get_rule_check_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """生成规则检查摘要"""
        return {
            "rule_check": [
                {
                    "rule": r.to_dict()["rule"],
                    "status": r.to_dict()["status"]
                }
                for r in result.results
            ],
            "overall_pass": result.overall_pass,
            "fatal_count": len(result.fatal_issues),
            "warning_count": len(result.warnings)
        }


# ============ 快捷函数 ============

def quick_validate(
    architecture_data: Dict,
    bia_data: Dict,
    dr_strategy: Dict,
    inputs: Dict
) -> Dict[str, Any]:
    """
    快速验证函数
    
    返回格式：
    {
        "overall_pass": true/false,
        "rule_check": [...],
        "fatal_issues": [...],
        "warnings": [...]
    }
    """
    engine = RuleEngine()
    result = engine.validate(architecture_data, bia_data, dr_strategy, inputs)
    return result.to_dict()


# ============ 规则表（可配置） ============

RULE_DEFINITIONS = """
# 灾备方案生成系统规则表

## RPO相关规则
| 规则ID | 条件 | 要求 | 严重性 |
|--------|------|------|--------|
| RPO-001 | RPO=0 | 必须同步复制 | FATAL |
| RPO-002 | RPO<15min | CDP或同步复制 | FATAL |
| RPO-003 | 所有RPO | 架构RPO<=需求RPO | FATAL |

## RTO相关规则
| 规则ID | 条件 | 要求 | 严重性 |
|--------|------|------|--------|
| RTO-001 | RTO<30min | 必须自动切换 | FATAL |
| RTO-002 | RTO<60min | 推荐自动切换 | WARNING |
| RTO-003 | 所有RTO | 架构RTO<=需求RTO | FATAL |

## 核心系统规则
| 规则ID | 条件 | 要求 | 严重性 |
|--------|------|------|--------|
| CRIT-001 | P0系统存在 | 禁止备份恢复 | FATAL |
| CRIT-002 | P0系统存在 | 推荐同城双活 | WARNING |
| CRIT-003 | P0系统存在 | 禁止手动切换 | FATAL |

## 成本规则
| 规则ID | 条件 | 要求 | 严重性 |
|--------|------|------|--------|
| COST-001 | 总成本 | <=预算×1.2 | FATAL |

## 技术可行性规则
| 规则ID | 条件 | 要求 | 严重性 |
|--------|------|------|--------|
| TECH-001 | 同步复制 | 距离<=100km | FATAL |
| TECH-002 | 异地灾备 | 距离>=100km | FATAL |
"""
