# This Python file uses the following encoding: utf-8
import getpass
import pathlib
import platform
import sys

from PySide6.QtWidgets import QApplication

from qfluentwidgets import setTheme, setThemeColor, Theme

APP_VERSION: str = "251225.1"
ROOT_PATH = str(pathlib.Path(__file__).parent).replace("\\", "/")


def is_windows_os() -> bool:
    return platform.system() == "Windows"


def get_current_user_name() -> str:
    return getpass.getuser()


if __name__ == "__main__":
    sys.path.append(".")
    app = QApplication(sys.argv)
    app.setApplicationName("AudioBox")
    app.setApplicationDisplayName("AudioBox")

    if is_windows_os():
        app.setStyle('Fusion')

    setTheme(Theme.LIGHT)
    setThemeColor("#4685eb")

    from Source.main_window import MainWindow

    main_window = MainWindow()
    # main_window.show()

    sys.exit(app.exec())
