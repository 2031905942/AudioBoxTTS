"""
IndexTTS2 环境依赖安装工具

"""
import os
import subprocess
import sys
from typing import Optional, List, Tuple

from PySide6.QtCore import QObject, Signal, Slot


# IndexTTS2 完整依赖列表（基于 pyproject.toml）
# 注意：某些依赖如 cython, keras, tensorboard, opencv 等仅用于训练，推理时不需要
CORE_DEPENDENCIES = [
    # === PyTorch 核心（版本会根据 CUDA/CPU 自动调整） ===
    "torch==2.8.0",
    "torchaudio==2.8.0",
    
    # === Transformers 和加速 ===
    "transformers==4.52.1",
    "accelerate==1.8.1",
    "tokenizers==0.21.0",
    
    # === 音频处理 ===
    "librosa==0.10.2.post1",
    "descript-audiotools==0.7.2",
    "ffmpeg-python==0.2.0",
    
    # === 深度学习工具 ===
    "safetensors==0.5.2",
    "einops>=0.8.1",
    "omegaconf>=2.3.0",
    
    # === NLP 和文本处理 ===
    "sentencepiece>=0.2.1",
    "jieba==0.42.1",
    "cn2an==0.5.22",
    "g2p-en==2.1.0",
    "pypinyin",
    "wetext>=0.0.9",  # Windows/Mac 文本处理
    
    # === 数据处理 ===
    "numpy==1.26.2",
    "numba==0.58.1",
    "pandas>=2.0.0",
    
    # === 配置和工具 ===
    "json5==0.10.0",
    "munch==4.0.0",
    "tqdm>=4.67.1",
    
    # === 模型下载 ===
    "huggingface_hub",
    "modelscope==1.27.0",
]

# PyTorch CUDA 索引 URL
PYTORCH_CUDA_INDEX = "https://download.pytorch.org/whl/cu128"
PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

# 国内镜像
PYPI_MIRRORS = {
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "default": "https://pypi.org/simple",
}

# 需要卸载的 AI 专用依赖列表
# 注意：我们会动态扫描并卸载 nvidia-* 和 triton 等大型依赖
UNINSTALL_PACKAGES = [
    "torch", "torchaudio", "transformers", "accelerate", "tokenizers",
    "librosa", "descript-audiotools", "ffmpeg-python",
    "safetensors", "einops", "omegaconf",
    "sentencepiece", "jieba", "cn2an", "g2p-en", "wetext",
    "numba", "munch", "huggingface_hub", "modelscope",
    "scipy", "scikit-learn", "pandas", "matplotlib", "pillow", "triton"
]


class IndexTTSEnvUtility(QObject):
    """IndexTTS2 环境依赖安装 Worker"""

    progress_signal = Signal(float, str)  # 进度, 描述
    error_signal = Signal(str)
    finished_signal = Signal(bool)  # 是否成功
    log_signal = Signal(str)  # 安装日志

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled = False
        self._python_path: str = sys.executable

    def cancel(self):
        """取消安装"""
        self._is_cancelled = True

    @staticmethod
    def get_python_path() -> str:
        """获取当前 Python 解释器路径"""
        return sys.executable

    @staticmethod
    def check_full_env_status() -> Tuple[bool, str, List[str]]:
        """检查完整环境状态 (子进程安全检测)
        
        Returns:
            (is_ready, message, missing_list)
        """
        import subprocess
        import sys
        import json
        
        # 完整的检测脚本，一次性检查所有依赖和 CUDA
        check_script = """
import sys
import importlib.util
import json

deps = [
    ("torch", "torch"),
    ("torchaudio", "torchaudio"),
    ("transformers", "transformers"),
    ("accelerate", "accelerate"),
    ("librosa", "librosa"),
    ("omegaconf", "omegaconf"),
    ("sentencepiece", "sentencepiece"),
    ("safetensors", "safetensors"),
    ("huggingface_hub", "huggingface_hub"),
]

missing = []
for import_name, pkg_name in deps:
    try:
        if importlib.util.find_spec(import_name) is None:
            missing.append(pkg_name)
    except:
        missing.append(pkg_name)

result = {
    "missing": missing,
    "cuda_available": False,
    "cuda_name": ""
}

if not missing:
    try:
        import torch
        if torch.cuda.is_available():
            result["cuda_available"] = True
            result["cuda_name"] = torch.cuda.get_device_name(0)
    except:
        pass

print(json.dumps(result))
"""
        try:
            creation_flags = 0x08000000 if sys.platform == 'win32' else 0
            proc = subprocess.run(
                [sys.executable, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=10,  # 10秒超时
                creationflags=creation_flags
            )
            
            if proc.returncode != 0:
                return False, "环境检测脚本执行失败 (Python 环境异常)", []
                
            try:
                data = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                return False, "环境检测返回数据格式错误", []
                
            missing = data.get("missing", [])
            
            if missing:
                return False, f"缺少依赖: {', '.join(missing[:3])}{'...' if len(missing)>3 else ''}", missing
            
            cuda_msg = f"CUDA 可用: {data.get('cuda_name', 'Unknown')}" if data.get('cuda_available') else "CUDA 不可用"
            return True, f"环境就绪 ({cuda_msg})", []
            
        except subprocess.TimeoutExpired:
            return False, "环境检测超时 (系统响应过慢)", []
        except Exception as e:
            return False, f"环境检测异常: {str(e)}", []

    @staticmethod
    def check_cuda_available() -> Tuple[bool, str]:
        """检查 CUDA 是否可用 (通过子进程，防止崩溃)

        Returns:
            (是否可用, 描述信息)
        """
        import subprocess
        import sys
        import re
        
        # 使用简短的脚本检测，避免主进程 import torch 导致崩溃
        check_script = "import torch; print('CUDA_AVAILABLE:', torch.cuda.is_available()); print('DEVICE_NAME:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
        
        try:
            # 启动子进程检测
            # creationflags=0x08000000 (CREATE_NO_WINDOW) 防止弹出黑框
            creation_flags = 0x08000000 if sys.platform == 'win32' else 0
            
            result = subprocess.run(
                [sys.executable, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=15,  # 15秒超时
                creationflags=creation_flags
            )
            
            if result.returncode != 0:
                # 脚本执行失败（可能是 import torch 报错）
                return False, "PyTorch 环境异常 (无法加载)"
                
            output = result.stdout
            if "CUDA_AVAILABLE: True" in output:
                # 提取设备名
                match = re.search(r"DEVICE_NAME: (.+)", output)
                device_name = match.group(1).strip() if match else "Unknown GPU"
                return True, f"CUDA 可用: {device_name}"
            else:
                return False, "CUDA 不可用，将使用 CPU 模式"
                
        except subprocess.TimeoutExpired:
            return False, "环境检测超时 (PyTorch 加载过慢)"
        except Exception as e:
            return False, f"环境检测失败: {str(e)}"

    @staticmethod
    def check_dependencies_installed() -> Tuple[bool, List[str]]:
        """检查核心依赖是否已安装

        Returns:
            (是否全部安装, 缺失的包列表)
        """
        import importlib.util
        missing = []
        check_packages = [
            ("torch", "torch"),
            ("torchaudio", "torchaudio"),
            ("transformers", "transformers"),
            ("accelerate", "accelerate"),
            ("librosa", "librosa"),
            ("omegaconf", "omegaconf"),
            ("sentencepiece", "sentencepiece"),
            ("safetensors", "safetensors"),
            ("huggingface_hub", "huggingface_hub"),
        ]

        for import_name, package_name in check_packages:
            if importlib.util.find_spec(import_name) is None:
                missing.append(package_name)

        return len(missing) == 0, missing

    @Slot(bool, str)
    def install_dependencies(self, use_cuda: bool = True, mirror: str = "default"):
        """安装依赖

        Args:
            use_cuda: 是否安装 CUDA 版本的 PyTorch
            mirror: PyPI 镜像源 (aliyun/tsinghua/default)
        """
        self._is_cancelled = False

        try:
            self.progress_signal.emit(0.0, "准备安装环境...")
            self.log_signal.emit(f"Python 路径: {self._python_path}")

            # 确定 pip 索引
            pypi_index = PYPI_MIRRORS.get(mirror, PYPI_MIRRORS["default"])
            pytorch_index = PYTORCH_CUDA_INDEX if use_cuda else PYTORCH_CPU_INDEX

            self.log_signal.emit(f"PyPI 镜像: {pypi_index}")
            self.log_signal.emit(f"PyTorch 源: {pytorch_index}")

            # 升级 pip
            self.progress_signal.emit(0.05, "升级 pip...")
            self._run_pip(["install", "--upgrade", "pip"])

            # 安装 PyTorch（单独处理，因为需要特殊索引）
            self.progress_signal.emit(0.1, "安装 PyTorch（可能需要几分钟）...")

            torch_packages = ["torch==2.8.0", "torchaudio==2.8.0"]
            result = self._run_pip([
                "install",
                *torch_packages,
                "--index-url", pytorch_index,
            ])

            if not result:
                self.error_signal.emit("PyTorch 安装失败")
                return

            # 安装其他依赖
            other_deps = [d for d in CORE_DEPENDENCIES if not d.startswith("torch")]
            total = len(other_deps)

            for i, dep in enumerate(other_deps):
                if self._is_cancelled:
                    self.error_signal.emit("安装已取消")
                    return

                progress = 0.2 + 0.7 * (i / total)
                self.progress_signal.emit(progress, f"安装 {dep}...")

                result = self._run_pip([
                    "install", dep,
                    "-i", pypi_index,
                    "--trusted-host", pypi_index.split("//")[1].split("/")[0],
                ])

                if not result:
                    self.log_signal.emit(f"警告: {dep} 安装可能失败，继续...")

            # 验证安装
            self.progress_signal.emit(0.95, "验证安装...")
            is_ok, missing = self.check_dependencies_installed()

            if is_ok:
                self.progress_signal.emit(1.0, "安装完成！")
                self.finished_signal.emit(True)
            else:
                self.error_signal.emit(f"部分依赖安装失败: {', '.join(missing)}")
                self.finished_signal.emit(False)

        except Exception as e:
            import traceback
            self.error_signal.emit(f"安装失败: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit(False)

    @Slot()
    def uninstall_dependencies(self):
        """卸载依赖"""
        self._is_cancelled = False
        
        try:
            self.progress_signal.emit(0.0, "正在扫描已安装的包...")
            self.log_signal.emit(f"Python 路径: {self._python_path}")
            
            # 1. 获取所有已安装的包
            installed_packages = []
            try:
                proc = subprocess.run(
                    [self._python_path, "-m", "pip", "freeze"],
                    capture_output=True, text=True, encoding='utf-8'
                )
                if proc.returncode == 0:
                    # 解析 freeze 输出 (package==version)
                    for line in proc.stdout.splitlines():
                        if "==" in line:
                            installed_packages.append(line.split("==")[0].lower())
                        elif "@" in line: # 处理 url 安装的情况
                            pass 
            except Exception as e:
                self.log_signal.emit(f"扫描包失败: {e}")

            # 2. 构建完整的卸载列表
            to_uninstall = set(UNINSTALL_PACKAGES)
            
            # 动态添加 nvidia-* 包 (这些通常很大，且不会被自动卸载)
            for pkg in installed_packages:
                if pkg.startswith("nvidia-") or pkg.startswith("triton"):
                    to_uninstall.add(pkg)
            
            # 转换为列表并排序
            final_list = sorted(list(to_uninstall))
            
            total = len(final_list)
            self.progress_signal.emit(0.1, f"发现 {total} 个相关包需要卸载...")
            
            for i, pkg in enumerate(final_list):
                if self._is_cancelled:
                    self.error_signal.emit("卸载已取消")
                    return
                
                progress = 0.1 + 0.9 * (i / total)
                self.progress_signal.emit(progress, f"正在卸载 {pkg}...")
                
                # 使用 -y 自动确认
                self._run_pip(["uninstall", "-y", pkg])
            
            self.progress_signal.emit(1.0, "卸载完成")
            self.finished_signal.emit(True)
            
        except Exception as e:
            import traceback
            self.error_signal.emit(f"卸载失败: {e}\n{traceback.format_exc()}")
            self.finished_signal.emit(False)

    def _run_pip(self, args: List[str]) -> bool:
        """运行 pip 命令

        Returns:
            是否成功
        """
        cmd = [self._python_path, "-m", "pip"] + args

        self.log_signal.emit(f"执行: {' '.join(cmd)}")
        print(f"执行: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            # 实时输出日志
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log_signal.emit(line)
                    print(line)

            process.wait()
            return process.returncode == 0

        except Exception as e:
            self.log_signal.emit(f"命令执行失败: {e}")
            print(f"命令执行失败: {e}")
            return False

    @staticmethod
    def get_install_size_estimate() -> str:
        """获取安装大小估算"""
        return "约 3-5 GB（含 PyTorch CUDA）"
