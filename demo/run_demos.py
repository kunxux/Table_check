"""
运行全部 5 个演示场景
====================
直接运行此脚本:  python run_demos.py

这 5 个场景对应你规划的 5 层校验：
  场景1: 单元格原子校验 — 单表全列扫描（漏填/类型/范围/枚举）
  场景2: 表内跨列校验 — 道具表列间逻辑（唯一性/列比较/条件依赖）
  场景3: 跨表外键校验 — 掉落表.item_id 是否在 道具表.id 中存在
  场景4: 多表联表聚合 — 掉落表 JOIN 道具表，生成可读的掉落汇总
  场景5: 规划对比 — 实际掉落 vs 策划规划表，按 item_id 对齐比较
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from table_check.core.table_loader import TableLoader
from table_check.core.chain_engine import ChainValidator, ChainStep
from table_check.core.report_generator import ReportGenerator
from table_check.core.rule_base import registry

# 触发规则注册
import table_check.rules.cell_rules          # noqa
import table_check.rules.column_rules        # noqa
import table_check.rules.cross_table_rules   # noqa
import table_check.rules.aggregation_rules   # noqa
import table_check.rules.diff_rules          # noqa


# ── 准备工作：确保测试数据存在 ──
TEST_DATA = Path(__file__).parent / "test_data"
REPORTS = Path(__file__).parent / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

if not (TEST_DATA / "道具表.xlsx").exists():
    print("⚠️  测试数据不存在，正在生成...")
    from generate_test_data import generate
    generate()


def demo_header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ═══════════════════════════════════════════════════════
# 场景1: 单元格原子校验
# ═══════════════════════════════════════════════════════
def demo_1_cell_validation():
    demo_header("场景1: 单元格原子校验 — 道具表全列扫描")

    df = TableLoader.load(str(TEST_DATA / "道具表.xlsx"))

    # 1a. 非空校验
    r1 = registry.get("not_null").validate(
        df, columns=["id", "name", "type", "quality", "price", "level"]
    )
    print(f"  1a. 非空校验: {r1.summary}")

    # 1b. 类型校验
    r2 = registry.get("type_check").validate(
        df, column_types={"id": "int", "name": "str", "quality": "int", "price": "int"}
    )
    print(f"  1b. 类型校验: {r2.summary}")

    # 1c. 范围校验
    r3 = registry.get("range_check").validate(
        df, ranges={"price": {"min": 0, "max": 10000}, "quality": {"min": 1, "max": 5}}
    )
    print(f"  1c. 范围校验: {r3.summary}")

    # 1d. 枚举校验
    r4 = registry.get("enum_check").validate(
        df, enums={"type": [1, 2, 3, 4]}
    )
    print(f"  1d. 枚举校验: {r4.summary}")

    # 合并所有错误并输出报告
    all_errors = r1.errors + r2.errors + r3.errors + r4.errors
    merged = type(r1)(
        rule_name="场景1_合集",
        status="fail" if all_errors else "pass",
        total_rows=r1.total_rows + r2.total_rows + r3.total_rows + r4.total_rows,
        failed_rows=len(all_errors),
        errors=all_errors,
        summary=f"4项检查共发现 {len(all_errors)} 个错误",
    )
    path = ReportGenerator.generate_single(merged, str(REPORTS / "demo1_原子校验.xlsx"))
    print(f"\n  📄 报告: {path}")


# ═══════════════════════════════════════════════════════
# 场景2: 表内跨列校验
# ═══════════════════════════════════════════════════════
def demo_2_column_validation():
    demo_header("场景2: 表内跨列校验 — 道具表列间逻辑")

    df = TableLoader.load(str(TEST_DATA / "道具表.xlsx"))

    # 2a. ID 唯一性
    r1 = registry.get("unique_check").validate(df, columns=["id"])
    print(f"  2a. ID唯一性: {r1.summary}")

    # 2b. 条件依赖: type=2(武器) 时 desc 必填
    r2 = registry.get("conditional_required").validate(
        df, conditions=[{"if_column": "type", "if_value": 2, "then_columns": ["desc"]}]
    )
    print(f"  2b. 条件依赖: {r2.summary}")

    # 合并报告
    all_errors = r1.errors + r2.errors
    merged = type(r1)(
        rule_name="场景2_合集",
        status="fail" if all_errors else "pass",
        total_rows=r1.total_rows + r2.total_rows,
        failed_rows=len(all_errors),
        errors=all_errors,
        summary=f"2项检查共发现 {len(all_errors)} 个错误",
    )
    path = ReportGenerator.generate_single(merged, str(REPORTS / "demo2_表内校验.xlsx"))
    print(f"\n  📄 报告: {path}")


# ═══════════════════════════════════════════════════════
# 场景3: 跨表外键校验
# ═══════════════════════════════════════════════════════
def demo_3_cross_table():
    demo_header("场景3: 跨表外键校验 — 掉落表 item_id → 道具表 id")

    drops = TableLoader.load(str(TEST_DATA / "掉落表.xlsx"))
    items = TableLoader.load(str(TEST_DATA / "道具表.xlsx"))

    # 3a. 外键存在性
    r1 = registry.get("foreign_key").validate(
        drops,
        source_column="item_id",
        target_df=items,
        target_column="id",
    )
    print(f"  3a. 外键校验: {r1.summary}")

    # 3b. 双向一致性
    r2 = registry.get("fk_consistency").validate(
        drops,
        source_column="item_id",
        target_df=items,
        target_column="id",
    )
    print(f"  3b. 双向一致性: {r2.summary}")

    # 合并报告
    all_errors = r1.errors + r2.errors
    merged = type(r1)(
        rule_name="场景3_合集",
        status="fail" if all_errors else "pass",
        total_rows=r1.total_rows + r2.total_rows,
        failed_rows=len(all_errors),
        errors=all_errors,
        summary=f"2项检查共发现 {len(all_errors)} 个错误",
    )
    path = ReportGenerator.generate_single(merged, str(REPORTS / "demo3_跨表校验.xlsx"))
    print(f"\n  📄 报告: {path}")


# ═══════════════════════════════════════════════════════
# 场景4: 多表联表聚合
# ═══════════════════════════════════════════════════════
def demo_4_aggregation():
    demo_header("场景4: 多表联表聚合 — 掉落 + 道具 → 可读掉落汇总")

    drops = TableLoader.load(str(TEST_DATA / "掉落表.xlsx"))
    items = TableLoader.load(str(TEST_DATA / "道具表.xlsx"))

    chain = ChainValidator("掉落数据聚合链")

    chain.register_table("掉落表", drops)
    chain.register_table("道具表", items)

    # 步骤1: 筛选出合法的掉落（排除 item_id 为空的数据）
    chain.add_step(ChainStep(
        step_index=1, step_name="过滤有效掉落",
        rule_name="filter_rows",
        mode="transform",
        config={
            "source": "掉落表",
            "filters": [{"column": "item_id", "op": "!=", "value": None}],
        },
        output_table="有效掉落",
    ))

    # 步骤2: LEFT JOIN 道具表，获取道具名称/类型
    chain.add_step(ChainStep(
        step_index=2, step_name="关联道具名称",
        rule_name="join_tables",
        mode="transform",
        config={
            "join_sequence": [
                {"left": "有效掉落", "right": "道具表",
                 "left_on": ["item_id"], "right_on": ["id"], "how": "left"}
            ],
        },
        input_tables=["有效掉落", "道具表"],
        output_table="掉落汇总",
    ))

    # 步骤3: 列映射 — 只保留需要展示的列
    chain.add_step(ChainStep(
        step_index=3, step_name="精简列",
        rule_name="column_map",
        mode="transform",
        config={
            "source": "掉落汇总",
            "select_columns": ["drop_id", "monster_name", "item_id", "name", "type",
                               "quality", "drop_rate", "min_count", "max_count"],
            "rename": {"name": "道具名称", "type": "道具类型"},
        },
        output_table="最终掉落汇总",
    ))

    result = chain.run()
    print(result.summary())

    path = ReportGenerator.generate(result, str(REPORTS / "demo4_聚合汇总.xlsx"))
    print(f"\n  📄 报告: {path}")


# ═══════════════════════════════════════════════════════
# 场景5: 规划对比
# ═══════════════════════════════════════════════════════
def demo_5_plan_diff():
    demo_header("场景5: 规划对比 — 实际掉落 vs 策划规划")

    drops = TableLoader.load(str(TEST_DATA / "掉落表.xlsx"))
    plan = TableLoader.load(str(TEST_DATA / "掉落规划表.xlsx"))

    chain = ChainValidator("掉落规划对比链")

    chain.register_table("掉落表", drops)
    chain.register_table("规划表", plan)

    # 步骤1: 按 item_id 聚合实际掉落的概率和数量
    chain.add_step(ChainStep(
        step_index=1, step_name="聚合实际掉落",
        rule_name="groupby_agg",
        mode="transform",
        config={
            "source": "掉落表",
            "group_by": ["item_id"],
            "aggregations": {"drop_rate": "sum", "min_count": "sum"},
        },
        output_table="实际聚合",
    ))

    # 步骤2: 列映射规划表使其与实际表对齐
    chain.add_step(ChainStep(
        step_index=2, step_name="对齐规划列",
        rule_name="column_map",
        mode="transform",
        config={
            "source": "规划表",
            "rename": {"plan_rate": "期望概率", "plan_count": "期望数量"},
        },
        output_table="规划对齐",
    ))

    # 步骤3: LEFT JOIN 实际 vs 规划
    chain.add_step(ChainStep(
        step_index=3, step_name="关联实际与规划",
        rule_name="join_tables",
        mode="transform",
        config={
            "join_sequence": [
                {"left": "规划对齐", "right": "实际聚合", "on": ["item_id"], "how": "left"}
            ],
        },
        input_tables=["规划对齐", "实际聚合"],
        output_table="对比结果",
    ))

    # 步骤4: 按主键对比差异
    chain.add_step(ChainStep(
        step_index=4, step_name="差异标注",
        rule_name="pk_diff",
        mode="validate",
        config={
            "expected_df": "规划表",
            "key_column": "item_id",
            "compare_columns": [],
        },
        input_tables=["掉落表"],
    ))

    result = chain.run()
    print(result.summary())

    path = ReportGenerator.generate(result, str(REPORTS / "demo5_规划对比.xlsx"))
    print(f"\n  📄 报告: {path}")


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  TableCheck 演示 — 5层校验规则验证")
    print("=" * 70)

    print(f"\n📋 已注册 {len(registry)} 条规则:")
    for r in registry.list_all():
        print(f"   • {r['name']}  [{r['category']}]")

    demo_1_cell_validation()
    demo_2_column_validation()
    demo_3_cross_table()
    demo_4_aggregation()
    demo_5_plan_diff()

    print(f"\n{'='*70}")
    print(f"  ✅ 全部 5 个场景演示完成!")
    print(f"  📂 报告目录: {REPORTS.resolve()}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()