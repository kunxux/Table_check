"""
第3层 · 跨表校验规则
====================
验证不同表格之间的数据引用关系：
  - foreign_key:    外键存在性 → A表.a列的值必须在 B表.b列中存在
  - fk_consistency: 外键双向一致性 → 检查孤立引用 + 未被引用的 ID
  - cross_compare:  跨表列值比较 → 按共同列关联后比较同名列值是否一致
"""

import pandas as pd
from ..core.rule_base import BaseRule, RuleResult, registry


def _resolve_df(source, param_name: str = "target_df"):
    """将参数中的字符串路径解析为 DataFrame，支持直接传 DataFrame。"""
    if isinstance(source, pd.DataFrame):
        return source
    if isinstance(source, str):
        from ..core.table_loader import TableLoader
        return TableLoader.load(source)
    raise TypeError(f"{param_name} 必须是 DataFrame 或文件路径字符串，收到: {type(source)}")


# ═══════════════════════════════════════════════
# 1. 外键存在性校验
# ═══════════════════════════════════════════════

class ForeignKeyRule(BaseRule):
    name = "foreign_key"
    description = "外键校验：检查源表某列的值是否都在目标表某列中存在（引用完整性）"
    category = "跨表校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        """
        df: 源表（source table）
        params:
            source_column: 源表中的列名
            target_df:     目标表 DataFrame 或文件路径
            target_column: 目标表中的列名
        """
        source_col = params.get("source_column")
        target_df_raw = params.get("target_df")
        target_col = params.get("target_column")

        if not (source_col and target_df_raw is not None and target_col):
            return RuleResult(rule_name=self.name, status="error",
                              summary="缺少必要参数: source_column, target_df, target_column")

        if source_col not in df.columns:
            return RuleResult(rule_name=self.name, status="error",
                              summary=f"源列 '{source_col}' 在源表中不存在")

        target_df = _resolve_df(target_df_raw)
        if target_col not in target_df.columns:
            return RuleResult(rule_name=self.name, status="error",
                              summary=f"目标列 '{target_col}' 在目标表中不存在")

        target_set = set(target_df[target_col].dropna())
        errors = []

        for idx, val in df[source_col].items():
            if pd.isna(val):
                continue
            if val not in target_set:
                errors.append({
                    "行号": int(idx) + 2,
                    "列名": source_col,
                    "当前值": str(val),
                    "引用目标": f"目标表.{target_col}",
                    "错误类型": "外键丢失",
                    "规则说明": f"[{source_col}]={val} 在目标表 [{target_col}] 中不存在",
                })

        failed = len(errors)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=len(df),
            passed_rows=len(df) - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"外键检查: [{source_col}] → 目标表.[{target_col}], 发现 {failed} 个孤立引用",
        )


registry.register(ForeignKeyRule())


# ═══════════════════════════════════════════════
# 2. 外键双向一致性
# ═══════════════════════════════════════════════

class FKConsistencyRule(BaseRule):
    name = "fk_consistency"
    description = "外键双向一致性：检查 A↔B 两个方向的引用完整性"
    category = "跨表校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        source_col = params.get("source_column")
        target_df_raw = params.get("target_df")
        target_col = params.get("target_column")

        if not (source_col and target_df_raw is not None and target_col):
            return RuleResult(rule_name=self.name, status="error",
                              summary="缺少必要参数")
        if source_col not in df.columns:
            return RuleResult(rule_name=self.name, status="error",
                              summary=f"源列 '{source_col}' 不存在")

        target_df = _resolve_df(target_df_raw)
        if target_col not in target_df.columns:
            return RuleResult(rule_name=self.name, status="error",
                              summary=f"目标列 '{target_col}' 不存在")

        source_set = set(df[source_col].dropna())
        target_set = set(target_df[target_col].dropna())
        errors = []

        # A→B: 源表中的值在目标表中不存在
        orphan = source_set - target_set
        for val in orphan:
            rows = df[df[source_col] == val]
            for idx in rows.index:
                errors.append({
                    "行号": int(idx) + 2, "列名": source_col,
                    "当前值": str(val),
                    "错误类型": "孤立的源引用",
                    "规则说明": f"[{source_col}]={val} 在目标表中不存在",
                })

        # B→A: 目标表的 ID 在源表中没有被任何记录引用
        unused = target_set - source_set
        for val in unused:
            rows = target_df[target_df[target_col] == val]
            for idx in rows.index:
                errors.append({
                    "行号": f"目标表行{int(idx)+2}", "列名": target_col,
                    "当前值": str(val),
                    "错误类型": "未被引用的ID",
                    "规则说明": f"[{target_col}]={val} 未被任何源记录引用",
                })

        failed = len(errors)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=len(df) + len(target_df),
            passed_rows=len(df) + len(target_df) - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"双向检查: {len(orphan)} 个孤立引用, {len(unused)} 个未用ID",
        )


registry.register(FKConsistencyRule())


# ═══════════════════════════════════════════════
# 3. 跨表列值比较
# ═══════════════════════════════════════════════

class CrossTableCompareRule(BaseRule):
    name = "cross_compare"
    description = "跨表列值比较：按关联列连接两张表，比较同名或指定列的数值是否一致"
    category = "跨表校验"

    def validate(self, df: pd.DataFrame, **params) -> RuleResult:
        """
        df: A表（主表）
        params:
            other_df:       B表 DataFrame 或文件路径
            join_on:        连接列（如 ["id"]）
            compare_pairs:  [{"a_col": "hp", "b_col": "hp"}, ...]
        """
        other_raw = params.get("other_df")
        join_on = params.get("join_on", [])
        compare_pairs = params.get("compare_pairs", [])

        if other_raw is None or not join_on or not compare_pairs:
            return RuleResult(rule_name=self.name, status="error",
                              summary="缺少必要参数: other_df, join_on, compare_pairs")

        other_df = _resolve_df(other_raw, "other_df")

        # merge
        merged = df.merge(other_df, on=join_on, how="inner",
                          suffixes=("_A", "_B"))

        errors = []
        for pair in compare_pairs:
            a_col = pair["a_col"]
            b_col = pair["b_col"]
            col_a = f"{a_col}_A" if a_col in df.columns else a_col
            col_b = f"{b_col}_B" if b_col in other_df.columns else b_col

            if col_a not in merged.columns or col_b not in merged.columns:
                continue

            mismatch = merged[merged[col_a] != merged[col_b]]
            for _, row in mismatch.iterrows():
                errors.append({
                    "关联键": {k: row[k] for k in join_on},
                    "列名": f"{a_col} vs {b_col}",
                    "A表值": str(row[col_a]),
                    "B表值": str(row[col_b]),
                    "错误类型": "跨表数据不一致",
                    "规则说明": f"[{a_col}] ≠ [{b_col}]",
                })

        failed = len(errors)
        return RuleResult(
            rule_name=self.name,
            status="pass" if failed == 0 else "fail",
            total_rows=len(merged),
            passed_rows=len(merged) - failed,
            failed_rows=failed,
            errors=errors,
            summary=f"跨表比较 {len(compare_pairs)} 对列，发现 {failed} 处不一致",
        )


registry.register(CrossTableCompareRule())