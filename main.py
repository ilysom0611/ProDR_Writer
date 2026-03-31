#!/usr/bin/env python
"""
ProDR_Writer - 灾备技术方案自动生成系统 v1.0
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'ProDR_Writer'))

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

console = Console()
app = typer.Typer(help="🤖 ProDR_Writer 灾备技术方案自动生成系统 v1.0", no_args_is_help=True)


def check_api_key():
    api_key = os.environ.get('MINIMAX_API_KEY')
    if not api_key:
        console.print("[yellow]⚠️  未设置 MINIMAX_API_KEY[/yellow]")
        api_key = Prompt.ask("[bold cyan]请输入 MiniMax API Key[/bold cyan]", password=True)
        os.environ['MINIMAX_API_KEY'] = api_key


def get_interactive_inputs() -> dict:
    console.print("\n[bold cyan]📝 请填写项目信息[/bold cyan]\n")
    inputs = {}
    inputs["project_name"] = Prompt.ask("[bold]项目名称[/bold]",
        default="XX集团数据中心灾备建设项目")
    inputs["company_name"] = Prompt.ask("[bold]投标单位[/bold]",
        default="XX科技有限公司")
    inputs["industry"] = Prompt.ask("[bold]行业[/bold]",
        choices=["金融", "医疗", "政府", "教育", "制造", "零售", "保险", "其他"],
        default="金融")
    inputs["rto_requirement"] = Prompt.ask("[bold]RTO要求[/bold]",
        default="4小时")
    inputs["rpo_requirement"] = Prompt.ask("[bold]RPO要求[/bold]",
        default="15分钟")
    inputs["budget_range"] = Prompt.ask("[bold]预算范围[/bold]",
        default="2000-3000万")
    return inputs


def execute_workflow(inputs: dict):
    from ProDR_Writer.crew_v3_final import DRCrewV3Final
    crew = DRCrewV3Final()
    result = crew.run(inputs)
    if result.get("status") == "success":
        console.print("\n[bold green]✅ 生成完成！[/bold green]")
        console.print(f"📄 文档: {result.get('document', {}).get('document_path', 'N/A')}")
        console.print(f"🔄 优化轮次: {result.get('optimization_rounds', 1)}")
        console.print(f"📊 最终评分: {result.get('critic', {}).get('score', 'N/A')}/100")
    else:
        console.print("\n[bold red]❌ 生成失败[/bold red]")


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    ctx: typer.Context,
    interactive: bool = typer.Option(False, "--interactive", "-i", help="交互式输入"),
    project: str = typer.Option(None, "--project", "-p", help="项目名称"),
):
    """🚀 生成灾备技术方案

    示例:

        python main.py --project "XX集团数据中心灾备项目"

        python main.py --interactive

        python main.py info
    """
    console.print("\n")
    console.print("[bold cyan]╔══════════════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║       🤖  ProDR_Writer 灾备技术方案自动生成系统      ║[/bold cyan]")
    console.print("[bold cyan]║       🔄  多Agent协作 + 评审优化循环 + Word文档     ║[/bold cyan]")
    console.print("[bold cyan]╚══════════════════════════════════════════════════════╝[/bold cyan]")
    console.print("")

    check_api_key()

    if interactive or not project:
        inputs = get_interactive_inputs()
    else:
        inputs = {
            "project_name": project,
            "company_name": "XX科技有限公司",
            "industry": "金融",
            "rto_requirement": "4小时",
            "rpo_requirement": "15分钟",
            "budget_range": "2000-3000万",
        }

    console.print("\n[bold cyan]📋 项目信息[/bold cyan]")
    info_table = Table(show_header=False, box=None)
    for k, v in inputs.items():
        info_table.add_row(k, str(v))
    console.print(info_table)

    if not Confirm.ask("\n[bold yellow]确认开始生成？[/bold yellow]", default=True):
        console.print("[red]已取消[/red]")
        raise typer.Exit()

    execute_workflow(inputs)


@app.command()
def info():
    """ℹ️ 查看系统信息"""
    console.print("\n[bold cyan]📊 系统信息[/bold cyan]\n")
    table = Table(title="配置")
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")
    table.add_row("版本", "v1.0")
    table.add_row("LLM", os.environ.get('MINIMAX_MODEL', 'MiniMax-M2.5'))
    table.add_row("API Endpoint", os.environ.get('MINIMAX_API_BASE', 'https://api.minimax.io/v1'))
    table.add_row("API Key", "已配置" if os.environ.get('MINIMAX_API_KEY') else "未配置")
    console.print(table)


if __name__ == "__main__":
    app()
