# This Python file uses the following encoding: utf-8
import getpass
import pathlib
import platform
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import qInstallMessageHandler, QtMsgType

from qfluentwidgets import setTheme, setThemeColor, Theme

APP_VERSION: str = "260109.1"
ROOT_PATH = str(pathlib.Path(__file__).parent).replace("\\", "/")


def is_windows_os() -> bool:
    return platform.system() == "Windows"


def get_current_user_name() -> str:
    return getpass.getuser()


def _install_qt_message_filter() -> None:
    """过滤已知无害的 Qt Windows 几何告警，避免污染终端输出。

    目前只屏蔽 TeachingTip 在 Windows 下由于最小尺寸/窗口约束导致的
    `QWindowsWindow::setGeometry: Unable to set geometry ...` 警告。
    """

    previous_handler = qInstallMessageHandler(None)

    def _handler(mode, context, message):
        try:
            if (
                mode == QtMsgType.QtWarningMsg
                and isinstance(message, str)
                and message.startswith("QWindowsWindow::setGeometry: Unable to set geometry")
                and "TeachingTipClassWindow" in message
            ):
                return
        except Exception:
            pass

        # 其他消息保持原行为
        try:
            if callable(previous_handler):
                previous_handler(mode, context, message)
                return
        except Exception:
            pass

        try:
            # 兜底：至少把信息输出到 stderr
            if isinstance(message, str) and message:
                print(message, file=sys.stderr)
        except Exception:
            pass

    qInstallMessageHandler(_handler)


if __name__ == "__main__":
    sys.path.append(".")
    app = QApplication(sys.argv)

    # 必须尽早安装，避免启动阶段输出无害的 Qt geometry 警告
    _install_qt_message_filter()
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
