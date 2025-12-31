import os

from Source.Task.base_task import BaseTask
from Source.Utility.base_utility import BaseUtility


class FileDeleteTask(BaseTask):
    def __init__(self, utility: BaseUtility, path: str):
        super().__init__(utility)
        self.path = path

    def run(self):
        if not os.path.isfile(self.path):
            self.signals.error.emit({
                "message": f"删除文件\"{self.path}\"失败:\n文件路径不合法"
            })
            return
        try:
            os.remove(self.path)
            self.signals.progress.emit(100)
            self.signals.finished.emit({})
        except Exception as exception:
            self.signals.error.emit({
                "message": f"删除文件\"{self.path}\"发生异常:\n{exception}"
            })
