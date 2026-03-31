"""
灾备技术方案 Crew v3.0 FINAL
真正的多Agent职责分离架构 — 完整上下文传递版
"""

import os
import json
from typing import Dict, Any, Optional, List
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
        goal="将结构化JSON转换为专业投标Word文档",
        backstory="专业文档工程师，唯一被允许生成Word文档的Agent",
        verbose=True,
        llm=get_llm(),
        tools=[WordDocumentWriterTool()]
    )


class DRCrewV3Final:
    """
    真正的多Agent职责分离系统
    关键：每个Task的description包含完整的上下游数据作为上下文
    """

    def __init__(self):
        self.requirement_analyst = create_requirement_analyst()
        self.dr_architect = create_dr_architect()
        self.critic_agent = create_critic_agent()
        self.optimizer_agent = create_optimizer_agent()
        self.writer_agent = create_writer_agent()

    def run(self, inputs: Dict) -> Dict:
        print("\n" + "=" * 70)
        print("灾备方案生成系统 v3.0 FINAL")
        print("真正的多Agent职责分离架构")
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

        # Step 6: 生成文档
        print("\nStep 6/7: 生成文档...")
        doc_data = self._run_document(inputs, bia_data, infra_data, strategy_data, arch_data, critic_data)
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
        project_info = json.dumps(inputs, ensure_ascii=False, indent=2)
        desc = f"""
## 任务：业务影响分析（BIA）

### 项目信息
{project_info}

请进行业务影响分析，识别关键业务系统，设定 RTO/RPO 要求，输出结构化 JSON。

### 输出格式（必须严格遵循，仅输出 JSON）
{{
  "status": "success",
  "data": {{
    "analysis": "一行简短分析说明（中文）",
    "business_systems": [
      {{
        "name": "系统名称",
        "tier": "P0/P1/P2/P3",
        "rto": "目标恢复时间",
        "rpo": "目标恢复点",
        "criticality": "关键程度",
        "max_downtime_impact": "停机影响"
      }}
    ],
    "overall_rto": "整体RTO",
    "overall_rpo": "整体RPO",
    "recovery_priority": ["按优先级排序的系统列表"]
  }}
}}

### 要求
- 严格输出 JSON，不输出其他内容（禁止在 JSON 前添加任何说明文字）
"""
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
        project_info = json.dumps(inputs, ensure_ascii=False, indent=2)
        desc = f"""
## 任务：现状评估与差距分析

### 项目信息
{project_info}

请对客户当前 IT 基础设施进行现状评估，识别灾备能力差距，输出结构化 JSON。

### 输出格式
{{
  "status": "success",
  "data": {{
    "current_infrastructure": {{
      "compute": "计算资源现状",
      "storage": "存储资源现状",
      "network": "网络架构现状",
      "application": "应用系统现状"
    }},
    "gap_analysis": [
      {{
        "area": "领域",
        "current_capability": "当前能力",
        "required_capability": "要求能力",
        "gap": "差距描述",
        "risk_level": "高/中/低"
      }}
    ],
    "summary": "总体评估结论"
  }}
}}

### 要求
- 严格输出 JSON，不输出其他内容
"""
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
        project_info = json.dumps(inputs, ensure_ascii=False, indent=2)
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False, indent=2)
        infra_data = json.dumps(infra.get('data', {}), ensure_ascii=False, indent=2)
        desc = f"""
## 任务：灾备策略设计

### 项目信息
{project_info}

### BIA 分析结果（来自需求分析师）
{bia_data}

### 现状评估结果（来自需求分析师）
{infra_data}

请基于上述分析，设计完整的灾备策略，输出结构化 JSON。

### 输出格式
{{
  "status": "success",
  "data": {{
    "dr_strategy": {{
      "protection_tiers": [
        {{
          "tier": "P0/P1/P2/P3",
          "protection_mode": "双活/热备/温备/冷备",
          "replication": "同步/异步",
          "failover": "自动/半自动/手动",
          "rationale": "策略说明"
        }}
      ],
      "overall_strategy": "总体策略概述",
      "replication_direction": "主→备复制方向",
      "failover_trigger": "切换触发条件"
    }}
  }}
}}

### 要求
- 严格输出 JSON，不输出其他内容
"""
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
        project_info = json.dumps(inputs, ensure_ascii=False, indent=2)
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False, indent=2)
        infra_data = json.dumps(infra.get('data', {}), ensure_ascii=False, indent=2)
        strategy_data = json.dumps(strategy.get('data', {}), ensure_ascii=False, indent=2)
        desc = f"""
## 任务：灾备架构设计

### 项目信息
{project_info}

### BIA 分析结果
{bia_data}

### 现状评估结果
{infra_data}

### 灾备策略
{strategy_data}

### 设计约束（必须严格遵守）
- P0 系统：RPO=0（同步复制），RTO<30分钟，禁止使用备份恢复作为主策略
- P1 系统：RPO≤1分钟，RTO<1小时，热备架构
- P2 系统：RPO≤15分钟，RTO<4小时，温备架构
- P3 系统：RPO≤1小时，RTO≤24小时，冷备/备份恢复

### 输出格式
{{
  "status": "success",
  "data": {{
    "architecture": {{
      "deployment_mode": "部署模式（双活/主备等）",
      "primary_site": {{ "name": "主站点", "location": "位置" }},
      "dr_site": {{ "name": "灾备站点", "location": "位置" }},
      "tier_definitions": {{
        "P0": {{ "systems": [], "recovery_strategy": "双活", "rpo": "0", "rto": "<30min", "replication": "同步", "failover": "自动" }},
        "P1": {{ "systems": [], "recovery_strategy": "热备", "rpo": "≤1min", "rto": "<1h", "replication": "同步", "failover": "自动" }},
        "P2": {{ "systems": [], "recovery_strategy": "温备", "rpo": "≤15min", "rto": "<4h", "replication": "异步", "failover": "半自动" }},
        "P3": {{ "systems": [], "recovery_strategy": "冷备", "rpo": "≤1h", "rto": "≤24h", "replication": "异步", "failover": "手动" }}
      }},
      "network_architecture": "网络架构说明",
      "storage_architecture": "存储架构说明",
      "compute_architecture": "计算架构说明",
      "failover_automation": "自动切换设计"
    }}
  }}
}}

### 要求
- 严格输出 JSON，不输出其他内容
- 架构必须满足上述设计约束
"""
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
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False, indent=2)
        strategy_data = json.dumps(strategy.get('data', {}), ensure_ascii=False, indent=2)
        arch_data = json.dumps(arch.get('data', {}), ensure_ascii=False, indent=2)
        project_info = json.dumps(inputs, ensure_ascii=False, indent=2)

        critic_data = {}
        current_arch = arch

        for round_num in range(1, 4):
            print(f"\n  --- 评审轮次 {round_num}/3 ---")
            # 评分 prompt：注入架构上下文
            critic_desc = f"""
## 任务：评审灾备架构方案

### 项目信息
{project_info}

### BIA 需求
{bia_data}

### 灾备策略
{strategy_data}

### 待评审架构
{arch_data}

请严格按照以下维度打分：
1. 技术可行性（权重20%）
2. 架构合理性（权重20%）
3. 性能与扩展性（权重15%）
4. 安全与合规（权重15%）
5. 成本效益（权重15%）
6. 实施风险（权重15%）

### 输出格式
{{
  "score": <0-100整数>,
  "can_proceed": <true或false，score>=60为true>,
  "dimension_scores": {{
    "技术可行性": {{ "score": <0-100>, "reason": "评分理由" }},
    "架构合理性": {{ "score": <0-100>, "reason": "评分理由" }},
    "性能与扩展性": {{ "score": <0-100>, "reason": "评分理由" }},
    "安全与合规": {{ "score": <0-100>, "reason": "评分理由" }},
    "成本效益": {{ "score": <0-100>, "reason": "评分理由" }},
    "实施风险": {{ "score": <0-100>, "reason": "评分理由" }}
  }},
  "issues": [
    {{ "severity": "阻塞/严重/一般", "description": "问题描述", "suggestion": "修复建议" }}
  ],
  "summary": "总体评审意见"
}}

### 要求
- 严格输出 JSON，不输出其他内容
- can_proceed=true 时才会进入文档生成阶段
"""
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

            # 优化 prompt：注入架构 + 评审意见
            issues = json.dumps(critic_data.get('issues', []), ensure_ascii=False, indent=2)
            opt_desc = f"""
## 任务：根据评审意见优化灾备架构

### 当前架构
{arch_data}

### 评审意见
{issues}

### 设计约束（不可违背）
- P0 系统：RPO=0（同步复制），RTO<30分钟，禁止备份恢复
- P1 系统：RPO≤1分钟，RTO<1小时
- P2 系统：RPO≤15分钟，RTO<4小时
- P3 系统：RPO≤1小时，RTO≤24小时

请根据上述评审意见优化架构，输出 JSON。

### 输出格式
{{
  "optimized_architecture": {{ <优化后的完整架构JSON> }},
  "changes": ["变更1", "变更2", ...],
  "reason": "优化说明"
}}

### 要求
- 严格输出 JSON，不输出其他内容
"""
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
    # Step 6: 生成文档
    # ────────────────────────────────────────────────────────────────


    # ────────────────────────────────────────────────────────────────
    # Step 6: 生成文档
    # ────────────────────────────────────────────────────────────────
    def _run_document(self, inputs: Dict, bia: Dict, infra: Dict,
                       strategy: Dict, arch: Dict, critic: Dict) -> Dict:
        import textwrap
        project_info = json.dumps(inputs, ensure_ascii=False)
        bia_data = json.dumps(bia.get('data', {}), ensure_ascii=False)
        infra_data = json.dumps(infra.get('data', {}), ensure_ascii=False)
        strategy_data = json.dumps(strategy.get('data', {}), ensure_ascii=False)
        arch_data = json.dumps(arch.get('data', {}), ensure_ascii=False)
        critic_data = json.dumps({
            'score': critic.get('score', 'N/A'),
            'dimension_scores': critic.get('dimension_scores', {}),
            'issues': critic.get('issues', []),
            'summary': critic.get('summary', '')
        }, ensure_ascii=False)

        # 使用 textwrap.dedent 避免 f-string 中的 {}} 冲突
        desc = textwrap.dedent(f"""
            ## 任务：根据以下所有分析数据，生成完整的灾备技术方案 Word 文档

            ### 项目基本信息
            {project_info}

            ### BIA 业务影响分析结果
            {bia_data}

            ### 现状评估与差距分析
            {infra_data}

            ### 灾备策略设计
            {strategy_data}

            ### 灾备架构设计
            {arch_data}

            ### 架构评审结果
            {critic_data}

            ### 文档生成要求

            调用 WordDocumentWriterTool 来生成 Word 文档，参数如下：

            content 参数（JSON 格式）:
              - project_name: 项目名称（字符串）
              - company_name: 投标单位（字符串）
              - industry: 行业（字符串）
              - date: 日期（字符串）
              - sections: 章节列表，每个章节包含：
                  - title: 章节标题
                  - content: 内容列表，每项为 type + text

            output_path: "outputs/灾备技术方案.docx"

            **重要：直接调用工具，不要传递整个任务描述作为 content！**

            ### 输出格式
            完成后直接输出 JSON（不要添加其他文字）：
            {{"status": "success", "data": {{"document_path": "<output_path的值>"}}}}
        """).strip()

        task = Task(
            description=desc,
            agent=self.writer_agent,
            expected_output='JSON格式结果，必须包含 document_path 字段，指向生成的 .docx 文件',
        )
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                crew = Crew(agents=[self.writer_agent], tasks=[task])
                result = crew.kickoff()
                return self._parse_json(result)
            except Exception as e:
                last_error = e
                print(f"  ⚠️ 文档生成尝试 {attempt+1}/{max_retries} 失败: {type(e).__name__}: {str(e)[:100]}")
                if attempt < max_retries - 1:
                    import time
                    wait = (attempt + 1) * 15
                    print(f"  → 等待 {wait} 秒后重试...")
                    time.sleep(wait)
        print(f"  ⚠️ 文档生成最终失败: {last_error}")
        return {"status": "error", "data": {"document_path": None}}

    def _parse_json(self, output) -> Dict:
        try:
            text = str(output)
            # 移除 MiniMax 思考标记
            import re
            text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
            # 移除代码块标记
            text = text.replace('```json', '').replace('```', '').strip()

            # 括号计数法：找从第一个 { 开始的完整 JSON 对象/数组
            start = text.find('{')
            if start == -1:
                start = text.find('[')
            if start == -1:
                return {"status": "error", "data": {}}

            # 找到完整闭合的括号
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
