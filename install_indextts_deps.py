"""
IndexTTS2 依赖安装脚本

将 IndexTTS2 所需的全部依赖安装到 AudioBoxTTS\Python3 环境中。

使用方法：
    方式1: 双击运行 install_indextts_deps.bat
    方式2: cd AudioBoxTTS && Python3\python.exe install_indextts_deps.py

注意事项：
1. 需要稳定的网络连接
2. PyTorch 升级可能需要较长时间（约 2-3GB 下载）
3. 如果网络不稳定，可以分步执行脚本中的命令
"""
import subprocess
import sys
import os


def get_python_exe():
    """获取项目专属的 Python 解释器路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = os.path.join(script_dir, "Python3", "python.exe")
    if os.path.exists(python_exe):
        return python_exe
    return sys.executable


def run_pip(args, description=""):
    """运行 pip 命令"""
    python_exe = get_python_exe()
    cmd = [python_exe, "-m", "pip"] + args
    print(f"\n{'='*60}")
    if description:
        print(f"📦 {description}")
    print(f"运行: {' '.join(cmd)}")
    print("="*60)
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║              IndexTTS2 依赖安装脚本                          ║
║                                                              ║
║  此脚本将安装 AI 语音模块所需的全部依赖                      ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    python_exe = get_python_exe()
    print(f"🐍 Python 环境: {python_exe}")
    
    # 检查 Python 版本
    result = subprocess.run([python_exe, "--version"], capture_output=True, text=True)
    print(f"🐍 Python 版本: {result.stdout.strip()}")
    
    # ==========================================
    # 第一步：升级 pip
    # ==========================================
    run_pip(["install", "--upgrade", "pip"], "升级 pip")
    
    # ==========================================
    # 第二步：安装/升级 PyTorch (CUDA 12.8)
    # ==========================================
    print("\n" + "="*60)
    print("🔥 第1步: 安装 PyTorch 2.8.x (CUDA 12.8)")
    print("⚠️  这可能需要较长时间，请耐心等待...")
    print("="*60)
    
    run_pip([
        "install",
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "--index-url", "https://download.pytorch.org/whl/cu128"
    ], "安装 PyTorch 2.8.0 + CUDA 12.8")
    
    # ==========================================
    # 第三步：安装缺失的核心依赖
    # ==========================================
    print("\n" + "="*60)
    print("📦 第2步: 安装缺失的核心依赖")
    print("="*60)
    
    # 核心依赖列表（pyproject.toml 中定义但尚未安装的）
    # 注意：这些包在首次安装后可能已存在，pip 会自动跳过
    core_deps = [
        "cython==3.0.7",
        "descript-audiotools==0.7.2",
        "ffmpeg-python==0.2.0",
        "json5==0.10.0",
        "matplotlib==3.8.2",
        "opencv-python==4.9.0.80",
        "pandas==2.3.2",
        "pandas-stubs",
        "textstat>=0.7.10",
        "wetext>=0.0.9",  # Windows 版本的文本处理
        # IndexTTS2 核心依赖
        "accelerate==1.8.1",
        "cn2an==0.5.22",
        "einops>=0.8.1",
        "g2p-en==2.1.0",
        "jieba==0.42.1",
        "librosa==0.10.2.post1",
        "modelscope",
        "munch==4.0.0",
        "numba==0.58.1",
        "numpy==1.26.2",
        "omegaconf>=2.3.0",
        "safetensors==0.5.2",
        "sentencepiece>=0.2.1",
        "tokenizers",
        "transformers==4.52.1",
    ]
    
    run_pip(["install"] + core_deps, "安装核心依赖")
    
    # ==========================================
    # 第四步：安装可选依赖（keras, tensorboard）
    # ==========================================
    print("\n" + "="*60)
    print("📦 第3步: 安装可选依赖 (keras, tensorboard)")
    print("="*60)
    
    optional_deps = [
        "keras==2.9.0",
        "tensorboard==2.9.1",
    ]
    
    # keras 2.9.0 需要特定版本的 tensorflow，可能有兼容性问题
    # 这里我们尝试安装，如果失败则跳过
    try:
        run_pip(["install"] + optional_deps, "安装可选依赖")
    except Exception as e:
        print(f"⚠️ 可选依赖安装失败（不影响核心功能）: {e}")
    
    # ==========================================
    # 第五步：验证安装
    # ==========================================
    print("\n" + "="*60)
    print("🔍 第4步: 验证安装")
    print("="*60)
    
    verify_script = '''
import sys
print(f"Python: {sys.version}")

# 检查 PyTorch
try:
    import torch
    print(f"✅ torch: {torch.__version__}")
    print(f"   CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA 版本: {torch.version.cuda}")
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"❌ torch: {e}")

# 检查 torchaudio
try:
    import torchaudio
    print(f"✅ torchaudio: {torchaudio.__version__}")
except Exception as e:
    print(f"❌ torchaudio: {e}")

# 检查 transformers
try:
    import transformers
    print(f"✅ transformers: {transformers.__version__}")
except Exception as e:
    print(f"❌ transformers: {e}")

# 检查 librosa
try:
    import librosa
    print(f"✅ librosa: {librosa.__version__}")
except Exception as e:
    print(f"❌ librosa: {e}")

# 检查 descript-audiotools
try:
    import audiotools
    print(f"✅ audiotools (descript-audiotools)")
except Exception as e:
    print(f"❌ audiotools: {e}")

# 检查 wetext
try:
    import wetext
    print(f"✅ wetext")
except Exception as e:
    print(f"⚠️ wetext: {e} (可选)")

# 检查 indextts 模块
try:
    import sys
    import os
    # 添加 Source 目录到路径
    script_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
    source_dir = os.path.join(script_dir, "Source")
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)
    
    from indextts import infer
    print(f"✅ indextts 模块可导入")
except Exception as e:
    print(f"❌ indextts: {e}")

print()
print("="*50)
print("验证完成！如果主要依赖都显示 ✅，则安装成功。")
print("="*50)
'''
    
    # 将验证脚本保存到临时文件并执行
    verify_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_verify_deps.py")
    with open(verify_file, "w", encoding="utf-8") as f:
        f.write(verify_script)
    
    subprocess.run([python_exe, verify_file])
    
    # 删除临时文件
    try:
        os.remove(verify_file)
    except:
        pass
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║                       安装完成！                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  下一步操作：                                                ║
║  1. 启动音频工具箱                                          ║
║  2. 点击左侧「AI语音」                                       ║
║  3. 首次使用需要「下载模型」（约 4.6GB）                     ║
║  4. 点击「加载模型」开始使用                                ║
║                                                              ║
║  如果遇到问题，请查看 INDEXTTS_README.md                     ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
