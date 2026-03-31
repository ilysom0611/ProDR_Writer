"""
ProDR_Writer - 灾备技术方案 Crew
真正的多Agent职责分离架构
"""
import os
import json
import re
from typing import Dict, Any
from crewai import Agent, Crew, Task
from crewai.llm import LLM
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from tools.doc_writer import WordDocumentWriterTool


def get_llm():
    return LLM(
        model=os.environ.get('MINIMAX_MODEL', 'MiniMax-M2.5'),
        api_key=os.environ.get('MINIMAX_API_KEY', ''),
        base_url=os.environ.get('MINIMAX_API_BASE', 'https://api.minimax.io/v1'),
    )


def create_requirement_analyst():
    return Agent(
        role="业务需求分析师",
        goal="准确提取和结构化业务需求，不写任何描述性文档",
        backstory="资深需求分析师，精通BCM标准和RTO/RPO计算，只输出结构化JSON",
        verbose=True,
        llm=get_llm(),
    )


def create_dr_architect():
    return Agent(
        role="灾备架构设计师",
        goal="设计满足RTO/RPO要求的灾备架构，不写Word内容",
        backstory="15年灾备行业经验，精通各类灾备技术，只输出架构JSON",
        verbose=True,
        llm=get_llm(),
    )


def create_critic_agent():
    return Agent(
        role="方案评审专家",
        goal="严格评审架构，输出评分和问题清单，不参与文档生成",
        backstory="资深评审专家，只做评分和验收，不生成内容",
        verbose=True,
        llm=get_llm(),
    )


def create_optimizer_agent():
    return Agent(
        role="架构优化专家",
        goal="根据评审意见修复问题，不写任何文档",
        backstory="擅长架构优化，只输出优化后的架构JSON",
        verbose=True,
        llm=get_llm(),
    )


def create_writer_agent():
    return Agent(
        role="技术文档工程师",
        goal="将结构化JSON转换为专业投标Word文档内容，不直接生成文件",
        backstory="专业文档工程师，擅长将数据转化为结构化文档内容",
        verbose=True,
        llm=get_llm(),
    )


class DRCrewV3Final:

    def __init__(self):
        self.requirement_analyst = create_requirement_analyst()
        self.dr_architect = create_dr_architect()
        self.critic_agent = create_critic_agent()
        self.optimizer_agent = create_optimizer_agent()
        self.writer_agent = create_writer_agent()
        self.doc_tool = WordDocumentWriterTool()

    def run(self, inputs: Dict) -> Dict:
        print("\n" + "=" * 70)
        print("灾备方案生成系统 v1.0 - ProDR_Writer")
        print("=" * 70)

        # Step 1: BIA
        print("\nStep 1/7: BIA分析...")
        bia_data = self._run_bia(inputs)
        bia_status = "完成" if bia_data.get('status') == 'success' else '失败(使用默认)'
        bia_systems = bia_data.get('data', {}).get('business_systems', [])
        print(f"  → BIA {bia_status}，关键系统数: {len(bia_systems)}")

        # Step 2: 现状评估
        print("\nStep 2/7: 现状评估...")
        infra_data = self._run_infrastructure(inputs)
        print(f"  → 现状评估完成")

        # Step 3: 灾备策略设计
        print("\nStep 3/7: 灾备策略设计...")
        strategy_data = self._run_strategy(inputs, bia_data, infra_data)
        print(f"  → 灾备策略完成")

        # Step 4: 灾备架构设计
        print("\nStep 4/7: 灾备架构设计...")
        arch_data = self._run_architecture(inputs, bia_data, infra_data, strategy_data)
        print(f"  → 架构设计完成")

        # Step 5: 架构评审循环
        print("\nStep 5/7: 架构评审...")
        arch_data, critic_data, rounds = self._run_critic_loop(
            inputs, bia_data, infra_data, strategy_data, arch_data
        )
        print(f"  → 评审完成，轮次: {rounds}，评分: {critic_data.get('score', 'N/A')}/100")

        # Step 6: 生成文档（直接构建，不通过工具调用）
        print("\nStep 6/7: 生成文档...")
        doc_data = self._run_document(
            inputs, bia_data, infra_data, strategy_data, arch_data, critic_data
        )
        doc_path = doc_data.get('data', {}).get('document_path', 'N/A')
        print(f"  → 文档生成完成: {doc_path}")

        print("\n" + "=" * 70)
        print("灾备方案生成完成!")
        print("=" * 70)

        return {
            "status": "success",
            "bia": bia_data,
            "infrastructure": infra_data,
            "strategy": strategy_data,
            "architecture": arch_data,
            "critic": critic_data,
            "document": doc_data,
            "optimization_rounds": rounds
        }

    # ────────────────────────────────────────────────────────────────
    # Step 1: BIA
    # ────────────────────────────────────────────────────────────────
    def _run_bia(self, inputs: Dict) -> Dict:
        project_info = json.dumps(inputs, ensure_ascii=False)
        desc = (
            "## 任务：业务影响分析（BIA）\n\n"
            "### 项目信息\n"
            f"{project_info}\n\n"
            "请进行业务影响分析，识别关键业务系统，设定 RTO/RPO 要求，输出结构化 JSON。\n\n"
            "### 输出格式（严格输出 JSON，不输出其他内容）\n"
            '```json\n'
            "{\n"
            '  "status": "success",\n'
            '  "data": {\n'
            '    "business_systems": [\n'
            '      {\n'
            '        "name": "系统名称",\n'
            '        "tier": "P0/P1/P2/P3",\n'
            '        "rto": "目标恢复时间",\n'
            '        "rpo": "目标恢复点",\n'
            '        "criticality": "关键程度",\n'
            '        "max_downtime_impact": "停机影响"\n'
            '      }\n'
            "    ],\n"
            '    "overall_rto": "整体RTO",\n'
            '    "overall_rpo": "整体RPO",\n'
            '    "recovery_priority": ["按优先级排序的系统列表"]\n'
            "  }\n"
            "}\n"
            '```\n'
        )
        task = Task(
            description=desc,
            agent=self.requirement_analyst,
            expected_output='JSON格式的BIA分析结果，必须包含 business_systems、overall_rto、overall_rpo 等字段',
        )
        crew = Crew(agents=[self.requirement_analyst], tasks=[task])
        result = crew.kickoff()
        return self._parse_json(result)

    # ────────────────────────────────────────────────────────────────
    # Step 2: 现状评估
    # ────────────────────────────────────────────────────────────────
    def _run_infrastructure(self, inputs: Dict) -> Dict:
        project_info = json.dumps(inputs, ensure_ascii=False)
        desc = (
            "## 任务：现状评估与差距分析\n\n"
            "### 项目信息\n"
            f"{project_info}\n\n"
            "请对客户当前 IT 基础设施进行现状评估，识别灾备能力差距，输出结构化 JSON。\n\n"
            "### 输出格式（严格输出 JSON，不输出其他内容）\n"
            '```json\n'
            "{\n"
            '  "status": "success",\n'
            '  "data": {\n'
            '    "current_infrastructure": {\n'
            '      "compute": "计算资源现状",\n'
            '      "storage": "存储资源现状",\n'
            '      "network": "网络架构现状",\n'
            '      "application": "应用系统现状"\n'
            "    },\n"
            '    "gap_analysis": [\n'
            '      {\n'
            '        "area": "领域",\n'
            '        "current_capability": "当前能力",\n'
            '        "required_capability": "要求能力",\n'
            '        "gap": "差距描述",\n'
            '        "risk_level": "高/中/低"\n'
            "      }\n"
            "    ],\n"
            '    "summary": "总体评估结论"\n'
            "  }\n"
            "}\n"
            '```\n'
        )
        task = Task(
            description=desc,
            agent=self.requirement_analyst,
            expected_output='JSON格式的现状评估结果，必须包含 current_infrastructure、gap_analysis 等字段',
        )
        crew = Crew(agents=[self.requirement_analyst], tasks=[task])
        result = crew.kickoff()
        return self._parse_json(result)

    # ────────────────────────────────────────────────────────────────
    # Step 3: 灾备策略设计
    # ────────────────────────────────────────────────────────────────
    def _run_strategy(self, inputs: Dict, bia: Dict, infra: Dict) -> Dict:
        project_info = json.dumps(inputs, ensure_ascii=False)
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False)
        infra_data = json.dumps(infra.get('data', {}), ensure_ascii=False)
        desc = (
            "## 任务：灾备策略设计\n\n"
            "### 项目信息\n"
            f"{project_info}\n\n"
            "### BIA 分析结果\n"
            f"{bia_data}\n\n"
            "### 现状评估结果\n"
            f"{infra_data}\n\n"
            "请基于上述分析，设计完整的灾备策略，输出结构化 JSON。\n\n"
            "### 输出格式（严格输出 JSON，不输出其他内容）\n"
            '```json\n'
            "{\n"
            '  "status": "success",\n'
            '  "data": {\n'
            '    "dr_strategy": {\n'
            '      "protection_tiers": [\n'
            '        {\n'
            '          "tier": "P0/P1/P2/P3",\n'
            '          "protection_mode": "双活/热备/温备/冷备",\n'
            '          "replication": "同步/异步",\n'
            '          "failover": "自动/半自动/手动",\n'
            '          "rationale": "策略说明"\n'
            "        }\n"
            "      ],\n"
            '      "overall_strategy": "总体策略概述"\n'
            "    }\n"
            "  }\n"
            "}\n"
            '```\n'
        )
        task = Task(
            description=desc,
            agent=self.dr_architect,
            expected_output='JSON格式的灾备策略，必须包含 dr_strategy.protection_tiers 等字段',
        )
        crew = Crew(agents=[self.dr_architect], tasks=[task])
        result = crew.kickoff()
        return self._parse_json(result)

    # ────────────────────────────────────────────────────────────────
    # Step 4: 灾备架构设计
    # ────────────────────────────────────────────────────────────────
    def _run_architecture(self, inputs: Dict, bia: Dict, infra: Dict, strategy: Dict) -> Dict:
        project_info = json.dumps(inputs, ensure_ascii=False)
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False)
        infra_data = json.dumps(infra.get('data', {}), ensure_ascii=False)
        strategy_data = json.dumps(strategy.get('data', {}), ensure_ascii=False)
        desc = (
            "## 任务：灾备架构设计\n\n"
            "### 项目信息\n"
            f"{project_info}\n\n"
            "### BIA 分析结果\n"
            f"{bia_data}\n\n"
            "### 现状评估结果\n"
            f"{infra_data}\n\n"
            "### 灾备策略\n"
            f"{strategy_data}\n\n"
            "### 设计约束（必须严格遵守）\n"
            "- P0 系统：RPO=0（同步复制），RTO<30分钟，禁止使用备份恢复作为主策略\n"
            "- P1 系统：RPO≤1分钟，RTO<1小时，热备架构\n"
            "- P2 系统：RPO≤15分钟，RTO<4小时，温备架构\n"
            "- P3 系统：RPO≤1小时，RTO≤24小时，冷备/备份恢复\n\n"
            "### 输出格式（严格输出 JSON，不输出其他内容）\n"
            '```json\n'
            "{\n"
            '  "status": "success",\n'
            '  "data": {\n'
            '    "architecture": {\n'
            '      "deployment_mode": "部署模式（双活/主备等）",\n'
            '      "primary_site": {"name": "主站点", "location": "位置"},\n'
            '      "dr_site": {"name": "灾备站点", "location": "位置"},\n'
            '      "tier_definitions": {\n'
            '        "P0": {"systems": [], "recovery_strategy": "双活", "rpo": "0", "rto": "<30min", "replication": "同步", "failover": "自动", "description": "说明"},\n'
            '        "P1": {"systems": [], "recovery_strategy": "热备", "rpo": "≤1min", "rto": "<1h", "replication": "同步", "failover": "自动", "description": "说明"},\n'
            '        "P2": {"systems": [], "recovery_strategy": "温备", "rpo": "≤15min", "rto": "<4h", "replication": "异步", "failover": "半自动", "description": "说明"},\n'
            '        "P3": {"systems": [], "recovery_strategy": "冷备", "rpo": "≤1h", "rto": "≤24h", "replication": "异步", "failover": "手动", "description": "说明"}\n'
            "      },\n"
            '      "network_architecture": "网络架构说明",\n'
            '      "storage_architecture": "存储架构说明",\n'
            '      "compute_architecture": "计算架构说明",\n'
            '      "failover_automation": "自动切换设计"\n'
            "    }\n"
            "  }\n"
            "}\n"
            '```\n'
        )
        task = Task(
            description=desc,
            agent=self.dr_architect,
            expected_output='JSON格式的完整灾备架构，必须包含 architecture.tier_definitions 等字段',
        )
        crew = Crew(agents=[self.dr_architect], tasks=[task])
        result = crew.kickoff()
        return self._parse_json(result)

    # ────────────────────────────────────────────────────────────────
    # Step 5: 评审循环
    # ────────────────────────────────────────────────────────────────
    def _run_critic_loop(
        self, inputs: Dict, bia: Dict, infra: Dict, strategy: Dict, arch: Dict
    ) -> tuple:
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False)
        strategy_data = json.dumps(strategy.get('data', {}), ensure_ascii=False)
        arch_data = json.dumps(arch.get('data', {}), ensure_ascii=False)
        project_info = json.dumps(inputs, ensure_ascii=False)

        critic_data = {}
        current_arch = arch

        for round_num in range(1, 4):
            print(f"\n  --- 评审轮次 {round_num}/3 ---")
            critic_desc = (
                "## 任务：评审灾备架构方案\n\n"
                "### 项目信息\n"
                f"{project_info}\n\n"
                "### BIA 需求\n"
                f"{bia_data}\n\n"
                "### 灾备策略\n"
                f"{strategy_data}\n\n"
                "### 待评审架构\n"
                f"{arch_data}\n\n"
                "请严格按照以下维度打分：\n"
                "1. 技术可行性（权重20%）\n"
                "2. 架构合理性（权重20%）\n"
                "3. 性能与扩展性（权重15%）\n"
                "4. 安全与合规（权重15%）\n"
                "5. 成本效益（权重15%）\n"
                "6. 实施风险（权重15%）\n\n"
                "### 输出格式（严格输出 JSON，不输出其他内容）\n"
                '```json\n'
                "{\n"
                '  "score": <0-100整数>,\n'
                '  "can_proceed": <true或false，score>=60为true>,\n'
                '  "dimension_scores": {\n'
                '    "技术可行性": {"score": <0-100>, "reason": "评分理由"},\n'
                '    "架构合理性": {"score": <0-100>, "reason": "评分理由"},\n'
                '    "性能与扩展性": {"score": <0-100>, "reason": "评分理由"},\n'
                '    "安全与合规": {"score": <0-100>, "reason": "评分理由"},\n'
                '    "成本效益": {"score": <0-100>, "reason": "评分理由"},\n'
                '    "实施风险": {"score": <0-100>, "reason": "评分理由"}\n'
                "  },\n"
                '  "issues": [\n'
                '    {"severity": "阻塞/严重/一般", "description": "问题描述", "suggestion": "修复建议"}\n'
                "  ],\n"
                '  "summary": "总体评审意见"\n'
                "}\n"
                '```\n'
            )
            critic_task = Task(
                description=critic_desc,
                agent=self.critic_agent,
                expected_output='JSON格式的评审结果，必须包含 score(0-100)、can_proceed(true/false)、dimension_scores、issues 等字段',
            )
            crew = Crew(agents=[self.critic_agent], tasks=[critic_task])
            result = crew.kickoff()
            critic_data = self._parse_json(result)

            score = critic_data.get('score', 0)
            can_proceed = critic_data.get('can_proceed', False)
            print(f"  → 评分: {score}/100，{'✅ 通过' if can_proceed else '❌ 不通过'}")

            if can_proceed:
                return current_arch, critic_data, round_num

            if round_num >= 3:
                print("  → 达到最大评审轮次（3轮），强制进入文档生成")
                break

            # 优化 prompt
            issues = json.dumps(critic_data.get('issues', []), ensure_ascii=False)
            opt_desc = (
                "## 任务：根据评审意见优化灾备架构\n\n"
                "### 当前架构\n"
                f"{arch_data}\n\n"
                "### 评审意见\n"
                f"{issues}\n\n"
                "### 设计约束（不可违背）\n"
                "- P0 系统：RPO=0（同步复制），RTO<30分钟，禁止备份恢复\n"
                "- P1 系统：RPO≤1分钟，RTO<1小时\n"
                "- P2 系统：RPO≤15分钟，RTO<4小时\n"
                "- P3 系统：RPO≤1小时，RTO≤24小时\n\n"
                "### 输出格式（严格输出 JSON，不输出其他内容）\n"
                '```json\n'
                "{\n"
                '  "optimized_architecture": { <优化后的完整架构JSON> },\n'
                '  "changes": ["变更1", "变更2", ...],\n'
                '  "reason": "优化说明"\n'
                "}\n"
                '```\n'
            )
            opt_task = Task(
                description=opt_desc,
                agent=self.optimizer_agent,
                expected_output='JSON格式的优化结果，必须包含 optimized_architecture 字段',
            )
            crew = Crew(agents=[self.optimizer_agent], tasks=[opt_task])
            result = crew.kickoff()
            opt_data = self._parse_json(result)

            if opt_data.get('optimized_architecture'):
                current_arch = {'data': {'architecture': opt_data['optimized_architecture']}}
                print(f"  → 架构已优化，变更: {', '.join(opt_data.get('changes', []))}")
            else:
                print(f"  → 优化器未提供有效架构: {opt_data.get('reason', '未知原因')}")

        return current_arch, critic_data, round_num

    # ────────────────────────────────────────────────────────────────
    # Step 6: 生成文档（直接从上游数据构建，不通过工具调用）
    # ────────────────────────────────────────────────────────────────
    def _run_document(
        self, inputs: Dict, bia: Dict, infra: Dict,
        strategy: Dict, arch: Dict, critic: Dict
    ) -> Dict:
        import textwrap
        from datetime import datetime

        bia_d = bia.get('data', {})
        infra_d = infra.get('data', {})
        strategy_d = strategy.get('data', {})
        arch_d = arch.get('data', {})
        arch_full = arch_d.get('architecture', {})
        critic_score = critic.get('score', 'N/A')
        critic_summary = critic.get('summary', '')

        # 提取 BIA 系统列表
        business_systems = bia_d.get('business_systems', [])

        # 提取差距分析
        gap_analysis = infra_d.get('gap_analysis', [])
        current_infra = infra_d.get('current_infrastructure', {})

        # 提取分层策略
        dr_strategy = strategy_d.get('dr_strategy', {})
        protection_tiers = dr_strategy.get('protection_tiers', [])

        # 提取架构
        tier_defs = arch_full.get('tier_definitions', {})
        net_arch = arch_full.get('network_architecture', '')
        stor_arch = arch_full.get('storage_architecture', '')
        compute_arch = arch_full.get('compute_architecture', '')
        failover = arch_full.get('failover_automation', '')

        # 准备文档内容
        project_name = inputs.get('project_name', '灾备技术方案')
        company_name = inputs.get('company_name', 'XX科技有限公司')
        industry = inputs.get('industry', '金融')
        date_str = datetime.now().strftime('%Y年%m月%d日')

        # 调用文档工具直接构建
        content = {
            'project_name': project_name,
            'company_name': company_name,
            'industry': industry,
            'date': date_str,
            'sections': []
        }

        # ========== 章节 1: 执行摘要 ==========
        summary_text = textwrap.dedent(f"""\
            本灾备技术方案针对 {project_name} 进行系统性设计。
            投标单位：{company_name}，行业：{industry}。

            本方案基于业务影响分析（BIA）结果，对 {len(business_systems)} 个关键业务系统进行了分层保护设计，
            其中 P0 系统 {len(tier_defs.get('P0', {}).get('systems', []))} 个，
            P1 系统 {len(tier_defs.get('P1', {}).get('systems', []))} 个，
            P2 系统 {len(tier_defs.get('P2', {}).get('systems', []))} 个，
            P3 系统 {len(tier_defs.get('P3', {}).get('systems', []))} 个。

            架构评审得分：{critic_score}/100。
            {critic_summary}
        """).strip()
        content['sections'].append({
            'title': '第一章 执行摘要',
            'content': [{'type': 'text', 'text': summary_text}]
        })

        # ========== 章节 2: 项目概述 ==========
        overview_text = textwrap.dedent(f"""\
            {project_name}旨在建设一套完整的灾备体系，确保在灾难发生时业务连续性得到有效保障。

            本方案覆盖以下范围：
            一、数据中心灾备架构设计与实施
            二、灾备策略制定与验证
            三、灾备自动化切换机制建设
            四、灾备运维管理体系建立

            目标：
            一、建立符合行业标准的灾备体系
            二、实现核心业务 RTO≤4小时，RPO≤15分钟
            三、建立自动化的灾备切换能力
            四、通过定期演练验证灾备系统有效性
        """).strip()
        content['sections'].append({
            'title': '第二章 项目概述',
            'content': [{'type': 'text', 'text': overview_text}]
        })

        # ========== 章节 3: 需求分析 ==========
        # BIA 部分
        bia_text_lines = [f"根据业务影响分析，共识别 {len(business_systems)} 个关键业务系统："]
        for sys in business_systems:
            bia_text_lines.append(
                f"• {sys.get('name', '')}（{sys.get('tier', '')}）"
                f" | RTO: {sys.get('rto', '')} | RPO: {sys.get('rpo', '')}"
                f" | 关键程度: {sys.get('criticality', '')}"
            )
        bia_text = '\n'.join(bia_text_lines)

        # 差距分析表格
        gap_rows = [['领域', '当前能力', '要求能力', '差距', '风险等级']]
        for g in gap_analysis:
            gap_rows.append([
                g.get('area', ''),
                g.get('current_capability', ''),
                g.get('required_capability', ''),
                g.get('gap', ''),
                g.get('risk_level', '')
            ])

        content['sections'].append({
            'title': '第三章 需求分析',
            'content': [
                {'type': 'heading', 'text': '3.1 业务影响分析（BIA）'},
                {'type': 'text', 'text': bia_text},
                {'type': 'heading', 'text': '3.2 现状评估'},
                {'type': 'text', 'text': f"计算资源：{current_infra.get('compute', 'N/A')}\n"
                                          f"存储资源：{current_infra.get('storage', 'N/A')}\n"
                                          f"网络架构：{current_infra.get('network', 'N/A')}\n"
                                          f"应用系统：{current_infra.get('application', 'N/A')}"},
                {'type': 'heading', 'text': '3.3 差距分析'},
                {'type': 'table', 'rows': gap_rows},
            ]
        })

        # ========== 章节 4: 灾备方案设计 ==========
        strategy_text = f"总体策略：{dr_strategy.get('overall_strategy', 'N/A')}\n\n"
        for tier_info in protection_tiers:
            tier_text = (
                f"• {tier_info.get('tier', '')} 系统："
                f"保护模式 {tier_info.get('protection_mode', '')}，"
                f"复制方式 {tier_info.get('replication', '')}，"
                f"切换方式 {tier_info.get('failover', '')}。"
            )
            if tier_info.get('rationale'):
                tier_text += f" {tier_info.get('rationale', '')}"
            strategy_text += tier_text + '\n'

        # 架构表格
        arch_rows = [['优先级', '系统数量', '恢复策略', 'RPO', 'RTO', '复制方式', '切换方式']]
        for tier in ['P0', 'P1', 'P2', 'P3']:
            td = tier_defs.get(tier, {})
            arch_rows.append([
                tier,
                str(len(td.get('systems', []))),
                td.get('recovery_strategy', ''),
                td.get('rpo', ''),
                td.get('rto', ''),
                td.get('replication', ''),
                td.get('failover', '')
            ])

        content['sections'].append({
            'title': '第四章 灾备方案设计',
            'content': [
                {'type': 'heading', 'text': '4.1 分层保护策略'},
                {'type': 'text', 'text': strategy_text},
                {'type': 'heading', 'text': '4.2 架构设计'},
                {'type': 'table', 'rows': arch_rows},
                {'type': 'heading', 'text': '4.3 网络架构'},
                {'type': 'text', 'text': net_arch or 'N/A'},
                {'type': 'heading', 'text': '4.4 存储架构'},
                {'type': 'text', 'text': stor_arch or 'N/A'},
                {'type': 'heading', 'text': '4.5 计算架构'},
                {'type': 'text', 'text': compute_arch or 'N/A'},
                {'type': 'heading', 'text': '4.6 自动切换设计'},
                {'type': 'text', 'text': failover or 'N/A'},
            ]
        })

        # ========== 章节 5: 投资估算 ==========
        budget_range = inputs.get('budget_range', 'N/A')
        budget_text = textwrap.dedent(f"""\
            本项目预算范围：{budget_range}。

            投资估算说明：
            一、P0 系统（占比约40%）：包括双活存储、小型机集群、专用网络等
            二、P1 系统（占比约30%）：包括热备存储、同步复制许可、虚拟化资源等
            三、P2 系统（占比约20%）：包括温备存储、异步复制、平台软件等
            四、P3 系统（占比约10%）：包括备份软件、介质、恢复工具等
            五、项目管理与实施费用：约占总预算的10-15%

            具体分项报价待详细设计后提供。
        """).strip()
        content['sections'].append({
            'title': '第五章 投资估算',
            'content': [{'type': 'text', 'text': budget_text}]
        })

        # ========== 章节 6: 风险评估 ==========
        issues = critic.get('issues', [])
        risk_rows = [['严重程度', '问题描述', '修复建议']]
        for issue in issues:
            risk_rows.append([
                issue.get('severity', ''),
                issue.get('description', ''),
                issue.get('suggestion', '')
            ])

        content['sections'].append({
            'title': '第六章 风险评估',
            'content': [
                {'type': 'text', 'text': f"架构评审共发现问题 {len(issues)} 项，具体如下："},
                {'type': 'table', 'rows': risk_rows},
            ]
        })

        # ========== 章节 7: 附录 ==========
        appendix_text = (
            "一、投标人营业执照及相关资质证书\n"
            "二、同类项目成功案例清单\n"
            "三、技术团队资质证明\n"
            "四、售后服务承诺书\n"
            "五、保修期服务说明"
        )
        content['sections'].append({
            'title': '第七章 附录',
            'content': [{'type': 'text', 'text': appendix_text}]
        })

        # 调用文档工具生成文件
        os.makedirs('outputs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"outputs/{project_name}_{timestamp}.docx"
        try:
            self.doc_tool.run(content=content, output_path=output_path)
            return {"status": "success", "data": {"document_path": output_path}}
        except Exception as e:
            print(f"  ⚠️ 文档生成失败: {e}")
            return {"status": "error", "data": {"document_path": None}}

    # ────────────────────────────────────────────────────────────────
    # JSON 解析工具
    # ────────────────────────────────────────────────────────────────
    def _parse_json(self, output) -> Dict:
        try:
            text = str(output)
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            text = text.replace('```json', '').replace('```', '').strip()

            start = text.find('{')
            if start == -1:
                start = text.find('[')
            if start == -1:
                return {"status": "error", "data": {}}

            depth = 0
            in_string = False
            escape = False
            end = start
            for i in range(start, len(text)):
                ch = text[i]
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{' or ch == '[':
                    depth += 1
                elif ch == '}' or ch == ']':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            text = text[start:end]
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"  ⚠️ JSON解析失败: {e}，提取内容前200字: {text[:200]}")
            return {"status": "error", "data": {}}
        except Exception as e:
            print(f"  ⚠️ 解析异常: {e}")
            return {"status": "error", "data": {}}
