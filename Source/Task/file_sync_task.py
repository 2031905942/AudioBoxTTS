import os
from os import path

from PySide6.QtCore import QMutexLocker

from Source.Task.base_task import BaseTask
from Source.Utility.base_utility import BaseUtility
from Source.Utility.file_utility import FileUtility


class FileSyncTask(BaseTask):
    def __init__(self, utility: BaseUtility, src_path: str, dest_path: str):
        super().__init__(utility)
        self.src_path = src_path
        self.dest_path = dest_path

    def run(self):
        if not os.path.isfile(self.src_path):
            self.signals.error.emit({
                "message": f"同步文件\"{self.src_path}\"到\"{self.dest_path}\"失败:\n源文件路径不合法"
            })
            return
        if not os.path.isfile(self.dest_path):
            self.signals.error.emit({
                "message": f"同步文件\"{self.src_path}\"到\"{self.dest_path}\"失败:\n目标文件路径不合法"
            })
            return
        try:
            is_same = FileUtility.compare_file(self.src_path, self.dest_path)
            if is_same:
                self.signals.progress.emit(100)
                self.signals.finished.emit({
                    "is_same": True,
                    "src_path": self.src_path,
                    "dest_path": self.dest_path,
                })
                return
            else:
                # 模拟大文件拷贝（实际可用shutil.copy ）
                total_size = path.getsize(self.src_path)
                copied = 0
                with open(self.src_path, 'rb') as src_file, open(self.dest_path, 'wb') as dest_file:
                    while True:
                        chunk = src_file.read(1024 * 1024)  # 分块读取（1MB）
                        if not chunk:
                            break
                        # 检查中断标志, 每处理1MB数据检查一次中断
                        with QMutexLocker(self._lock):
                            if not self._is_running:
                                self.signals.interrupted.emit({})
                                return  # 主动终止任务
                        dest_file.write(chunk)
                        copied += len(chunk)
                        progress = int((copied / total_size) * 100)
                        self.signals.progress.emit(progress)
                self.signals.finished.emit({
                    "is_same": False,
                    "src_path": self.src_path,
                    "dest_path": self.dest_path,
                })
        except Exception as exception:
            self.signals.error.emit({
                "message": f"同步文件\"{self.src_path}\"到\"{self.dest_path}\"发生异常:\n{exception}"
            })
        finally:
            if not self._is_running:
                os.remove(self.dest_path)  # 删除未完成文件
