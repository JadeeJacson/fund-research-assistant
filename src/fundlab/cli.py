from __future__ import annotations

import argparse
import json
from pathlib import Path

from fundlab.ai import EvidenceAnalysisOrchestrator, build_llm_provider
from fundlab.config import Settings
from fundlab.providers import AKShareFundProvider
from fundlab.services import FundResearchService, PortfolioService
from fundlab.storage import Database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="个人基金研究辅助系统")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="初始化本地 SQLite 数据库")

    analyze = subparsers.add_parser("analyze", help="分析一只公募基金")
    analyze.add_argument("fund_code", help="六位基金代码")
    analyze.add_argument("--ai", action="store_true", help="同时运行证据 AI 分析")
    analyze.add_argument("--no-refresh", action="store_true", help="只使用本地缓存")

    import_transactions = subparsers.add_parser(
        "import-transactions", help="导入支付宝人工整理的交易 CSV"
    )
    import_transactions.add_argument("csv_path")

    subparsers.add_parser("ai-check", help="检查当前 DeepSeek/Mock 配置")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = Path.cwd()
    settings = Settings.from_env(root)
    database = Database(settings.database_path)
    database.initialize()

    if args.command == "init-db":
        print(f"数据库已初始化：{settings.database_path}")
        return
    if args.command == "ai-check":
        provider = build_llm_provider(settings)
        ok, message = provider.health_check()
        print(
            json.dumps(
                {"ok": ok, "provider": provider.name, "message": message}, ensure_ascii=False
            )
        )
        return
    if args.command == "import-transactions":
        inserted, duplicates = PortfolioService(database).import_csv(args.csv_path)
        print(json.dumps({"inserted": inserted, "duplicates": duplicates}, ensure_ascii=False))
        return
    if args.command == "analyze":
        provider = build_llm_provider(settings)
        orchestrator = EvidenceAnalysisOrchestrator(provider, database, settings)
        service = FundResearchService(
            AKShareFundProvider(), database, settings, ai_orchestrator=orchestrator
        )
        report = service.analyze(args.fund_code, refresh=not args.no_refresh, include_ai=args.ai)
        print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
