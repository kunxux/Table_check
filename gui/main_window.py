"""
主窗口 — 菜单栏 / 工具栏 / 停靠面板布局
========================================
"""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QDockWidget, QWidget,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon

from gui.app import AppState
from gui.panels.table_panel import TablePanel
from gui.panels.rule_library import RuleLibraryPanel
from gui.panels.rule_editor import RuleEditorPanel
from gui.panels.chain_panel import ChainPanel
from gui.panels.result_panel import ResultPanel


class MainWindow(QMainWindow):
    """TableCheck 主窗口"""

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state

        self.setWindowTitle("TableCheck — 游戏配表自动化校验")
        self.setAcceptDrops(True)

        # ── 构建 UI ──
        self._create_actions()
        self._create_menubar()
        self._create_toolbar()
        self._create_panels()
        self._create_statusbar()

        # ── 信号连接 ──
        self.state.status_message.connect(self.statusBar().showMessage)

        # 启动后自动加载演示数据
        QTimer.singleShot(100, self._load_demo_data)

    # ═══════════════════════════════════════════
    # Actions
    # ═══════════════════════════════════════════

    def _create_actions(self):
        # 文件
        self.act_open = QAction("打开表格(&O)", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self._on_open_file)

        self.act_close = QAction("关闭表格(&C)", self)
        self.act_close.triggered.connect(self._on_close_table)

        self.act_export = QAction("导出报告(&E)", self)
        self.act_export.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export.triggered.connect(self._on_export_report)

        self.act_quit = QAction("退出(&Q)", self)
        self.act_quit.setShortcut(QKeySequence.Quit)
        self.act_quit.triggered.connect(self.close)

        # 规则
        self.act_run_current = QAction("执行当前规则(&R)", self)
        self.act_run_current.setShortcut(QKeySequence("F5"))
        self.act_run_current.triggered.connect(self._on_run_current)

        self.act_run_chain = QAction("执行链(&H)", self)
        self.act_run_chain.setShortcut(QKeySequence("Ctrl+F5"))
        self.act_run_chain.triggered.connect(self._on_run_chain)

        # 帮助
        self.act_about = QAction("关于(&A)", self)
        self.act_about.triggered.connect(self._on_about)

    # ═══════════════════════════════════════════
    # 菜单栏
    # ═══════════════════════════════════════════

    def _create_menubar(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("文件(&F)")
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_close)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        rule_menu = mb.addMenu("规则(&R)")
        rule_menu.addAction(self.act_run_current)
        rule_menu.addAction(self.act_run_chain)

        help_menu = mb.addMenu("帮助(&H)")
        help_menu.addAction(self.act_about)

    # ═══════════════════════════════════════════
    # 工具栏
    # ═══════════════════════════════════════════

    def _create_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)

        tb.addAction(self.act_open)
        tb.addAction(self.act_run_current)
        tb.addAction(self.act_run_chain)
        tb.addSeparator()
        tb.addAction(self.act_export)

    # ═══════════════════════════════════════════
    # 面板布局
    # ═══════════════════════════════════════════

    def _create_panels(self):
        # ── 左侧: 规则库 ──
        self.rule_library = RuleLibraryPanel(self.state)
        dock_left = QDockWidget("规则库")
        dock_left.setWidget(self.rule_library)
        dock_left.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                              QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_left)

        # ── 右侧上: 规则编辑 + 链编排 ──
        self.rule_editor = RuleEditorPanel(self.state)
        self.chain_panel = ChainPanel(self.state)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.rule_editor, 3)
        right_layout.addWidget(self.chain_panel, 2)

        dock_right = QDockWidget("规则编辑 & 链编排")
        dock_right.setWidget(right_container)
        dock_right.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                               QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_right)

        # ── 中央: 表格预览 ──
        self.table_panel = TablePanel(self.state)
        self.setCentralWidget(self.table_panel)

        # ── 底部: 结果报告 ──
        self.result_panel = ResultPanel(self.state)
        dock_bottom = QDockWidget("检查结果")
        dock_bottom.setWidget(self.result_panel)
        dock_bottom.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                                QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock_bottom)

        # 连接: 规则库双击 → 加载到编辑区
        self.rule_library.rule_double_clicked.connect(self.rule_editor.load_rule)

        # 连接: 编辑区产生规则配置 → 加入链
        self.rule_editor.rule_add_to_chain.connect(self._on_add_to_chain)

    # ═══════════════════════════════════════════
    # 状态栏
    # ═══════════════════════════════════════════

    def _create_statusbar(self):
        sb = QStatusBar()
        sb.showMessage("就绪 — 点击 文件→打开 或拖入表格文件开始")
        self.setStatusBar(sb)

    # ═══════════════════════════════════════════
    # 拖放支持
    # ═══════════════════════════════════════════

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.xlsx', '.xls', '.csv')):
                self._load_file(path)
                break

    # ═══════════════════════════════════════════
    # 动作实现
    # ═══════════════════════════════════════════

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开表格", "",
            "表格文件 (*.xlsx *.xls *.csv);;Excel (*.xlsx *.xls);;CSV (*.csv);;所有文件 (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str):
        try:
            self.state.load_table(path)
        except Exception as e:
            QMessageBox.warning(self, "加载失败", str(e))

    def _on_close_table(self):
        self.state.dataframes.clear()
        self.state.table_infos.clear()
        self.state.current_table = None
        self.table_panel.clear()
        self.state.status_message.emit("表格已关闭")

    def _on_export_report(self):
        if self.state.last_result is None:
            QMessageBox.information(self, "提示", "尚未执行任何检查，无法导出报告")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "report.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return

        try:
            from table_check.core.report_generator import ReportGenerator
            from table_check.core.chain_engine import ChainResult

            result = self.state.last_result
            if isinstance(result, ChainResult):
                ReportGenerator.generate(result, path)
            else:
                ReportGenerator.generate_single(result, path)
            self.state.status_message.emit(f"报告已导出: {path}")
        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _on_run_current(self):
        if not self.state.current_rule_name:
            QMessageBox.information(self, "提示", "请先在规则库中选择一条规则")
            return

        try:
            self.state.run_single_rule(
                self.state.current_rule_name,
                self.state.current_rule_config,
            )
        except Exception as e:
            QMessageBox.warning(self, "执行失败", str(e))

    def _on_run_chain(self):
        if not self.state.chain_steps:
            QMessageBox.information(self, "提示", "请在链编排区添加至少一个步骤")
            return

        try:
            self.state.run_chain()
        except Exception as e:
            QMessageBox.warning(self, "执行失败", str(e))

    def _on_add_to_chain(self, step):
        """从规则编辑器收到步骤，加入链"""
        self.state.add_chain_step(step)

    def _on_about(self):
        QMessageBox.about(
            self, "关于 TableCheck",
            "TableCheck v0.2.0\n\n"
            "游戏配表自动化校验工具\n"
            "五层校验规则 + PySide6 GUI\n\n"
            "规则即积木，零代码配表检查"
        )

    # ═══════════════════════════════════════════
    # 演示数据
    # ═══════════════════════════════════════════

    def _load_demo_data(self):
        """启动时自动加载演示数据（如果存在）"""
        demo_dir = Path(__file__).parent.parent / "demo" / "test_data"
        items = demo_dir / "道具表.xlsx"
        if items.exists():
            try:
                self._load_file(str(items))
            except Exception:
                pass