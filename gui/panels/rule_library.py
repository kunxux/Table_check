"""
规则库面板
==========
左侧 QTreeWidget：按分类展示所有已注册规则 + 用户自定义规则。
支持搜索、双击加载、右键菜单。
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from gui.app import AppState
from table_check.core.rule_base import registry


class RuleLibraryPanel(QWidget):
    """规则库面板 — 左侧"""

    rule_double_clicked = Signal(str)   # 双击规则 → 加载到编辑区

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._user_rules = {}  # {name: config_dict}  用户通过UI创建的规则
        self._init_ui()
        self._populate()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索规则...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # 规则树
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["规则 / 分类"])
        self.tree.setRootIsDecorated(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

    # ── 填充 ──

    def _populate(self):
        self.tree.clear()

        # 系统规则（从 registry 读取）
        sys_root = QTreeWidgetItem(self.tree, ["📁 预置规则"])
        sys_root.setData(0, Qt.ItemDataRole.UserRole, "system")

        by_cat = {}
        for r in registry.list_all():
            by_cat.setdefault(r["category"], []).append(r)

        for cat, rules in by_cat.items():
            cat_item = QTreeWidgetItem(sys_root, [f"  {cat}  ({len(rules)})"])
            cat_item.setData(0, Qt.ItemDataRole.UserRole, "category")
            for r in rules:
                item = QTreeWidgetItem(cat_item, [r["name"]])
                item.setData(0, Qt.ItemDataRole.UserRole, "rule")
                item.setToolTip(0, r["description"])

        sys_root.setExpanded(True)

        # 用户规则
        user_root = QTreeWidgetItem(self.tree, ["📁 我的规则"])
        user_root.setData(0, Qt.ItemDataRole.UserRole, "user_root")
        if self._user_rules:
            for name in self._user_rules:
                item = QTreeWidgetItem(user_root, [name])
                item.setData(0, Qt.ItemDataRole.UserRole, "user_rule")
        user_root.setExpanded(True)

        self.tree.expandAll()

    # ── 搜索 ──

    def _on_search(self, text: str):
        """隐藏不匹配搜索词的项"""
        text_lower = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            root = self.tree.topLevelItem(i)
            self._filter_item(root, text_lower)

    def _filter_item(self, item: QTreeWidgetItem, text: str):
        visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            child_visible = self._filter_item(child, text)
            visible = visible or child_visible

        if text == "":
            item.setHidden(False)
            return True

        item_text = item.text(0).lower()
        if text in item_text and item.data(0, Qt.ItemDataRole.UserRole) == "rule":
            item.setHidden(False)
            return True

        if item.childCount() == 0:
            match = text in item_text
            item.setHidden(not match)
            return match

        item.setHidden(not visible)
        return visible

    # ── 交互 ──

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        role = item.data(0, Qt.ItemDataRole.UserRole)
        if role == "rule":
            rule_name = item.text(0)
            self.state.select_rule(rule_name)
            self.rule_double_clicked.emit(rule_name)
        elif role == "user_rule":
            # 加载用户保存的规则配置
            rule_name = item.text(0)
            if rule_name in self._user_rules:
                config_data = self._user_rules[rule_name]
                self.state.current_rule_name = config_data.get("rule")
                self.state.current_rule_config = config_data.get("config", {})
                self.rule_double_clicked.emit(config_data.get("rule", ""))

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return

        role = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        if role == "user_rule":
            act_del = menu.addAction("删除")
            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if action == act_del:
                name = item.text(0)
                self._user_rules.pop(name, None)
                self._populate()

    # ── 外部接口 ──

    def add_user_rule(self, name: str, rule_name: str, config: dict):
        """保存一条用户规则"""
        self._user_rules[name] = {"rule": rule_name, "config": config}
        self._populate()

    def get_user_rule(self, name: str) -> dict:
        return self._user_rules.get(name, {})