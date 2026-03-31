#!/usr/bin/env python3
"""三轮测试运行脚本"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ProDR_Writer'))

# 设置 API Key
os.environ.setdefault('MINIMAX_API_KEY', 'sk-cp-iNrczUohaMstNTucUakV00OS1nFGoWhk22XOhwoaVd6TPUhTpMVSxjkVfj1_mQJ8fC-UANgt-YySJci_T5jdVAAhBx0qwDYHEudPUVVANInLXAd6RqXo-zs')
os.environ.setdefault('MINIMAX_MODEL', 'MiniMax-M2.5')

from ProDR_Writer.crew_v3_final import DRCrewV3Final

inputs = {
    "project_name": "泰国Tune保险公司数据中心灾备建设项目",
    "company_name": "上海英方软件股份有限公司",
    "industry": "保险",
    "rto_requirement": "2小时",
    "rpo_requirement": "15分钟",
    "budget_range": "1500-2500万",
}

print("=" * 70)
print("项目: 泰国Tune保险公司数据中心灾备建设项目")
print("投标单位: 上海英方软件股份有限公司")
print("=" * 70)

crew = DRCrewV3Final()
result = crew.run(inputs)

print("\n" + "=" * 70)
print("最终结果:")
print(f"  状态: {result.get('status')}")
print(f"  优化轮次: {result.get('optimization_rounds')}")
print(f"  最终评分: {result.get('critic', {}).get('score', 'N/A')}/100")
doc_path = result.get('document', {}).get('data', {}).get('document_path', 'N/A')
print(f"  文档路径: {doc_path}")
print("=" * 70)
