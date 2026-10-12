"""
第5层 · 对比规则
================
将实际数据与策划的规划/预期数据进行比对：
  - pk_diff:       主键对齐对比 → 按 ID 对齐后逐列比较
  - full_diff:     全表对比 → 逐行逐列比较两张结构相同的表
"""

import pandas as pd
from ..core.rule_base import BaseRule, RuleResult, registry


def _resolve(source):
    if isinstance(source, pd.DataFrame):
        return source
    if isinstance(source, str):
        from ..core.table_loader import TableLoader
        return TableLoader.load(source)
    raise TypeError(f"无法解析数据源: {type(source)}")


# ═══════════════════════════════════════════════
# 1. 主键对齐对比
# ═══════════════════════════════════════════════

class PKDiffRule(BaseRule):
    name = "pk_diff"
    description = "规划对比：将实际数据与规划数据按主键对齐，逐列对比差异"
    category = "对比"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        """
        df: 实际数据表
        params:
            expected_df:     规划/预期表 (DataFrame 或文件路径)
            key_column:      主键列名（默认 "id"）
            compare_columns: 要比较的列（为空则自动选择所有共同列）
        """
        expected_raw = params.get("expected_df")
        key_col = params.get("key_column", "id")
        compare_cols = params.get("compare_columns", [])

        if expected_raw is None:
            return RuleResult(rule_name=self.name, status="error",
                              summary="缺少 expected_df 参数")

        expected = _resolve(expected_raw)

        # 校验主键列是否存在
        for label, tbl in [("实际表", df), ("规划表", expected)]:
            if key_col not in tbl.columns:
                return RuleResult(rule_name=self.name, status="error",
                                  summary=f"{label}中不存在主键列 '{key_col}'")

        actual_keys = set(df[key_col].dropna())
        expected_keys = set(expected[key_col].dropna())
        errors = []

        # 实际有、规划无
        for key in actual_keys - expected_keys:
            rows = df[df[key_col] == key]
            for idx in rows.index:
                errors.append({
                    "主键": key, "行号": int(idx) + 2,
                    "差异类型": "实际有·规划无",
                    "规则说明": f"[{key_col}]={key} 在实际表中存在，但规划表中没有",
                })

        # 规划有、实际无
        for key in expected_keys - actual_keys:
            rows = expected[expected[key_col] == key]
            for idx in rows.index:
                errors.append({
                    "主键": key, "行号": f"规划表行{int(idx)+2}",
                    "差异类型": "规划有·实际无",
                    "规则说明": f"[{key_col}]={key} 在规划表中存在，但实际表中没有",
                })

        # 共同主键 → 列值差异
        common = actual_keys & expected_keys

        if not compare_cols:
            # 自动选择所有共同列（排除主键）
            compare_cols = [c for c in df.columns
                            if c in expected.columns and c != key_col]

        for key in common:
            a_row = df[df[key_col] == key].iloc[0]
            e_row = expected[expected[key_col] == key].iloc[0]

            for col in compare_cols:
                if col not in df.columns or col not in expected.columns:
                    continue
                a_val = a_row[col]
                e_val = e_row[col]

                # NaN == NaN 视为相等
                if pd.isna(a_val) and pd.isna(e_val):
                    continue
                if pd.isna(a_val) or pd.isna(e_val) or a_val != e_val:
                    errors.append({
                        "主键": key, "列名": col,
                        "实际值": str(a_val), "规划值": str(e_val),
                        "差异类型": "数值不一致",
                        "规则说明": f"[{col}]: 实际={a_val} vs 规划={e_val}",
                    })

        extra = len(actual_keys - expected_keys)
        missing = len(expected_keys - actual_keys)
        mismatch = len([e for e in errors if e.get("差异类型") == "数值不一致"])
        failed = len(errors)

        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=len(actual_keys | expected_keys),
            passed_rows=len(common) - (mismatch // max(len(compare_cols), 1)),
            failed_rows=failed,
            errors=errors,
            summary=f"主键对比: +{extra}条多余 / -{missing}条缺失 / ~{mismatch}处不一致",
        )


registry.register(PKDiffRule())


# ═══════════════════════════════════════════════
# 2. 全表逐格对比
# ═══════════════════════════════════════════════

class FullTableDiffRule(BaseRule):
    name = "full_diff"
    description = "全表逐格对比：逐行逐列比较两张结构相同的表"
    category = "对比"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        other_raw = params.get("other_df")

        if other_raw is None:
            return RuleResult(rule_name=self.name, status="error",
                              summary="缺少 other_df 参数")

        other = _resolve(other_raw)
        errors = []

        # 形状不同 → 直接报
        if df.shape != other.shape:
            errors.append({
                "差异类型": "表结构不同",
                "左侧": f"{df.shape[0]}行 x {df.shape[1]}列",
                "右侧": f"{other.shape[0]}行 x {other.shape[1]}列",
                "规则说明": "两张表形状不一致",
            })
            return RuleResult(
                rule_name=self.name, status="fail",
                total_rows=max(len(df), len(other)), failed_rows=1,
                errors=errors,
                summary=f"表结构不一致: {df.shape} vs {other.shape}",
            )

        # 逐格对比（用 fillna 哨兵值处理 NaN 比较）
        sentinel = "__#NA#__"
        diff_mask = (df.fillna(sentinel).values != other.fillna(sentinel).values)
        diff_coords = diff_mask.nonzero()

        for r, c in zip(diff_coords[0], diff_coords[1]):
            errors.append({
                "行号": int(df.index[r]) + 2,
                "列名": str(df.columns[c]),
                "左侧值": str(df.iloc[r, c]),
                "右侧值": str(other.iloc[r, c]),
                "差异类型": "单元格不一致",
                "规则说明": f"第{int(df.index[r])+2}行 [{df.columns[c]}] 不一致",
            })

        failed = len(errors)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=len(df),
            passed_rows=len(df) - len(set(int(df.index[r]) for r, _ in zip(diff_coords[0], diff_coords[1]))),
            failed_rows=failed,
            errors=errors,
            summary=f"全表对比: 发现 {failed} 处单元格不一致",
        )


registry.register(FullTableDiffRule())