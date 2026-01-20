"""
控制器模块

包含 AIVoiceInterface 的所有控制器 mixin 类。
这些 mixin 通过多重继承组合到主 interface 类中。
"""
from .ui_builder import UIBuilderMixin
from .character_operations import CharacterOperationsMixin
from .model_management import ModelManagementMixin
from .download_manager import DownloadManagerMixin
from .audio_operations import AudioOperationsMixin
from .generation_controller import GenerationControllerMixin
from .history_manager import HistoryManagerMixin
from .project_tab_controller import ProjectTabControllerMixin
from .onboarding_guide import OnboardingGuideMixin

__all__ = [
    'UIBuilderMixin',
    'CharacterOperationsMixin',
    'ModelManagementMixin',
    'DownloadManagerMixin',
    'AudioOperationsMixin',
    'GenerationControllerMixin',
    'HistoryManagerMixin',
    'ProjectTabControllerMixin',
    'OnboardingGuideMixin',
]
