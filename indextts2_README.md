

## Usage Instructions

### ⚙️ Environment Setup

1. Ensure that you have both [git](https://git-scm.com/downloads)
   and [git-lfs](https://git-lfs.com/) on your system.

The Git-LFS plugin must also be enabled on your current user account:

```bash
git lfs install
```

2. Download this repository:

```bash
git clone https://github.com/index-tts/index-tts.git && cd index-tts
git lfs pull  # download large repository files
```

3. Install the [uv package manager](https://docs.astral.sh/uv/getting-started/installation/).
   It is *required* for a reliable, modern installation environment.

> [!TIP]
> **Quick & Easy Installation Method:**
> 
> There are many convenient ways to install the `uv` command on your computer.
> Please check the link above to see all options. Alternatively, if you want
> a very quick and easy method, you can install it as follows:
> 
> ```bash
> pip install -U uv
> ```

> [!WARNING]
> We **only** support the `uv` installation method. Other tools, such as `conda`
> or `pip`, don't provide any guarantees that they will install the correct
> dependency versions. You will almost certainly have *random bugs, error messages,*
> ***missing GPU acceleration**, and various other problems* if you don't use `uv`.
> Please *do not report any issues* if you use non-standard installations, since
> almost all such issues are invalid.
> 
> Furthermore, `uv` is [up to 115x faster](https://github.com/astral-sh/uv/blob/main/BENCHMARKS.md)
> than `pip`, which is another *great* reason to embrace the new industry-standard
> for Python project management.

4. Install required dependencies:

We use `uv` to manage the project's dependency environment. The following command
will *automatically* create a `.venv` project-directory and then installs the correct
versions of Python and all required dependencies:

```bash
uv sync --all-extras
```

If the download is slow, please try a *local mirror*, for example any of these
local mirrors in China (choose one mirror from the list below):

```bash
uv sync --all-extras --default-index "https://mirrors.aliyun.com/pypi/simple"

uv sync --all-extras --default-index "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
```

> [!TIP]
> **Available Extra Features:**
> 
> - `--all-extras`: Automatically adds *every* extra feature listed below. You can
>   remove this flag if you want to customize your installation choices.
> - `--extra webui`: Adds WebUI support (recommended).
> - `--extra deepspeed`: Adds DeepSpeed support (may speed up inference on some
>   systems).

> [!IMPORTANT]
> **Important (Windows):** The DeepSpeed library may be difficult to install for
> some Windows users. You can skip it by removing the `--all-extras` flag. If you
> want any of the other extra features above, you can manually add their specific
> feature flags instead.
> 
> **Important (Linux/Windows):** If you see an error about CUDA during the installation,
> please ensure that you have installed NVIDIA's [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit)
> version **12.8** (or newer) on your system.

5. Download the required models via [uv tool](https://docs.astral.sh/uv/guides/tools/#installing-tools):

Download via `huggingface-cli`:

```bash
uv tool install "huggingface-hub[cli,hf_xet]"

hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints
```

Or download via `modelscope`:

```bash
uv tool install "modelscope"

modelscope download --model IndexTeam/IndexTTS-2 --local_dir checkpoints
```

> [!IMPORTANT]
> If the commands above aren't available, please carefully read the `uv tool`
> output. It will tell you how to add the tools to your system's path.

> [!NOTE]
> In addition to the above models, some small models will also be automatically
> downloaded when the project is run for the first time. If your network environment
> has slow access to HuggingFace, it is recommended to execute the following
> command before running the code:
> 
> ```bash
> export HF_ENDPOINT="https://hf-mirror.com"
> ```


#### 🖥️ Checking PyTorch GPU Acceleration

If you need to diagnose your environment to see which GPUs are detected,
you can use our included utility to check your system:

```bash
uv run tools/gpu_check.py
```


### 🔥 IndexTTS2 Quickstart

#### 🌐 Web Demo

```bash
uv run webui.py
```

Open your browser and visit `http://127.0.0.1:7860` to see the demo.

You can also adjust the settings to enable features such as FP16 inference (lower
VRAM usage), DeepSpeed acceleration, compiled CUDA kernels for speed, etc. All
available options can be seen via the following command:

```bash
uv run webui.py -h
```

Have fun!

> [!IMPORTANT]
> It can be very helpful to use **FP16** (half-precision) inference. It is faster
> and uses less VRAM, with a very small quality loss.
> 
> **DeepSpeed** *may* also speed up inference on some systems, but it could also
> make it slower. The performance impact is highly dependent on your specific
> hardware, drivers and operating system. Please try with and without it,
> to discover what works best on your personal system.
> 
> Lastly, be aware that *all* `uv` commands will **automatically activate** the correct
> per-project virtual environments. Do *not* manually activate any environments
> before running `uv` commands, since that could lead to dependency conflicts!
