"""参考音频播放器组件

该组件用于“参考音频区域”，支持：
- 紧凑布局
- 空态上传提示（点击触发 upload_requested）
- 清空按钮（触发 clear_requested）

后续若参考音频区域需要新增能力（例如：自动切片、降噪预览等），
请优先在该文件内扩展，而不要影响生成结果播放器。
"""

from __future__ import annotations

from .audio_player_widget import AudioPlayerWidget


class ReferenceAudioPlayerWidget(AudioPlayerWidget):
    """参考音频播放器：紧凑 + 可导入空态 + 可清空。"""

    def __init__(self, title: str = "Voice Reference", parent=None):
        super().__init__(
            title,
            parent,
            compact_mode=True,
            compact_empty_hint="upload",
            show_clear_button=True,
            clear_tooltip="移除参考音频",
            title_follows_filename=True,
        )
