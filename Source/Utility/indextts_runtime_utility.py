import os
import shutil
from dataclasses import dataclass


_DEFAULT_PYPROJECT_TOML = """[project]
name = \"indextts\"
version = \"2.0.0\"
description = \"IndexTTS2 runtime environment (managed by uv)\"
requires-python = \">=3.10\"
dependencies = [
    \"accelerate==1.8.1\",
    \"cn2an==0.5.22\",
    \"cython==3.0.7\",
    \"descript-audiotools==0.7.2\",
    \"einops>=0.8.1\",
    \"ffmpeg-python==0.2.0\",
    \"g2p-en==2.1.0\",
    \"jieba==0.42.1\",
    \"json5==0.10.0\",
    \"keras==2.9.0\",
    \"librosa==0.10.2.post1\",
    \"matplotlib==3.8.2\",
    \"modelscope==1.27.0\",
    \"munch==4.0.0\",
    \"numba==0.58.1\",
    \"numpy==1.26.2\",
    \"omegaconf>=2.3.0\",
    \"opencv-python==4.9.0.80\",
    \"pandas==2.3.2\",
    \"pandas-stubs~=2.3.2\",
    \"safetensors==0.5.2\",
    \"sentencepiece>=0.2.1\",
    \"tensorboard==2.9.1\",
    \"textstat>=0.7.10\",
    \"tokenizers==0.21.0\",
    \"torch==2.8.*\",
    \"torchaudio==2.8.*\",
    \"tqdm>=4.67.1\",
    \"transformers==4.52.1\",
    \"wetext>=0.0.9; sys_platform != 'linux'\",
    \"WeTextProcessing; sys_platform == 'linux'\",
]

[project.optional-dependencies]
webui = [\"gradio==5.45.0\"]
deepspeed = [\"deepspeed==0.17.1\"]

[build-system]
requires = [\"hatchling >= 1.27.0\"]
build-backend = \"hatchling.build\"

[tool.uv]
no-build-isolation-package = [\"deepspeed\"]

[tool.uv.sources]
torch = [
    { index = \"pytorch-cuda\", marker = \"sys_platform == 'linux' or sys_platform == 'win32'\" },
]
torchaudio = [
    { index = \"pytorch-cuda\", marker = \"sys_platform == 'linux' or sys_platform == 'win32'\" },
]
torchvision = [
    { index = \"pytorch-cuda\", marker = \"sys_platform == 'linux' or sys_platform == 'win32'\" },
]

[[tool.uv.index]]
name = \"pytorch-cuda\"
url = \"https://download.pytorch.org/whl/cu128\"
explicit = true
"""


@dataclass(frozen=True)
class IndexTTSRuntimePaths:
    repo_root: str
    runtime_root: str
    pyproject_path: str
    venv_dir: str
    venv_python: str
    engine_worker: str


def _repo_root() -> str:
    # __file__ = <repo>/Source/Utility/indextts_runtime_utility.py
    # repo root should be: <repo>
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _legacy_repo_root() -> str:
    """Historical fallback.

    Previous versions mistakenly treated `<repo>/Source/Utility` as if it were
    one directory deeper, resulting in repo root being one level too high.
    We keep this to avoid breaking users who already installed to that path.
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def get_runtime_paths() -> IndexTTSRuntimePaths:
    repo_root = _repo_root()
    runtime_root = os.path.join(repo_root, "Runtime", "IndexTTS2")
    pyproject_path = os.path.join(runtime_root, "pyproject.toml")
    venv_dir = os.path.join(runtime_root, ".venv")

    # Legacy fallback: if user already has an installed runtime under the old
    # computed root, keep using it.
    legacy_repo = _legacy_repo_root()
    legacy_runtime = os.path.join(legacy_repo, "Runtime", "IndexTTS2")
    legacy_pyproject = os.path.join(legacy_runtime, "pyproject.toml")
    legacy_venv = os.path.join(legacy_runtime, ".venv")

    if (os.path.exists(legacy_pyproject) or os.path.exists(legacy_venv)) and not (
        os.path.exists(pyproject_path) or os.path.exists(venv_dir)
    ):
        repo_root = legacy_repo
        runtime_root = legacy_runtime
        pyproject_path = legacy_pyproject
        venv_dir = legacy_venv

    if os.name == "nt":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    engine_worker = os.path.join(runtime_root, "engine_worker.py")

    return IndexTTSRuntimePaths(
        repo_root=repo_root,
        runtime_root=runtime_root,
        pyproject_path=pyproject_path,
        venv_dir=venv_dir,
        venv_python=venv_python,
        engine_worker=engine_worker,
    )


def ensure_runtime_pyproject() -> None:
    """Ensure Runtime/IndexTTS2/pyproject.toml exists.

    If missing, copy from repo root ttspyproject.toml (migration convenience).
    """
    paths = get_runtime_paths()
    os.makedirs(paths.runtime_root, exist_ok=True)

    if os.path.exists(paths.pyproject_path):
        return

    fallback = os.path.join(paths.repo_root, "ttspyproject.toml")
    if os.path.exists(fallback):
        shutil.copyfile(fallback, paths.pyproject_path)
        return

    # Last resort: generate a default pyproject.toml so the GUI can self-heal
    # even if the Runtime folder was not shipped/checked-out.
    with open(paths.pyproject_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_DEFAULT_PYPROJECT_TOML)
