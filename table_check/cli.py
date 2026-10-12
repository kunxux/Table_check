"""
命令行入口
==========
提供 analyze / check / chain / list-rules 四个子命令。

用法示例:
  # 分析表格结构
  python -m table_check.cli analyze 道具表.xlsx

  # 单规则校验
  python -m table_check.cli check 道具表.xlsx --rule not_null --config '{"columns":["id","name"]}'

  # 链式校验
  python -m table_check.cli chain --config demo_chain.json --output report.xlsx

  # 列出所有规则
  python -m table_check.cli list-rules
"""

import argparse
import json
import sys
from pathlib import Path

from .core.table_loader import TableLoader
from .core.report_generator import ReportGenerator
from .core.rule_base import registry

# 导入所有规则以触发注册（必须保留，尽管看似未使用）
from .rules import cell_rules          # noqa: F401
from .rules import column_rules        # noqa: F401
from .rules import cross_table_rules   # noqa: F401
from .rules import aggregation_rules   # noqa: F401
from .rules import diff_rules          # noqa: F401


def main():
    parser = argparse.ArgumentParser(
        prog="table-check",
        description="TableCheck — 游戏配表自动化校验工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  table-check analyze 道具表.xlsx
  table-check check 道具表.xlsx --rule not_null --config '{"columns":["id","name"]}'
  table-check chain --config my_chain.json --output report.xlsx
  table-check list-rules
        """,
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    # ── analyze ──
    ap = sub.add_parser("analyze", help="分析表格: 列名、类型、关键字")
    ap.add_argument("file", help="表格文件路径 (.xlsx / .csv)")
    ap.add_argument("--sheet", help="Sheet 名称 (仅 Excel)")

    # ── check ──
    cp = sub.add_parser("check", help="单规则校验")
    cp.add_argument("file", help="表格文件路径")
    cp.add_argument("--rule", required=True, help="规则名称")
    cp.add_argument("--config", default="{}", help="规则配置 JSON 字符串")
    cp.add_argument("--output", default="report.xlsx", help="报告输出路径")

    # ── chain ──
    chp = sub.add_parser("chain", help="链式校验（JSON 配置文件）")
    chp.add_argument("--config", required=True, help="链配置 JSON 文件路径")
    chp.add_argument("--output", default="chain_report.xlsx", help="报告输出路径")

    # ── list-rules ──
    sub.add_parser("list-rules", help="列出全部可用规则")

    args = parser.parse_args()

    # ──────────────────────────────
    # 执行
    # ──────────────────────────────

    if args.command == "analyze":
        _cmd_analyze(args)

    elif args.command == "check":
        _cmd_check(args)

    elif args.command == "chain":
        _cmd_chain(args)

    elif args.command == "list-rules":
        _cmd_list_rules()

    else:
        parser.print_help()


# ──────────────────────────────
# 命令实现
# ──────────────────────────────

def _cmd_analyze(args):
    info = TableLoader.analyze(args.file, args.sheet)
    print(f"\n📊 表格分析: {info.name}")
    print(f"   路径: {info.file_path}")
    print(f"   行数: {info.total_rows}  列数: {info.total_columns}\n")
    print(f"   {'列名':<22} {'类型':<10} {'空值率':>7} {'唯一值':>7}  {'关键字'}")
    print(f"   {'─'*60}")
    for col in info.columns:
        kws = ", ".join(col.keywords) if col.keywords else "—"
        ext = ""
        if col.min_value is not None:
            ext = f"  [{col.min_value}~{col.max_value}]"
        print(
            f"   {col.name:<22} {col.python_type:<10} "
            f"{col.null_ratio:>6.1%} {col.unique_count:>7}  {kws}{ext}"
        )
    print()


def _cmd_check(args):
    df = TableLoader.load(args.file)
    rule = registry.get(args.rule)
    if rule is None:
        print(f"❌ 未知规则: '{args.rule}'")
        names = [r["name"] for r in registry.list_all()]
        print(f"   可用规则: {', '.join(names)}")
        sys.exit(1)

    config = json.loads(args.config)
    result = rule.validate(df, **config)

    print(f"\n   {'✅ 通过' if result.is_pass else '❌ 失败'}")
    print(f"   规则: {result.rule_name}")
    print(f"   {result.summary}\n")

    output = ReportGenerator.generate_single(result, args.output)
    print(f"   📄 报告已保存: {output}\n")


def _cmd_chain(args):
    from .config.config_loader import ConfigLoader

    print(f"\n🔗 加载校验链: {args.config}\n")
    chain = ConfigLoader.load(args.config)
    print(f"\n🚀 开始执行 ({len(chain.steps)} 个步骤)...\n")

    result = chain.run()

    print(f"\n{'='*60}")
    print(result.summary())
    print(f"{'='*60}")

    output = ReportGenerator.generate(result, args.output)
    print(f"\n📄 报告已保存: {output}\n")


def _cmd_list_rules():
    rules = registry.list_all()
    print(f"\n📋 已注册 {len(rules)} 条规则:\n")

    by_cat = {}
    for r in rules:
        by_cat.setdefault(r["category"], []).append(r)

    for cat, items in by_cat.items():
        print(f"  [{cat}]")
        for r in items:
            print(f"    • {r['name']:<20} {r['description']}")
        print()


if __name__ == "__main__":
    main()