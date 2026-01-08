from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PreflightSeverity(str, Enum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True)
class PreflightIssue:
    severity: PreflightSeverity
    title: str
    detail: str
    suggestion: str


@dataclass(frozen=True)
class GPUInfo:
    names: tuple[str, ...]
    vendor: str | None
    total_vram_gib: float | None


@dataclass(frozen=True)
class IndexTTSPreflightResult:
    issues: tuple[PreflightIssue, ...]
    gpu: GPUInfo
    os_name: str
    os_version: str
    free_disk_gib: float | None
    ram_gib: float | None

    @property
    def has_blockers(self) -> bool:
        return any(i.severity == PreflightSeverity.BLOCK for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == PreflightSeverity.WARN for i in self.issues)


class IndexTTSPreflightUtility:
    """IndexTTS2 运行前预检（尽量不依赖重依赖，如 torch）。

    目的：在用户首次点击“下载依赖和模型”时，给出是否建议/是否允许继续下载的判断。
    """

    # UI 内提示“约 5GB”，但考虑下载/缓存/解压/依赖，预留更安全。
    MIN_FREE_DISK_GIB = 8.0
    RECOMMENDED_FREE_DISK_GIB = 12.0

    # 模型推理通常需要 CUDA；低于该显存容易直接 OOM。
    MIN_VRAM_GIB = 6.0
    RECOMMENDED_VRAM_GIB = 8.0

    MIN_RAM_GIB_WARN = 16.0
    MIN_RAM_GIB_BLOCK = 8.0

    @staticmethod
    def run_check(save_dir: str) -> IndexTTSPreflightResult:
        issues: list[PreflightIssue] = []

        os_name = platform.system() or "Unknown"
        os_version = platform.version() or ""

        # 1) OS 兼容性
        if os_name.lower() == "darwin":
            issues.append(
                PreflightIssue(
                    severity=PreflightSeverity.BLOCK,
                    title="当前系统为 macOS",
                    detail="IndexTTS2 推理通常依赖 NVIDIA CUDA；macOS 设备一般无法满足该运行条件。",
                    suggestion="建议在 Windows（NVIDIA 独显）/ Linux（NVIDIA 独显）设备上运行。",
                )
            )

        # 2) GPU/显存
        gpu = IndexTTSPreflightUtility._detect_gpu_info()
        issues.extend(IndexTTSPreflightUtility._evaluate_gpu(gpu))

        # 3) 磁盘空间（以模型保存目录所在磁盘为准）
        free_disk_gib = IndexTTSPreflightUtility._get_free_disk_gib(save_dir)
        if free_disk_gib is not None:
            if free_disk_gib < IndexTTSPreflightUtility.MIN_FREE_DISK_GIB:
                issues.append(
                    PreflightIssue(
                        severity=PreflightSeverity.BLOCK,
                        title="磁盘空间不足",
                        detail=f"模型与依赖下载/解压预计需要至少 {IndexTTSPreflightUtility.MIN_FREE_DISK_GIB:.0f}GB 可用空间；当前仅约 {free_disk_gib:.1f}GB。",
                        suggestion="请先清理磁盘空间，或把模型目录放到空间更大的磁盘后再下载。",
                    )
                )
            elif free_disk_gib < IndexTTSPreflightUtility.RECOMMENDED_FREE_DISK_GIB:
                issues.append(
                    PreflightIssue(
                        severity=PreflightSeverity.WARN,
                        title="磁盘空间偏紧",
                        detail=f"当前可用空间约 {free_disk_gib:.1f}GB，可能因缓存/临时文件导致下载失败。",
                        suggestion=f"建议至少保留 {IndexTTSPreflightUtility.RECOMMENDED_FREE_DISK_GIB:.0f}GB 可用空间，以提升成功率。",
                    )
                )
        else:
            issues.append(
                PreflightIssue(
                    severity=PreflightSeverity.WARN,
                    title="无法读取磁盘可用空间",
                    detail="未能获取模型目录所在磁盘的可用空间，可能影响下载稳定性判断。",
                    suggestion="如后续下载失败，请优先检查磁盘剩余空间是否充足。",
                )
            )

        # 4) 内存（RAM）
        ram_gib = IndexTTSPreflightUtility._get_total_ram_gib()
        if ram_gib is not None:
            if ram_gib < IndexTTSPreflightUtility.MIN_RAM_GIB_BLOCK:
                issues.append(
                    PreflightIssue(
                        severity=PreflightSeverity.BLOCK,
                        title="系统内存过低",
                        detail=f"检测到系统内存约 {ram_gib:.1f}GB，可能无法稳定安装依赖或运行推理。",
                        suggestion=f"建议至少 {IndexTTSPreflightUtility.MIN_RAM_GIB_WARN:.0f}GB 内存；最低也建议不低于 {IndexTTSPreflightUtility.MIN_RAM_GIB_BLOCK:.0f}GB。",
                    )
                )
            elif ram_gib < IndexTTSPreflightUtility.MIN_RAM_GIB_WARN:
                issues.append(
                    PreflightIssue(
                        severity=PreflightSeverity.WARN,
                        title="系统内存偏低",
                        detail=f"检测到系统内存约 {ram_gib:.1f}GB，可能出现安装慢/运行卡顿/生成失败。",
                        suggestion="建议关闭其他大型程序或提高内存配置后再使用。",
                    )
                )
        else:
            issues.append(
                PreflightIssue(
                    severity=PreflightSeverity.WARN,
                    title="无法读取系统内存信息",
                    detail="未能获取系统内存大小，无法给出更准确的稳定性建议。",
                    suggestion="如遇到安装失败/运行崩溃，请优先检查内存占用与可用内存。",
                )
            )

        return IndexTTSPreflightResult(
            issues=tuple(issues),
            gpu=gpu,
            os_name=os_name,
            os_version=os_version,
            free_disk_gib=free_disk_gib,
            ram_gib=ram_gib,
        )

    @staticmethod
    def format_report_text(result: IndexTTSPreflightResult) -> str:
        lines: list[str] = []

        # 概览
        gpu_name = " / ".join(result.gpu.names) if result.gpu.names else "未检测到"
        vram_text = (
            f"{result.gpu.total_vram_gib:.1f}GB" if result.gpu.total_vram_gib is not None else "未知"
        )
        disk_text = f"{result.free_disk_gib:.1f}GB" if result.free_disk_gib is not None else "未知"
        ram_text = f"{result.ram_gib:.1f}GB" if result.ram_gib is not None else "未知"

        lines.append("设备检测结果：")
        lines.append(f"- 系统：{result.os_name} {result.os_version}")
        lines.append(f"- 显卡：{gpu_name}")
        lines.append(f"- 显存：{vram_text}")
        lines.append(f"- 内存：{ram_text}")
        lines.append(f"- 磁盘可用：{disk_text}")

        if not result.issues:
            lines.append("\n未发现明显风险：可以继续下载依赖和模型。")
            return "\n".join(lines)

        # 问题列表
        lines.append("\n检测到以下风险/限制：")
        for issue in result.issues:
            tag = "阻断" if issue.severity == PreflightSeverity.BLOCK else "建议"
            lines.append(f"\n[{tag}] {issue.title}")
            lines.append(f"- 说明：{issue.detail}")
            lines.append(f"- 建议：{issue.suggestion}")

        return "\n".join(lines)

    @staticmethod
    def format_terminal_block(result: IndexTTSPreflightResult) -> str:
        """给运行时终端输出的结构化文本（更适合日志阅读）。"""
        header = "=" * 68

        gpu_name = " / ".join(result.gpu.names) if result.gpu.names else "未检测到"
        vram_text = (
            f"{result.gpu.total_vram_gib:.1f}GB" if result.gpu.total_vram_gib is not None else "未知"
        )
        disk_text = f"{result.free_disk_gib:.1f}GB" if result.free_disk_gib is not None else "未知"
        ram_text = f"{result.ram_gib:.1f}GB" if result.ram_gib is not None else "未知"

        lines: list[str] = []
        lines.append(header)
        lines.append("[IndexTTS2 Preflight] 运行设备检测")
        lines.append(f"- OS        : {result.os_name} {result.os_version}")
        lines.append(f"- GPU       : {gpu_name}")
        lines.append(f"- VRAM      : {vram_text}")
        lines.append(f"- RAM       : {ram_text}")
        lines.append(f"- Free Disk : {disk_text}")

        if not result.issues:
            lines.append("- Verdict   : PASS")
            lines.append(header)
            return "\n".join(lines)

        blockers = [i for i in result.issues if i.severity == PreflightSeverity.BLOCK]
        warns = [i for i in result.issues if i.severity == PreflightSeverity.WARN]

        verdict = "BLOCK" if blockers else "WARN"
        lines.append(f"- Verdict   : {verdict}")

        def _emit(title: str, items: Iterable[PreflightIssue]):
            items = list(items)
            if not items:
                return
            lines.append("")
            lines.append(title)
            for idx, issue in enumerate(items, start=1):
                lines.append(f"  {idx}. {issue.title}")
                lines.append(f"     - detail: {issue.detail}")
                lines.append(f"     - suggest: {issue.suggestion}")

        _emit("Blockers:", blockers)
        _emit("Warnings:", warns)
        lines.append(header)
        return "\n".join(lines)

    @staticmethod
    def _evaluate_gpu(gpu: GPUInfo) -> list[PreflightIssue]:
        issues: list[PreflightIssue] = []

        vendor = (gpu.vendor or "").lower()
        names_joined = " ".join(gpu.names).lower()

        has_nvidia = "nvidia" in vendor or "nvidia" in names_joined or "geforce" in names_joined or "rtx" in names_joined
        has_amd = "amd" in vendor or "radeon" in names_joined
        has_intel = "intel" in vendor or "intel" in names_joined or "uhd" in names_joined or "iris" in names_joined

        # 本轮需求：AMD / 无独显 / 显存过低 一律阻断（完全不允许下载）
        if not gpu.names:
            issues.append(
                PreflightIssue(
                    severity=PreflightSeverity.BLOCK,
                    title="未检测到可用显卡信息",
                    detail="无法确认设备具备 NVIDIA CUDA 环境；IndexTTS2 需要 NVIDIA 显卡才能稳定运行。",
                    suggestion="请确认已安装 NVIDIA 驱动并可运行 nvidia-smi；或更换到带 NVIDIA 独显的设备后再下载。",
                )
            )
            return issues

        if not has_nvidia:
            title = "未检测到 NVIDIA 独显"
            if has_amd:
                title = "检测到 AMD 显卡（不支持）"
            elif has_intel:
                title = "检测到 Intel 核显/集显（不支持）"

            issues.append(
                PreflightIssue(
                    severity=PreflightSeverity.BLOCK,
                    title=title,
                    detail="IndexTTS2 推理依赖 NVIDIA CUDA；当前设备不满足运行条件。",
                    suggestion="请使用带 NVIDIA 独显的设备（建议 8GB+ 显存）后再下载。",
                )
            )
            return issues

        # 如果能读到显存，做阈值判断
        if gpu.total_vram_gib is not None:
            if gpu.total_vram_gib < IndexTTSPreflightUtility.MIN_VRAM_GIB:
                issues.append(
                    PreflightIssue(
                        severity=PreflightSeverity.BLOCK,
                        title="显存过低（不支持）",
                        detail=f"检测到显存约 {gpu.total_vram_gib:.1f}GB，低于最低要求 {IndexTTSPreflightUtility.MIN_VRAM_GIB:.0f}GB。",
                        suggestion=f"建议使用 {IndexTTSPreflightUtility.RECOMMENDED_VRAM_GIB:.0f}GB+ 显存的 NVIDIA 显卡后再下载与运行。",
                    )
                )
            elif gpu.total_vram_gib < IndexTTSPreflightUtility.RECOMMENDED_VRAM_GIB:
                issues.append(
                    PreflightIssue(
                        severity=PreflightSeverity.WARN,
                        title="显存偏紧",
                        detail=f"检测到显存约 {gpu.total_vram_gib:.1f}GB，可能出现加载慢或生成失败。",
                        suggestion=f"建议 {IndexTTSPreflightUtility.RECOMMENDED_VRAM_GIB:.0f}GB+ 显存以获得更稳定体验。",
                    )
                )
        else:
            issues.append(
                PreflightIssue(
                    severity=PreflightSeverity.WARN,
                    title="无法读取显存大小",
                    detail="已检测到 NVIDIA 显卡，但未能读取显存大小，无法判断是否满足最低显存要求。",
                    suggestion="建议在终端运行 nvidia-smi 验证显存，并确保驱动安装正常。",
                )
            )

        return issues

    @staticmethod
    def _get_free_disk_gib(save_dir: str) -> float | None:
        try:
            path = os.path.abspath(save_dir or ".")
            # disk_usage 需要存在的路径
            probe_path = path if os.path.exists(path) else os.path.dirname(path)
            if not probe_path or not os.path.exists(probe_path):
                probe_path = os.getcwd()
            usage = shutil.disk_usage(probe_path)
            return usage.free / (1024 ** 3)
        except Exception:
            return None

    @staticmethod
    def _get_total_ram_gib() -> float | None:
        try:
            import psutil

            return psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            return None

    @staticmethod
    def _detect_gpu_info() -> GPUInfo:
        """尽力检测 GPU 名称与显存。

        - Windows：优先 nvidia-smi（若存在），否则 wmic
        - 其他：优先 nvidia-smi
        """

        # 1) nvidia-smi（更可靠的显存数）
        smi = IndexTTSPreflightUtility._try_nvidia_smi()
        if smi is not None:
            return smi

        # 2) Windows: wmic
        if (platform.system() or "").lower() == "windows":
            wmic = IndexTTSPreflightUtility._try_wmic_gpu()
            if wmic is not None:
                return wmic

        # 3) fallback
        return GPUInfo(names=tuple(), vendor=None, total_vram_gib=None)

    @staticmethod
    def _try_nvidia_smi() -> GPUInfo | None:
        try:
            proc = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if proc.returncode != 0:
                return None
            out = (proc.stdout or "").strip()
            if not out:
                return None

            names: list[str] = []
            max_mem_mib: float | None = None
            for line in out.splitlines():
                parts = [p.strip() for p in line.split(",")]
                if not parts:
                    continue
                name = parts[0] if len(parts) >= 1 else ""
                mem = parts[1] if len(parts) >= 2 else ""
                if name:
                    names.append(name)
                try:
                    mem_mib = float(re.sub(r"[^0-9.]", "", mem))
                    max_mem_mib = mem_mib if max_mem_mib is None else max(max_mem_mib, mem_mib)
                except Exception:
                    pass

            total_vram_gib = (max_mem_mib / 1024.0) if max_mem_mib is not None else None
            return GPUInfo(names=tuple(names), vendor="nvidia", total_vram_gib=total_vram_gib)
        except Exception:
            return None

    @staticmethod
    def _try_wmic_gpu() -> GPUInfo | None:
        try:
            proc = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if proc.returncode != 0:
                return None

            text_out = (proc.stdout or "").strip()
            if not text_out:
                return None

            lines = [ln.strip() for ln in text_out.splitlines() if ln.strip()]
            if len(lines) <= 1:
                return None

            # 跳过 header
            data_lines = lines[1:]
            names: list[str] = []
            max_ram_bytes: int | None = None

            for ln in data_lines:
                # wmic 输出通常是：<AdapterRAM><spaces><Name>
                m = re.match(r"^(\d+)\s+(.*)$", ln)
                if m:
                    ram_bytes = int(m.group(1))
                    name = m.group(2).strip()
                else:
                    # 兜底：仅取最后一段当 name
                    ram_bytes = 0
                    name = ln.strip()

                if name:
                    names.append(name)
                if ram_bytes > 0:
                    max_ram_bytes = ram_bytes if max_ram_bytes is None else max(max_ram_bytes, ram_bytes)

            total_vram_gib = (max_ram_bytes / (1024 ** 3)) if max_ram_bytes is not None else None

            vendor = None
            joined = " ".join(names).lower()
            if "nvidia" in joined:
                vendor = "nvidia"
            elif "amd" in joined or "radeon" in joined:
                vendor = "amd"
            elif "intel" in joined:
                vendor = "intel"

            return GPUInfo(names=tuple(names), vendor=vendor, total_vram_gib=total_vram_gib)
        except Exception:
            return None
