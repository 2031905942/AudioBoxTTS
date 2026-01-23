"""生成结果播放器组件

该组件用于“生成结果区域”（包括历史记录等），默认：
- 紧凑布局
- 不显示上传空态提示
- 默认不提供清空按钮

后续若需要在生成结果播放器上增加更多自定义功能（例如：
A/B 标记、波形点击跳转、重命名、批量导出、音频对比等），
请优先在该文件内扩展。
"""

from __future__ import annotations

from .audio_player_widget import AudioPlayerWidget


class ResultAudioPlayerWidget(AudioPlayerWidget):
    """生成结果播放器：紧凑 + 不显示导入空态 + 无清空按钮。"""

    def __init__(self, title: str = "音频", parent=None):
        super().__init__(
            title,
            parent,
            compact_mode=True,
            compact_empty_hint="none",
            show_clear_button=False,
            # 输出样本希望展示 wav 文件名
            title_follows_filename=True,
        )
