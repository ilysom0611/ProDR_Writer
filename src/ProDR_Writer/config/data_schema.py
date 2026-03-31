# 灾备技术方案统一数据模型 Schema
# 所有Agent必须遵循此JSON Schema进行数据交换

PROJECT_INFO_SCHEMA = {
    "type": "object",
    "required": ["project_name", "company_name", "industry"],
    "properties": {
        "project_name": {"type": "string", "description": "项目名称"},
        "company_name": {"type": "string", "description": "投标单位名称"},
        "industry": {"type": "string", "enum": ["金融", "医疗", "政府", "教育", "制造", "零售", "其他"]},
        "scale": {"type": "string", "enum": ["小型", "中型", "大型", "超大型"]},
        "rto_requirement": {"type": "string", "description": "RTO要求"},
        "rpo_requirement": {"type": "string", "description": "RPO要求"},
        "budget_range": {"type": "string", "description": "预算范围"},
        "submission_date": {"type": "string", "description": "投标日期"},
        "contact_person": {"type": "string", "description": "联系人"},
    }
}

BUSINESS_SYSTEMS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["name", "rto_minutes", "rpo_minutes", "criticality", "hourly_loss"],
        "properties": {
            "name": {"type": "string", "description": "业务系统名称"},
            "description": {"type": "string", "description": "业务描述"},
            "rto_minutes": {"type": "integer", "description": "RTO要求（分钟）"},
            "rpo_minutes": {"type": "integer", "description": "RPO要求（分钟）"},
            "criticality": {"type": "string", "enum": ["P0", "P1", "P2", "P3"], "description": "优先级"},
            "hourly_loss": {"type": "number", "description": "每小时业务中断损失（万元）"},
            "data_volume_tb": {"type": "number", "description": "日数据增量（TB）"},
            "peak_concurrent_users": {"type": "integer", "description": "峰值并发用户数"},
        }
    }
}

INFRASTRUCTURE_SCHEMA = {
    "type": "object",
    "properties": {
        "servers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["物理机", "虚拟机", "容器"]},
                    "count": {"type": "integer"},
                    "specs": {"type": "string"},
                    "location": {"type": "string"},
                }
            }
        },
        "storage": {
            "type": "object",
            "properties": {
                "total_capacity_tb": {"type": "number"},
                "current_type": {"type": "string"},
                "vendor": {"type": "string"},
                "location": {"type": "string"},
            }
        },
        "database": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "enum": ["Oracle", "MySQL", "PostgreSQL", "SQLServer", "MongoDB", "其他"]},
                    "version": {"type": "string"},
                    "cluster_mode": {"type": "string", "enum": ["单机", "主备", "RAC", "集群"]},
                    "data_size_tb": {"type": "number"},
                }
            }
        },
        "network": {
            "type": "object",
            "properties": {
                "bandwidth": {"type": "string"},
                "firewall": {"type": "string"},
                "load_balancer": {"type": "string"},
            }
        },
        "existing_dr": {
            "type": "object",
            "properties": {
                "backup_mode": {"type": "string"},
                "backup_frequency": {"type": "string"},
                "has_remote_replication": {"type": "boolean"},
                "has_auto_switch": {"type": "boolean"},
                "has_dr_site": {"type": "boolean"},
            }
        }
    }
}

GAP_ANALYSIS_SCHEMA = {
    "type": "object",
    "required": ["current_state", "target_state", "gaps", "recommendations"],
    "properties": {
        "current_state": {
            "type": "object",
            "properties": {
                "current_rto_minutes": {"type": "integer"},
                "current_rpo_minutes": {"type": "integer"},
                "max_acceptable_loss": {"type": "number"},
            }
        },
        "target_state": {
            "type": "object",
            "properties": {
                "target_rto_minutes": {"type": "integer"},
                "target_rpo_minutes": {"type": "integer"},
                "max_acceptable_loss": {"type": "number"},
            }
        },
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "severity": {"type": "string", "enum": ["高", "中", "低"]},
                }
            }
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
}

DR_STRATEGY_SCHEMA = {
    "type": "object",
    "required": ["strategy_type", "replication_mode", "switch_mode"],
    "properties": {
        "strategy_type": {
            "type": "string",
            "enum": ["同城双活", "异地灾备", "3DC", "云灾备", "混合灾备"],
            "description": "灾备策略类型"
        },
        "replication_mode": {
            "type": "string",
            "enum": ["同步复制", "异步复制", "强一致性异步", " CDP持续数据保护"],
            "description": "数据复制模式"
        },
        "switch_mode": {
            "type": "string",
            "enum": ["手动切换", "自动切换", "半自动切换"],
            "description": "切换模式"
        },
        "rpo_guaranteed_minutes": {"type": "integer", "description": "保证的RPO（分钟）"},
        "rto_guaranteed_minutes": {"type": "integer", "description": "保证的RTO（分钟）"},
        "rationale": {"type": "string", "description": "策略选择理由"}
    }
}

ARCHITECTURE_SCHEMA = {
    "type": "object",
    "required": ["primary_site", "dr_site", "components"],
    "properties": {
        "primary_site": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "string"},
                "tier_level": {"type": "string", "enum": ["T1", "T2", "T3", "T4"]},
            }
        },
        "dr_site": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "location": {"type": "string"},
                "distance_km": {"type": "integer"},
                "tier_level": {"type": "string"},
            }
        },
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "component_name": {"type": "string"},
                    "component_type": {"type": "string", "enum": ["存储", "计算", "网络", "数据库", "中间件", "应用"]},
                    "vendor": {"type": "string"},
                    "model": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price_wan": {"type": "number"},
                    "deployment_site": {"type": "string", "enum": ["生产站点", "灾备站点", "云端"]},
                }
            }
        },
        "network_topology": {"type": "string", "description": "网络拓扑描述"},
        "data_flow": {"type": "string", "description": "数据流向描述"},
    }
}

RISK_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["risk_id", "description", "probability", "impact", "mitigation"],
        "properties": {
            "risk_id": {"type": "string"},
            "description": {"type": "string"},
            "category": {"type": "string", "enum": ["技术风险", "运营风险", "外部风险"]},
            "probability": {"type": "string", "enum": ["高", "中", "低"]},
            "impact": {"type": "string", "enum": ["高", "中", "低"]},
            "risk_level": {"type": "string", "enum": ["严重", "高", "中", "低"]},
            "mitigation": {"type": "string"},
            "contingency": {"type": "string"},
        }
    }
}

COST_SCHEMA = {
    "type": "object",
    "required": ["hardware", "software", "service", "year3_ops", "total"],
    "properties": {
        "hardware": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "vendor": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price_wan": {"type": "number"},
                    "subtotal_wan": {"type": "number"},
                }
            }
        },
        "software": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "vendor": {"type": "string"},
                    "license_type": {"type": "string"},
                    "quantity": {"type": "integer"},
                    "unit_price_wan": {"type": "number"},
                    "subtotal_wan": {"type": "number"},
                }
            }
        },
        "service": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "scope": {"type": "string"},
                    "man_days": {"type": "integer"},
                    "daily_rate_wan": {"type": "number"},
                    "subtotal_wan": {"type": "number"},
                }
            }
        },
        "year1_total_wan": {"type": "number"},
        "year2_ops_wan": {"type": "number"},
        "year3_ops_wan": {"type": "number"},
        "total_wan": {"type": "number"},
        "total_yi": {"type": "number"},
    }
}

# 最终输出Schema
FINAL_REPORT_SCHEMA = {
    "type": "object",
    "required": ["project_info", "executive_summary", "bia", "gap_analysis", "dr_strategy", "architecture", "risk_assessment", "cost_estimate"],
    "properties": {
        "version": {"type": "string"},
        "generated_at": {"type": "string"},
        "project_info": PROJECT_INFO_SCHEMA,
        "executive_summary": {
            "type": "object",
            "properties": {
                "project_overview": {"type": "string"},
                "key_metrics": {
                    "type": "object",
                    "properties": {
                        "total_investment_yi": {"type": "number"},
                        "rto_achieved_minutes": {"type": "integer"},
                        "rpo_achieved_minutes": {"type": "integer"},
                        "payback_years": {"type": "number"},
                    }
                }
            }
        },
        "bia": {"$ref": "#/definitions/business_systems"},
        "gap_analysis": GAP_ANALYSIS_SCHEMA,
        "dr_strategy": DR_STRATEGY_SCHEMA,
        "architecture": ARCHITECTURE_SCHEMA,
        "risk_assessment": RISK_SCHEMA,
        "cost_estimate": COST_SCHEMA,
    }
}
