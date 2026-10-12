# TableCheck — 游戏配表自动化校验框架

> 一个**零代码、可编排**的游戏配表数据质量检查工具。
>
> 策划配表 (Excel/CSV) → 自动识别列结构 → 选择校验规则 → 一键生成报告

---

## ⚡ 快速开始

### 环境要求

- Python 3.9+
- 依赖安装：

```bash
pip install -r requirements.txt
```

### 启动 GUI

```bash
python gui_main.py
```

启动后会自动加载演示数据（`demo/test_data/道具表.xlsx`），你可以在表格预览区看到数据。

### CLI 命令行

```bash
# 分析表格结构（自动识别列名/类型/关键字）
python -m table_check.cli analyze demo/test_data/道具表.xlsx

# 列出全部 18 条规则
python -m table_check.cli list-rules

# 单规则校验
python -m table_check.cli check demo/test_data/道具表.xlsx \
  --rule not_null --config '{"columns":["id","name"]}' --output report.xlsx

# 链式校验（JSON 配置）
python -m table_check.cli chain \
  --config config_examples/example1_single_table.json --output report.xlsx

# 运行全部演示（5 个场景）
cd demo && python run_demos.py
```

---

## 🏗️ 核心理念：规则即积木

所有检查逻辑封装为独立的「规则」，通过 GUI 或 JSON 配置把它们串联成校验流水线。

### 五层校验体系

| 层级 | 分类 | 规则数 | 代表规则 | 说明 |
|------|------|--------|---------|------|
| L1 | 原子校验 | 5 | `not_null` `type_check` `range_check` `enum_check` `regex_check` | 单元格逐格检查 |
| L2 | 表内校验 | 4 | `column_compare` `conditional_required` `unique_check` `composite_key` | 同表跨列关系 |
| L3 | 跨表校验 | 3 | `foreign_key` `fk_consistency` `cross_compare` | 多表引用完整性 |
| L4 | 聚合 | 4 | `join_tables` `column_map` `groupby_agg` `filter_rows` | 多表清洗整理 |
| L5 | 对比 | 2 | `pk_diff` `full_diff` | 实际 vs 规划对比 |

### 三层规则创建（GUI 支持）

| 层次 | 名称 | 适用场景 | 示例 |
|------|------|---------|------|
| ① | 预置规则 + 动态表单 | 80% 日常检查 | 选列 → 填参数 → 测试 |
| ② | 可视表达式构建器 | 15% 组合条件 | 拖选列/操作符/值，AND/OR 组合 |
| ③ | 自定义 Python 表达式 | 5% 复杂逻辑 | `df['price'] >= df['level'] * 100` |

---

## 🖥️ GUI 使用指南

### 主界面布局

```
┌────────────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 规则 | 帮助                                  │
│  工具栏: [打开] [执行规则] [执行链] [导出报告]                 │
├──────────────┬────────────────────┬────────────────────────┤
│  规则库(左)   │  表格预览(中央)     │  规则编辑 & 链编排(右)   │
│              │                    │                        │
│ 📁 预置规则   │ ┌────────────────┐ │ ┌────────────────────┐ │
│  ├ 原子校验   │ │id│name│price  │ │ │ ①预置 ②表达式 ③代码│ │
│  ├ 表内校验   │ │1 │药水│ 100   │ │ │ 选规则: [not_null] │ │
│  ├ 跨表校验   │ │2 │剑  │ -50🔴 │ │ │ 选列:   [☑id ☑name]│ │
│  ├ 聚合      │ │3 │盾  │ 800   │ │ │ [测试] [保存] [入链]│ │
│  └ 对比      │ └────────────────┘ │ └────────────────────┘ │
│ 📁 我的规则   │                    │ ┌────────────────────┐ │
│              │  列名 │类型│空值率  │ │ 🔗 链式编排         │ │
│              │  id   │int │0%    │ │ 1. 非空→2. 类型→... │ │
│              │  name │str │12%   │ │ [执行链] [清空]     │ │
│              │  price│int │25%   │ └────────────────────┘ │
├──────────────┴────────────────────┴────────────────────────┤
│  结果报告(底): ✅/❌ 摘要 + 错误列表（双击跳转到表格单元格）    │
└────────────────────────────────────────────────────────────┘
```

### 基本工作流

1. **加载表格**: 点击 文件→打开，选择 .xlsx/.csv 文件，或直接拖入窗口
2. **选择规则**: 在左侧规则库双击一条规则（如 `not_null`）
3. **配置参数**: 右侧编辑器自动生成对应表单，勾选列/填参数
4. **测试**: 点击「▶ 测试」按钮，表格中错误单元格自动变红高亮
5. **加入链**: 点击「➕ 加入链」，将配好的规则加入链式编排
6. **执行链**: 添加多条规则后，点击「▶ 执行链」，底部分步骤查看结果
7. **导出报告**: 点击「📄 导出 Excel 报告」生成多 Sheet 报告

### 高级操作

- **拖拽排序链**: 在链编排面板直接拖拽步骤调整执行顺序
- **搜索规则**: 规则库顶部搜索框输入关键字（如 "外键"）
- **保存规则**: Layer① 配置好的规则可保存到「我的规则」分组
- **表达式规则**: 切换到 Layer②，通过下拉框组合条件而不用写代码
- **自定义代码**: 切换到 Layer③，写 pandas 表达式处理复杂逻辑
- **双击跳转**: 结果面板双击错误行，自动跳到表格对应单元格

---

## 📁 项目结构

```
TableCheckFramework/
├── gui_main.py                       # ① GUI 启动入口
├── gui/                              # PySide6 GUI 层
│   ├── app.py                        #   全局状态管理 (Signal 驱动)
│   ├── main_window.py                #   主窗口 (菜单/工具栏/停靠面板)
│   ├── models/
│   │   └── dataframe_model.py        #   DataFrame → QTableView 适配器
│   ├── panels/
│   │   ├── table_panel.py            #   表格预览面板
│   │   ├── rule_library.py           #   规则库面板 (分类树+搜索)
│   │   ├── rule_editor.py            #   规则编辑容器 (①②③Tab切换)
│   │   ├── chain_panel.py            #   链式编排面板 (拖拽排序)
│   │   └── result_panel.py           #   结果报告面板 (双击跳转)
│   ├── editors/
│   │   ├── preset_editor.py          #   Layer①: 预置规则动态表单
│   │   ├── expression_editor.py      #   Layer②: 可视表达式构建器
│   │   └── python_editor.py          #   Layer③: 自定义Python编辑器
│   └── widgets/
│       ├── column_selector.py        #   列多选组件
│       ├── range_editor.py           #   范围编辑器
│       └── condition_builder.py      #   条件构建器
│
├── table_check/                      # ② 核心引擎 (纯Python, 可脱离GUI)
│   ├── core/
│   │   ├── rule_base.py              #   规则基类 + RuleRegistry 注册中心
│   │   ├── table_loader.py           #   表格加载 + 列识别 + 关键字提取
│   │   ├── chain_engine.py           #   链式调度引擎
│   │   └── report_generator.py       #   Excel 报告生成
│   ├── rules/
│   │   ├── cell_rules.py             #   L1: 原子校验 (not_null/type/range/enum/regex)
│   │   ├── column_rules.py           #   L2: 表内校验 (compare/conditional/unique/composite)
│   │   ├── cross_table_rules.py      #   L3: 跨表校验 (fk/consistency/cross_compare)
│   │   ├── aggregation_rules.py      #   L4: 聚合 (join/map/groupby/filter)
│   │   └── diff_rules.py             #   L5: 对比 (pk_diff/full_diff)
│   ├── config/
│   │   └── config_loader.py          #   JSON 配置加载与验证
│   └── cli.py                        #   命令行入口
│
├── demo/                             # ③ 演示
│   ├── generate_test_data.py         #   生成模拟游戏配表 (道具/掉落/规划)
│   ├── run_demos.py                  #   5 个场景完整演示脚本
│   ├── test_data/                    #   生成的测试 Excel 文件
│   └── reports/                      #   演示生成的报告
│
├── config_examples/                  # ④ JSON 配置示例
│   ├── example1_single_table.json    #   单表原子校验
│   ├── example2_column_validate.json #   表内跨列校验
│   ├── example3_cross_table.json     #   跨表外键校验
│   ├── example4_multi_aggregate.json #   多表联表聚合
│   └── example5_plan_diff.json       #   规划 vs 实际对比
│
└── requirements.txt                  # ⑤ 依赖: pandas + openpyxl + PySide6
```

---

## 🧩 架构设计 — 分层解耦

```
┌──────────────────────────────────────┐
│  GUI 层 (PySide6)                    │  ← 只管"长什么样"
│  表格预览 / 规则编辑 / 链编排 / 报告    │
├──────────────────────────────────────┤
│  接口层 (RuleRegistry)               │  ← GUI 和引擎只通过这个通信
│  注册-发现 / Schema→表单 / Signal     │
├──────────────────────────────────────┤
│  引擎层 (纯 Python)                   │  ← 只管"怎么做检查"
│  RuleBase / ChainEngine / Reporter   │
└──────────────────────────────────────┘
```

### 维护指南

| 要做什么 | 改哪里 | 影响范围 |
|---------|--------|---------|
| 加一条检查规则 | `rules/*_rules.py` 写1个类 + `register()` | 自动出现在 GUI 规则库 |
| 改检查逻辑 | `rules/*_rules.py` 对应类的 `validate()` | 只影响那条规则 |
| 改报告格式 | `core/report_generator.py` | 不影响检查逻辑 |
| 改表格加载方式 | `core/table_loader.py` | 不影响规则 |
| 改 GUI 布局 | `gui/main_window.py` | 不影响引擎 |
| 加一个新面板 | `gui/panels/` 新建一个文件 | 不影响其他面板 |
| 加 Layer① 规则表单 | `gui/editors/preset_editor.py` 加 `_build_xxx_form()` | 不影响其他编辑器 |
| 改链式调度 | `core/chain_engine.py` | 不影响单条规则 |

---

## 🔧 如何添加新规则

### 3 步即可

```python
# 1. 在 table_check/rules/ 下创建或编辑文件
from table_check.core.rule_base import BaseRule, RuleResult, registry

class MyNewRule(BaseRule):
    name = "my_new_rule"                    # 规则唯一标识
    description = "我的自定义规则"            # GUI 中显示的说明
    category = "原子校验"                    # 分类: 原子校验/表内校验/跨表校验/聚合/对比

    def validate(self, df, **params):
        errors = []
        # ... 你的检查逻辑
        return RuleResult(
            rule_name=self.name,
            status="pass" if len(errors) == 0 else "fail",
            total_rows=len(df),
            errors=errors,
            summary=f"发现 {len(errors)} 个问题",
        )

# 2. 注册
registry.register(MyNewRule())

# 3. 在 table_check/cli.py 和 gui_main.py 中 import 该文件
```

> GUI 层 **不需要任何改动**。规则库面板自动从 registry 读取并展示新规则。

---

## 📄 License

MIT — 自由使用、修改、分发。

---

## 🗺️ 路线图

- [x] 核心引擎 + 18 条规则 + CLI
- [x] 5 个 JSON 配置示例
- [x] 5 个场景演示脚本
- [x] PySide6 GUI（表格预览 / 规则库 / 三层编辑器 / 链编排 / 结果报告）
- [ ] 规则模板库（装备/技能/关卡/掉落/商店 等常见游戏配表检查模板）
- [ ] `expression_check` 规则 — Layer②③ 的运行时执行引擎
- [ ] 规则配置 JSON 导出/导入（团队共享规则模板）
- [ ] 增量检查（只检查变更的行）
- [ ] CI/CD 集成（Git Hook / 命令行静默模式）
- [ ] 多 Sheet / 多文件批量校验
- [ ] 增加新检查规则
