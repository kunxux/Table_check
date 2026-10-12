"""
表格加载器 — 自动识别列名、类型、语义关键字
==============================================
放入一张表 → 自动拆解每列的名字、数据类型、空值分布、值域范围、关键字标签。
这些信息供给 UI 做「智能列推荐」和「规则自动匹配」。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


# ──────────────────────────────────────────────
# 数据类：列信息 & 表信息
# ──────────────────────────────────────────────

@dataclass
class ColumnInfo:
    """单列的完整识别信息"""
    name: str                    # 原始列名
    dtype: str                   # pandas dtype 字符串，如 'int64'
    python_type: str             # 语义类型：int / float / str / bool / datetime
    null_count: int              # 空值个数
    null_ratio: float            # 空值比例
    unique_count: int            # 唯一值个数
    sample_values: List[Any]     # 前 5 个非空样本
    keywords: List[str]          # 从列名提取的关键字标签（id / name / type / count …）
    min_value: Optional[Any] = None  # 数值列的最小值
    max_value: Optional[Any] = None  # 数值列的最大值


@dataclass
class TableInfo:
    """一张表的完整分析摘要"""
    name: str
    file_path: str
    sheet_name: Optional[str] = None
    total_rows: int = 0
    total_columns: int = 0
    columns: List[ColumnInfo] = field(default_factory=list)

    def get_column_names(self) -> List[str]:
        return [c.name for c in self.columns]

    def get_id_columns(self) -> List[ColumnInfo]:
        """找出可能是 ID 的列（列名关键字中包含 'id'）"""
        return [c for c in self.columns if "id" in c.keywords]

    def get_columns_by_keyword(self, keyword: str) -> List[ColumnInfo]:
        """按关键字查找列"""
        return [c for c in self.columns if keyword in c.keywords]


# ──────────────────────────────────────────────
# TableLoader — 核心加载器
# ──────────────────────────────────────────────

class TableLoader:
    """表格加载 + 自动分析

    用法:
        # 加载一张表
        df = TableLoader.load("道具表.xlsx")

        # 分析一张表（不返回数据，只返回元信息）
        info = TableLoader.analyze("道具表.xlsx")
        for col in info.columns:
            print(col.name, col.python_type, col.keywords)

        # 批量加载
        dfs = TableLoader.load_multi(["表A.xlsx", "表B.csv"])
    """

    # ── 关键字模式库 ──
    # 列名包含以下模式之一，就打上对应关键字标签。
    # 扩展方式：直接在这里加模式即可，UI 会自动识别。
    KEYWORD_PATTERNS: Dict[str, List[str]] = {
        "id":       ["id", "编号", "序号", "ID", "Id", "code", "key"],
        "name":     ["名称", "名字", "name", "姓名", "标题", "title"],
        "type":     ["类型", "type", "种类", "分类", "category", "品质", "quality"],
        "count":    ["数量", "count", "个数", "amount", "num", "次数"],
        "rate":     ["概率", "rate", "几率", "权重", "weight", "比例", "ratio", "百分比"],
        "desc":     ["描述", "desc", "说明", "备注", "remark", "note", "comment"],
        "price":    ["价格", "price", "cost", "售价", "花费", "购买"],
        "level":    ["等级", "level", "lv", "级别", "rank", "星级", "star"],
        "time":     ["时间", "time", "date", "日期", "duration", "时长", "cd", "冷却"],
        "status":   ["状态", "status", "enable", "是否", "开关", "flag"],
        "damage":   ["伤害", "damage", "攻击", "atk", "攻击力", "防御", "def", "生命", "hp"],
    }

    # ── 文件加载 ──

    @staticmethod
    def load(path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
        """加载 Excel / CSV，返回 DataFrame。"""
        path = Path(path)
        suffix = path.suffix.lower()

        if suffix in (".xlsx", ".xls", ".xlsm"):
            return pd.read_excel(path, sheet_name=sheet_name or 0)
        elif suffix == ".csv":
            try:
                return pd.read_csv(path, encoding="utf-8")
            except UnicodeDecodeError:
                return pd.read_csv(path, encoding="gbk")
        else:
            raise ValueError(f"不支持的文件格式: {suffix}（支持 .xlsx / .xls / .csv）")

    @staticmethod
    def list_sheets(path: str) -> List[str]:
        """列出 Excel 文件的所有 Sheet 名称。CSV 返回空列表。"""
        p = Path(path)
        if p.suffix.lower() in (".xlsx", ".xls", ".xlsm"):
            xl = pd.ExcelFile(p)
            return xl.sheet_names
        return []

    # ── 关键字提取 ──

    @classmethod
    def _extract_keywords(cls, col_name: str) -> List[str]:
        """从列名提取语义关键字"""
        col_lower = col_name.lower()
        keywords = []
        for kw, patterns in cls.KEYWORD_PATTERNS.items():
            for pat in patterns:
                if pat.lower() in col_lower:
                    keywords.append(kw)
                    break
        return keywords

    # ── 单列分析 ──

    @classmethod
    def analyze_column(cls, df: pd.DataFrame, col_name: str) -> ColumnInfo:
        """分析单列的属性"""
        series = df[col_name]
        null_count = int(series.isna().sum())
        total = len(df)

        # 推断语义 Python 类型
        if pd.api.types.is_integer_dtype(series):
            py_type = "int"
        elif pd.api.types.is_float_dtype(series):
            py_type = "float"
        elif pd.api.types.is_bool_dtype(series):
            py_type = "bool"
        elif pd.api.types.is_datetime64_any_dtype(series):
            py_type = "datetime"
        else:
            py_type = "str"

        # 非空统计
        non_null = series.dropna()
        unique_count = int(non_null.nunique()) if len(non_null) > 0 else 0
        sample_values = non_null.head(5).tolist()

        # 数值列的 min / max
        min_val, max_val = None, None
        if py_type in ("int", "float") and len(non_null) > 0:
            try:
                min_val = float(non_null.min()) if py_type == "float" else int(non_null.min())
                max_val = float(non_null.max()) if py_type == "float" else int(non_null.max())
            except (TypeError, ValueError):
                pass

        return ColumnInfo(
            name=str(col_name),
            dtype=str(series.dtype),
            python_type=py_type,
            null_count=null_count,
            null_ratio=round(null_count / total, 4) if total > 0 else 0,
            unique_count=unique_count,
            sample_values=sample_values,
            keywords=cls._extract_keywords(str(col_name)),
            min_value=min_val,
            max_value=max_val,
        )

    # ── 整表分析 ──

    @classmethod
    def analyze(cls, path: str, sheet_name: Optional[str] = None) -> TableInfo:
        """加载一张表并返回其完整分析摘要（不含数据，只含元信息）。"""
        df = cls.load(path, sheet_name)
        file_path = Path(path)

        columns = [cls.analyze_column(df, col) for col in df.columns]

        return TableInfo(
            name=file_path.stem,
            file_path=str(file_path.resolve()),
            sheet_name=sheet_name,
            total_rows=len(df),
            total_columns=len(df.columns),
            columns=columns,
        )

    # ── 批量加载 ──

    @staticmethod
    def load_multi(paths: List[str]) -> Dict[str, pd.DataFrame]:
        """批量加载多个文件 → {文件名(不含扩展名): DataFrame}"""
        result = {}
        for p in paths:
            try:
                df = TableLoader.load(p)
                name = Path(p).stem
                result[name] = df
            except Exception as e:
                print(f"[警告] 加载 {p} 失败: {e}")
        return result