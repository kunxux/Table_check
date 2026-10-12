"""
第4层 · 聚合/清洗规则
=====================
将多张表的数据按业务逻辑清洗、关联、聚合为一张可读的汇总表。
  - join_tables:  联表聚合 → 多表按列关联成一张宽表
  - column_map:   列映射 → 重命名/选列/删列
  - groupby_agg:  分组聚合 → 按列分组后统计
  - filter_rows:  行筛选 → 按条件过滤数据
"""

import pandas as pd
from ..core.rule_base import BaseRule, RuleResult, registry


def _load(source):
    """统一的数据源加载：支持 DataFrame 或文件路径。"""
    if isinstance(source, pd.DataFrame):
        return source.copy()
    if isinstance(source, str):
        from ..core.table_loader import TableLoader
        return TableLoader.load(source)
    raise TypeError(f"无法识别的数据源类型: {type(source)}")


# ═══════════════════════════════════════════════
# 1. 联表聚合
# ═══════════════════════════════════════════════

class JoinRule(BaseRule):
    name = "join_tables"
    description = "联表聚合：将多张表按指定列 JOIN 成一张新表"
    category = "聚合"

    def transform(self, dfs: dict, **params) -> pd.DataFrame:
        """
        dfs: {"表名": DataFrame 或 文件路径}
        params:
            join_sequence: [
                {"left": "表A", "right": "表B", "on": ["id"], "how": "left"},
                {"left": "<previous>", "right": "表C", "on": ["id"], "how": "inner"},
            ]
        """
        join_sequence = params.get("join_sequence", [])
        result = None

        for step in join_sequence:
            left_name = step["left"]
            right_name = step["right"]
            on = step.get("on", [])              # 同名列关联
            left_on = step.get("left_on", [])    # 异构列名关联（左表列）
            right_on = step.get("right_on", [])  # 异构列名关联（右表列）
            how = step.get("how", "left")
            suffixes = step.get("suffixes", ("_x", "_y"))

            left_df = result if left_name == "<previous>" and result is not None else _load(dfs.get(left_name))
            right_df = _load(dfs.get(right_name))

            if left_df is None or right_df is None:
                continue

            if left_on and right_on:
                result = left_df.merge(right_df, left_on=left_on, right_on=right_on,
                                       how=how, suffixes=suffixes)
            else:
                result = left_df.merge(right_df, on=on, how=how, suffixes=suffixes)

        return result if result is not None else pd.DataFrame()


registry.register(JoinRule())


# ═══════════════════════════════════════════════
# 2. 列映射 / 重命名 / 选择
# ═══════════════════════════════════════════════

class ColumnMapRule(BaseRule):
    name = "column_map"
    description = "列映射：重命名列、选择/删除指定的列"
    category = "聚合"

    def transform(self, dfs: dict, **params) -> pd.DataFrame:
        source_name = params.get("source")
        if source_name not in dfs:
            return pd.DataFrame()

        df = _load(dfs[source_name])

        # 重命名
        rename_map = params.get("rename", {})
        if rename_map:
            df = df.rename(columns=rename_map)

        # 选择列
        select = params.get("select_columns", [])
        if select:
            existing = [c for c in select if c in df.columns]
            df = df[existing]

        # 删除列
        drop = params.get("drop_columns", [])
        if drop:
            df = df.drop(columns=[c for c in drop if c in df.columns], errors="ignore")

        return df


registry.register(ColumnMapRule())


# ═══════════════════════════════════════════════
# 3. 分组聚合
# ═══════════════════════════════════════════════

class GroupByAggRule(BaseRule):
    name = "groupby_agg"
    description = "分组聚合：按指定列分组，对其他列做统计（sum/count/mean/min/max）"
    category = "聚合"

    def transform(self, dfs: dict, **params) -> pd.DataFrame:
        source_name = params.get("source")
        group_by = params.get("group_by", [])
        aggs = params.get("aggregations", {})  # {"列名": "sum"}

        if source_name not in dfs:
            return pd.DataFrame()

        df = _load(dfs[source_name])
        valid_groups = [g for g in group_by if g in df.columns]
        valid_aggs = {col: agg for col, agg in aggs.items() if col in df.columns}

        if not valid_groups or not valid_aggs:
            return df

        result = df.groupby(valid_groups, as_index=False).agg(valid_aggs)
        return result


registry.register(GroupByAggRule())


# ═══════════════════════════════════════════════
# 4. 行筛选
# ═══════════════════════════════════════════════

class FilterRule(BaseRule):
    name = "filter_rows"
    description = "行筛选：按条件过滤行（== / != / > / >= / < / <= / in / contains）"
    category = "聚合"

    def transform(self, dfs: dict, **params) -> pd.DataFrame:
        source_name = params.get("source")
        filters = params.get("filters", [])

        if source_name not in dfs:
            return pd.DataFrame()

        df = _load(dfs[source_name])

        for f in filters:
            col = f["column"]
            op = f.get("op", "==")
            value = f.get("value")

            if col not in df.columns:
                continue

            col_series = df[col]

            if op == "==":
                mask = col_series == value
            elif op == "!=":
                mask = col_series != value
            elif op == ">":
                mask = col_series > value
            elif op == ">=":
                mask = col_series >= value
            elif op == "<":
                mask = col_series < value
            elif op == "<=":
                mask = col_series <= value
            elif op == "in":
                mask = col_series.isin(value) if isinstance(value, list) else col_series == value
            elif op == "not_in":
                mask = ~col_series.isin(value) if isinstance(value, list) else col_series != value
            elif op == "contains":
                mask = col_series.astype(str).str.contains(str(value), na=False)
            else:
                continue

            df = df[mask]

        return df


registry.register(FilterRule())