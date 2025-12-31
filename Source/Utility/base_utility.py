from typing import Optional  # typing：类型标注模块；Optional[T] 表示 T | None（允许为 None）

from PySide6.QtCore import QObject, Signal  # PySide6：Qt 的 Python 绑定；QObject 是 Qt 对象基类；Signal 用于定义 Qt 信号(线程间安全通信的常用方式)

from Source.Job.base_job import BaseJob  # BaseJob：封装后台线程(QThread) + UI 收尾(提示条/进度窗口)的“任务外壳”
from Source.Task.base_task import BaseTask  # BaseTask：项目里的“可运行任务”抽象(通常是 QRunnable/线程池任务)，支持 stop() 取消


class BaseUtility(QObject):
    """BaseUtility：业务工具/流程编排的基类。

    你可以把它理解成“任务调度器/流程控制器”：
    - 负责管理一组 BaseTask（通常跑在线程池 threadpool 里）
    - 通过 Qt Signal 把进度/错误/完成事件抛回到 UI 层(BaseJob)

    关键点：
    - 信号槽(Signals/Slots)是 Qt 推荐的跨线程通信方式：worker 线程发信号，GUI 线程的槽函数安全更新 UI。
    - 本类不直接操作 UI 组件，而是把 UI 行为委托给 BaseJob（解耦）。
    """

    # 信号定义（Signal 是“类属性”级别的声明；Qt 会在实例化时把它绑定成可用的信号对象）
    update_progress_text_signal: Signal = Signal(str)  # 发射进度文字（例如“正在处理 xxx...”），参数类型：str
    update_progress_total_count_signal: Signal = Signal(int)  # 发射总任务数/总步骤数，用于进度条最大值，参数类型：int
    update_progress_current_count_signal: Signal = Signal(int)  # 发射已完成数量/当前进度，用于进度条当前值，参数类型：int
    error_signal: Signal = Signal(str)  # 发射错误信息文本，UI 收到后弹 ErrorInfoBar，参数类型：str
    show_result_info_bar_signal = Signal(str, str, str)  # 发射结果提示条信息：(类型, 标题, 内容)
    finish_signal: Signal = Signal(str, str, str)  # 发射“整个 Job 结束”事件：(标题, 内容, 结果类型)

    def __init__(self, base_job: BaseJob):
        super().__init__()  # 初始化 QObject：让该对象具备 Qt 信号槽、线程亲和性(thread affinity)等机制

        self._base_job: BaseJob = base_job  # 关联的 BaseJob：用于统一 UI 回调、线程退出等收尾动作

        # 把 Utility 发出的信号连接到 BaseJob 的 UI 槽函数：实现“业务逻辑 -> UI 提示”的解耦
        self.error_signal.connect(self._base_job.show_error_info_bar)  # 错误信号 -> 弹错误提示条
        self.show_result_info_bar_signal.connect(self._base_job.show_result_info_bar)  # 结果提示信号 -> 弹结果提示条
        self.finish_signal.connect(self._base_job.job_finish)  # 结束信号 -> 统一收尾(关闭进度窗口、恢复主窗体、弹结果)
        self.finish_signal.connect(self._base_job.worker_thread.quit)  # 同时请求 BaseJob 的 QThread 事件循环退出(如果仍在运行)

        self.cancel_job: bool = False  # 取消标记：True 表示用户/错误触发取消，任务执行过程中应主动检查此标记并尽快退出

        self.active_task_list: list[BaseTask] = []  # 当前正在运行/准备运行的任务列表(用于统一取消/清理)
        self.total_task_count = 0  # 总任务数：用于判断是否“全部完成”(也可用于进度条最大值)
        self.completed_task_count = 0  # 已完成任务数：每个任务完成后累加，用于进度条当前值

    def notice_cancel_job(self):
        """通知取消整个 Job。

        典型场景：用户点击“取消”、关闭窗口、或上层逻辑判断无需继续。
        """
        self.cancel_all_task()  # 停止所有任务并清空线程池队列
        self.finish_signal.emit("任务中止", "", "warning")  # 发射结束信号：warning 表示“中止但未必是错误”

    def notice_error_and_cancel_job(self, data: Optional[dict]):
        """发生错误时：先取消所有任务，再提示错误信息，最后结束 Job。

        :param data: 可选的错误数据字典；可能为 None。
        """
        self.cancel_all_task()  # 出错后第一时间停止后续任务，避免越错越多
        if data:  # Python 的 truthy 判断：None/{} 会被视为 False
            message: Optional[str] = data.get("message")  # 从字典取 message；类型仍可能为 None
            if message:
                self.error_signal.emit(message)  # 发射错误提示：由 BaseJob 在 UI 线程里展示
        self.finish_signal.emit("任务中止", "", "error")  # 发射结束信号：error 表示异常结束

    def on_single_task_finished_internal(self, data: Optional[dict]):
        """单个任务完成后的“内部统一入口”。

        子类一般只需要重写 on_single_task_finished/on_all_task_finished，
        不要直接改 internal 逻辑，以免破坏计数与收尾。
        """
        self.completed_task_count += 1  # 计数 +1：表示又完成了一个任务
        self.on_single_task_finished(data)  # 留给子类扩展：例如记录结果、更新 UI 文本等
        self.update_progress_current_count_signal.emit(self.completed_task_count)  # 推送当前完成数量，用于 UI 更新
        if self.completed_task_count == self.total_task_count:  # 全部任务完成
            self.on_all_task_finished_internal()  # 进入“全部完成”收尾

    def on_single_task_finished(self, data: Optional[dict]):
        """子类可重写：处理单个任务完成后的业务逻辑。

        :param data: 任务返回的数据(可能为 None)
        """
        pass  # 基类默认不处理

    def on_all_task_finished_internal(self):
        """全部任务完成后的“内部统一入口”。"""
        self.cancel_all_task()  # 全部完成也做一次清理：停止残留任务、清空列表与线程池队列
        self.on_all_task_finished()  # 留给子类扩展：例如发 finish_signal、弹结果提示等

    def on_all_task_finished(self):
        """子类可重写：处理所有任务完成后的最终逻辑。"""
        pass

    def start_all_task(self):
        """启动 active_task_list 中的所有任务。

        这里使用 main_window.threadpool：说明项目使用的是 Qt 的线程池(QThreadPool)模式，
        适合跑大量短任务(BaseTask 很可能是 QRunnable 封装)。
        """
        for active_task in self.active_task_list:  # 遍历每个待执行任务
            self._base_job.main_window.threadpool.start(active_task)  # 提交到线程池异步执行

    def cancel_all_task(self):
        """取消并清理所有任务。

        取消的三件事：
        1) 设置 cancel_job 标记（给任务一个“自我退出”的依据）
        2) 调用每个 task.stop()（主动请求任务停止，具体实现看 BaseTask）
        3) 清列表 + 清线程池队列（避免未开始的任务继续被调度）
        """
        self.cancel_job = True  # 全局取消标志置 True
        for task in self.active_task_list:
            task.stop()  # 请求该任务停止；任务内部应定期检查标志/中断点
        self.active_task_list.clear()  # 清空任务引用：避免重复取消、也利于 GC
        self._base_job.main_window.threadpool.clear()  # 清空线程池“等待队列”；已在运行的任务仍需自己响应 stop/cancel_job

    def _print_log(self, log: str):
        """打印日志。

        :param log: 日志
        """
        print(f"[{self.__class__.__name__}] {log}")  # f-string：格式化输出；类名用于定位日志来源

    def _print_log_error(self, log: str):
        """打印错误日志。

        :param log: 日志
        """
        print(f"[{self.__class__.__name__}][Error] {log}")  # 追加 [Error] 标签，便于搜索/过滤
