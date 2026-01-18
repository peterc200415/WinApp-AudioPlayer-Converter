"""
應用程式主入口
注意：建議從專案根目錄運行：python main.py
或使用模組方式：python -m src.main
"""

import sys
from pathlib import Path

# 如果直接運行此文件，添加專案根目錄到 Python 路徑
if __name__ == "__main__":
    # 獲取專案根目錄（src 的父目錄）
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.ui.main_window import MainWindow


def main():
    """主函數"""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
