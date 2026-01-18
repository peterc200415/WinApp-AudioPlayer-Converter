"""
應用程式主入口
"""

from src.ui.main_window import MainWindow


def main():
    """主函數"""
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
