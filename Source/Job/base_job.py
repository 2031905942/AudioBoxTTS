from PySide6.QtCore import QObject, QThread  # PySide6：Qt 的 Python 绑定；QObject 是 Qt 对象基类(支持信号槽/父子对象树)，QThread 用于后台线程执行耗时任务
from qfluentwidgets import Dialog  # qfluentwidgets：仿 Fluent Design 的 Qt 组件库；Dialog 是现成的模态对话框(通常用于确认/提示)

from Source.UI.Basic.error_info_bar import ErrorInfoBar  # 自定义：错误提示条(通常是顶部/底部弹出的 InfoBar)
from Source.UI.Basic.progress_bar_window import ProgressBarWindow  # 自定义：进度条窗口(线性进度)
from Source.UI.Basic.progress_ring_window import ProgressRingWindow  # 自定义：进度环窗口(旋转/环形进度)
from Source.UI.Basic.result_info_bar import ResultInfoBar  # 自定义：结果提示条(成功/信息/警告等)


class BaseJob(QObject):
    """BaseJob：所有“后台任务(Job)”的基类。

    设计目标：
    - 用一个 QThread 承载耗时逻辑，避免阻塞 GUI 主线程
    - 提供统一的 UI 反馈：进度窗口、错误提示、结果提示

    注意：仅创建线程对象并不会自动执行任务；通常还需要：
    1) 创建 worker(QObject 子类)
    2) worker.moveToThread(worker_thread)
    3) 连接 thread.started -> worker.run / 自定义槽函数
    4) worker 完成后发信号通知 UI 收尾

    本类当前只负责“线程壳 + UI 收尾”，具体 worker 的创建/连接由子类实现。
    """

    def __init__(self, main_window):
        super().__init__()  # 初始化 QObject：建立 Qt 对象基础能力(信号槽/父子关系等)
        from Source.main_window import MainWindow  # 延迟导入：常用于避免循环依赖(例如 MainWindow 也 import 了 Job)

        self.main_window: MainWindow = main_window  # 主窗口引用：用于禁用/启用窗口、弹提示条、作为对话框父窗口

        self.worker_thread: QThread = QThread(self)  # 后台线程对象；parent=self 可让 Qt 在销毁 BaseJob 时一并释放线程对象
        # ↑ 重要：QThread 默认不会做任何事，除非你把 worker 移入线程并连接 started 信号。

        self._progress_ring_window: ProgressRingWindow | None = None  # 进度环窗口实例；| None 是 Python 3.10+ 的联合类型写法(等价 Optional)
        self._progress_bar_window: ProgressBarWindow | None = None  # 进度条窗口实例；未显示时为 None，用于避免重复创建/便于统一释放

    def unit(self):
        """释放/停止资源(这里更像 uninit：可能是命名笔误，但保持原逻辑不做改名)。"""
        if self.worker_thread.isRunning():  # 判断线程是否正在运行
            self.worker_thread.quit()  # 请求线程事件循环退出(非强杀)；若线程里没跑 event loop 或被阻塞，可能不会立刻退出

    def start_worker(self):
        """启动后台线程，并暂时禁用主窗口输入。"""
        self.worker_thread.start()  # 启动线程：如果线程里有 event loop，会开始运行；通常配合 thread.started 信号触发 worker 执行
        # self.worker_thread.run()  # 不建议直接调用 run()：那会在当前线程同步执行，失去“后台线程”的意义
        self.main_window.setDisabled(True)  # 禁用主窗口：避免用户在任务过程中重复点击/触发冲突操作

    def show_error_info_bar(self, content: str):
        """弹出错误提示条。"""
        ErrorInfoBar(content, self.main_window)  # 创建错误 InfoBar：一般会自行 show，并附着在 main_window
        self.main_window.raise_()  # 把窗口抬到最前：确保提示可见(raise_ 是 Qt 的 API 名称)

    def job_finish(self, title: str, content: str, result: str):
        """任务结束统一收尾：关闭进度窗口、恢复主窗口、弹出结果提示。

        :param title: 提示标题
        :param content: 提示内容
        :param result: 结果类型(例如 success/info/warning/error 等，具体取决于 ResultInfoBar 的实现)
        """
        self.delete_progress_window()  # 关闭并释放进度相关窗口，防止悬浮窗口残留
        self.main_window.setDisabled(False)  # 恢复主窗口可交互
        self.show_result_info_bar(result, title, content)  # 用统一入口弹出“结果提示条”
        self.main_window.raise_()  # 再次抬到最前：确保用户看到结果

    def show_result_info_bar(self, info_bar_type: str, title: str, content: str):
        """弹出结果提示条(成功/提示/警告/失败等)。"""
        ResultInfoBar(info_bar_type, title, content, self.main_window)  # 由 ResultInfoBar 内部决定样式与展示位置

    def delete_progress_window(self):
        """安全销毁进度窗口。

        为什么 close() + deleteLater() 要一起用？
        - close()：触发窗口关闭流程(隐藏、发 closeEvent 等)，用户能立刻看到窗口消失
        - deleteLater()：把对象删除安排到 Qt 事件循环“稍后”执行，避免在信号槽或事件处理中立即 delete 导致崩溃

        注意：Qt GUI 对象应在 GUI 线程创建/销毁；如果你在子线程触发这里，最好用信号回到主线程执行。
        """
        if self._progress_ring_window:  # 仅当实例存在时才处理
            self._progress_ring_window.close()  # 关闭窗口(UI 立即消失)
            self._progress_ring_window.deleteLater()  # 延迟释放 Qt 对象内存(安全)
            self._progress_ring_window = None  # 置空引用：表示当前没有进度环窗口

        if self._progress_bar_window:
            self._progress_bar_window.close()
            self._progress_bar_window.deleteLater()
            self._progress_bar_window = None

    def _create_dialog(self, title: str, content: str) -> int:
        """创建并执行一个模态对话框。

        :return: Dialog.exec() 的返回值(通常是 QDialog.Accepted / Rejected)。

        说明：exec() 会阻塞当前线程的事件循环直到用户关闭对话框；
        在 GUI 线程里使用是常见的“确认框”模式，但别用它包裹耗时操作。
        """
        dialog: Dialog = Dialog(title, content, self.main_window)  # 将 main_window 作为父对象：对话框会居中且随父窗口生命周期管理
        return dialog.exec()  # 显示对话框并进入模态循环，返回用户选择结果

    def _print_log(self, log: str):
        """打印日志。

        :param log: 日志内容
        """
        print(f"[{self.__class__.__name__}] {log}")  # f-string：格式化字符串；__class__.__name__ 打印当前类名便于定位来源

    def _print_log_error(self, log: str):
        """打印错误日志。

        :param log: 日志内容
        """
        print(f"[{self.__class__.__name__}][Error] {log}")  # 与正常日志区分，便于检索/过滤
