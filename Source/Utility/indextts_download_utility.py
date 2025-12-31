"""
IndexTTS2 模型下载工具类

使用 huggingface_hub 下载模型文件，支持进度回调。
"""
import os
import sys
from typing import Optional, Callable, List

from PySide6.QtCore import QObject, Signal, Slot

# 默认模型仓库
DEFAULT_REPO_ID = "IndexTeam/IndexTTS-2"

# 必需文件及其大致大小（MB，用于进度估算）
# 注意: pinyin.vocab 是源码自带的参考文件，不在 HuggingFace 仓库中
REQUIRED_FILES = {
    "bpe.model": 0.5,
    "config.yaml": 0.01,
    "gpt.pth": 3400,
    "s2mel.pth": 1150,
    "wav2vec2bert_stats.pt": 0.01,
    "feat1.pt": 0.06,
    "feat2.pt": 0.4,
    # Qwen 情感分析模型（用于情感文本分析）
    "qwen0.6bemo4-merge/config.json": 0.01,
    "qwen0.6bemo4-merge/model.safetensors": 1300,
    "qwen0.6bemo4-merge/generation_config.json": 0.01,
    "qwen0.6bemo4-merge/tokenizer.json": 7,
    "qwen0.6bemo4-merge/tokenizer_config.json": 0.01,
    "qwen0.6bemo4-merge/merges.txt": 1.7,
    "qwen0.6bemo4-merge/vocab.json": 2.7,
}

# 外部依赖模型 (repo_id, filename, size_mb, local_subpath)
EXTERNAL_FILES = [
    ("facebook/w2v-bert-2.0", "config.json", 0.01, "facebook/w2v-bert-2.0"),
    ("facebook/w2v-bert-2.0", "preprocessor_config.json", 0.01, "facebook/w2v-bert-2.0"),
    ("facebook/w2v-bert-2.0", "model.safetensors", 2300, "facebook/w2v-bert-2.0"),
    ("amphion/MaskGCT", "semantic_codec/model.safetensors", 50, "amphion/MaskGCT"),
]

# 可选文件（已移至 REQUIRED_FILES）
OPTIONAL_FILES = {
    # Qwen 模型现在是必需的
}


class IndexTTSDownloadUtility(QObject):
    """IndexTTS2 模型下载 Worker（运行在子线程）

    信号：
        progress_signal(float, str): 进度更新 (0.0-1.0, 描述)
        error_signal(str): 错误消息
        finished_signal(str): 下载完成，返回模型目录路径
        file_downloaded_signal(str): 单个文件下载完成
    """

    progress_signal = Signal(float, str)
    error_signal = Signal(str)
    finished_signal = Signal(str)
    file_downloaded_signal = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled: bool = False

    def cancel(self):
        """取消下载"""
        self._is_cancelled = True

    @Slot(str, str, bool)
    def download(self, local_dir: str, repo_id: str = DEFAULT_REPO_ID,
                 use_mirror: bool = False):
        """下载模型到指定目录

        Args:
            local_dir: 本地保存目录
            repo_id: HuggingFace 仓库 ID
            use_mirror: 是否使用镜像源（hf-mirror.com）
        """
        self._is_cancelled = False

        try:
            self.progress_signal.emit(0.0, "准备下载环境...")

            # 设置镜像
            if use_mirror:
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            elif "HF_ENDPOINT" in os.environ:
                del os.environ["HF_ENDPOINT"]

            # 导入 huggingface_hub
            try:
                from huggingface_hub import hf_hub_download, snapshot_download
            except ImportError:
                self.error_signal.emit(
                    "huggingface_hub 未安装。\n"
                    "请运行: pip install huggingface_hub[hf_xet]"
                )
                return

            os.makedirs(local_dir, exist_ok=True)

            # 计算总大小
            total_size = sum(REQUIRED_FILES.values()) + sum(f[2] for f in EXTERNAL_FILES)
            downloaded_size = 0.0

            self.progress_signal.emit(0.05, f"开始下载 {len(REQUIRED_FILES) + len(EXTERNAL_FILES)} 个文件...")

            # 1. 下载主仓库文件
            for filename, size_mb in REQUIRED_FILES.items():
                if self._is_cancelled:
                    self.error_signal.emit("下载已取消")
                    return

                local_path = os.path.join(local_dir, filename)

                # 跳过已存在的文件
                if os.path.exists(local_path):
                    self.progress_signal.emit(
                        0.05 + 0.9 * (downloaded_size + size_mb) / total_size,
                        f"跳过已存在: {filename}"
                    )
                    downloaded_size += size_mb
                    continue

                self.progress_signal.emit(
                    0.05 + 0.9 * downloaded_size / total_size,
                    f"下载中: {filename} ({size_mb:.1f} MB)"
                )

                try:
                    # 使用 hf_hub_download 下载单个文件
                    hf_hub_download(
                        repo_id=repo_id,
                        filename=filename,
                        local_dir=local_dir,
                        local_dir_use_symlinks=False,
                    )
                    downloaded_size += size_mb
                    self.file_downloaded_signal.emit(filename)

                except Exception as e:
                    self.error_signal.emit(f"下载 {filename} 失败: {e}")
                    return

            # 2. 下载外部依赖文件
            for ext_repo_id, filename, size_mb, local_subpath in EXTERNAL_FILES:
                if self._is_cancelled:
                    self.error_signal.emit("下载已取消")
                    return

                # 构造本地完整路径
                target_dir = os.path.join(local_dir, local_subpath)
                local_path = os.path.join(target_dir, filename)

                # 跳过已存在
                if os.path.exists(local_path):
                    self.progress_signal.emit(
                        0.05 + 0.9 * (downloaded_size + size_mb) / total_size,
                        f"跳过已存在: {filename}"
                    )
                    downloaded_size += size_mb
                    continue

                self.progress_signal.emit(
                    0.05 + 0.9 * downloaded_size / total_size,
                    f"下载中: {filename} ({size_mb:.1f} MB)"
                )

                try:
                    hf_hub_download(
                        repo_id=ext_repo_id,
                        filename=filename,
                        local_dir=target_dir,
                        local_dir_use_symlinks=False,
                    )
                    downloaded_size += size_mb
                    self.file_downloaded_signal.emit(filename)
                except Exception as e:
                    self.error_signal.emit(f"下载 {filename} 失败: {e}")
                    return

            self.progress_signal.emit(0.95, "验证文件完整性...")

            # 验证必需文件
            missing = []
            for filename in REQUIRED_FILES:
                if not os.path.exists(os.path.join(local_dir, filename)):
                    missing.append(filename)

            if missing:
                self.error_signal.emit(f"文件验证失败，缺少: {', '.join(missing)}")
                return

            self.progress_signal.emit(1.0, "下载完成！")
            self.finished_signal.emit(local_dir)

        except Exception as e:
            import traceback
            self.error_signal.emit(f"下载失败: {e}\n{traceback.format_exc()}")

    @staticmethod
    def get_model_size_estimate() -> str:
        """获取模型总大小估算"""
        total = sum(REQUIRED_FILES.values())
        return f"约 {total / 1024:.1f} GB"

    @staticmethod
    def check_disk_space(path: str, required_mb: float = 5000) -> tuple[bool, str]:
        """检查磁盘空间

        Returns:
            (是否足够, 描述信息)
        """
        import shutil
        try:
            total, used, free = shutil.disk_usage(path)
            free_mb = free / (1024 * 1024)
            if free_mb < required_mb:
                return False, f"磁盘空间不足: 需要 {required_mb / 1024:.1f} GB，可用 {free_mb / 1024:.1f} GB"
            return True, f"可用空间: {free_mb / 1024:.1f} GB"
        except Exception as e:
            return False, f"无法检查磁盘空间: {e}"
