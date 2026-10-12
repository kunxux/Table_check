"""
TableCheck GUI 启动入口
=======================
用法:  python gui_main.py
"""

import sys
import os

# 确保项目根在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# 导入全部规则（触发注册）
import table_check.rules.cell_rules          # noqa: F401
import table_check.rules.column_rules        # noqa: F401
import table_check.rules.cross_table_rules   # noqa: F401
import table_check.rules.aggregation_rules   # noqa: F401
import table_check.rules.diff_rules          # noqa: F401

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.app import AppState
from gui.main_window import MainWindow


def main():
    # 高分屏适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("TableCheck")
    app.setOrganizationName("TableCheck")
    app.setApplicationVersion("0.2.0")

    # 初始化全局状态
    state = AppState()

    # 创建并显示主窗口
    window = MainWindow(state)
    window.resize(1400, 900)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()