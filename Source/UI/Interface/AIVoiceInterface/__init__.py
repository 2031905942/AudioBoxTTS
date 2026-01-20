"""
AI 语音界面包

提供基于 IndexTTS2 的 AI 语音合成功能。

主要类:
- AIVoiceInterface: 主界面类
"""
from .core import AIVoiceInterface

# 为了向后兼容,也导出一些常用的类
from .core import EnvCheckSignals, EnvCheckWorker
from .core import DragDropOverlay, _ModalInputBlockerOverlay

from .dialogs import (
    DownloadModelChoiceDialog,
    EnvMissingInstallDialog,
    IndexTTSPreflightDialog,
    LocalModelActionsDialog,
    OnlineModelDialog,
    AIVoiceWelcomeDialog,
    ModelDiagnosticsDialog,
    DeleteAssetsChoiceDialog,
)

__all__ = [
    # 主类
    'AIVoiceInterface',

    # 核心类
    'EnvCheckSignals',
    'EnvCheckWorker',
    'DragDropOverlay',
    '_ModalInputBlockerOverlay',

    # 对话框
    'DownloadModelChoiceDialog',
    'EnvMissingInstallDialog',
    'IndexTTSPreflightDialog',
    'LocalModelActionsDialog',
    'OnlineModelDialog',
    'AIVoiceWelcomeDialog',
    'ModelDiagnosticsDialog',
    'DeleteAssetsChoiceDialog',
]
