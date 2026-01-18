"""
應用程式主入口
從專案根目錄運行：python main.py
"""

from src.ui.main_window import MainWindow


def main():
    """主函數"""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
