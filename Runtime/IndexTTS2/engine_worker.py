import json
import os
import sys
import traceback
from typing import Any, Dict, Optional


def _emit(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _set_progress_printer() -> Any:
    # IndexTTS2 expects a callable like gradio progress.
    def _progress(value: float, desc: str = "") -> None:
        try:
            _emit({"type": "progress", "value": float(value), "desc": desc or ""})
        except Exception:
            pass

    return _progress


def _handle_load(payload: Dict[str, Any], state: Dict[str, Any]) -> None:
    model_dir = payload.get("model_dir")
    cfg_path = payload.get("cfg_path")
    use_fp16 = bool(payload.get("use_fp16", False))
    use_cuda_kernel = bool(payload.get("use_cuda_kernel", False))
    use_deepspeed = bool(payload.get("use_deepspeed", False))

    if not model_dir or not cfg_path:
        _emit({"type": "error", "message": "model_dir/cfg_path 不能为空"})
        return

    try:
        from indextts.infer_v2 import IndexTTS2

        tts = IndexTTS2(
            cfg_path=cfg_path,
            model_dir=model_dir,
            use_fp16=use_fp16,
            use_cuda_kernel=use_cuda_kernel,
            use_deepspeed=use_deepspeed,
        )
        tts.gr_progress = _set_progress_printer()
        state["tts"] = tts

        device = str(getattr(tts, "device", ""))
        _emit({"type": "loaded", "device": device})
    except Exception as e:
        _emit({
            "type": "error",
            "message": f"加载模型失败: {e}",
            "trace": traceback.format_exc(),
        })


def _handle_synthesize(payload: Dict[str, Any], state: Dict[str, Any]) -> None:
    tts = state.get("tts")
    if tts is None:
        _emit({"type": "error", "message": "模型未加载"})
        return

    spk_audio_prompt = payload.get("spk_audio_prompt")
    text = (payload.get("text") or "").strip()
    output_path = payload.get("output_path")

    emo_mode = int(payload.get("emo_mode", 0))
    emo_vector = payload.get("emo_vector")
    emo_alpha = float(payload.get("emo_alpha", 1.0))

    generation_kwargs = payload.get("generation_kwargs")
    max_text_tokens_per_segment = payload.get("max_text_tokens_per_segment")

    if not spk_audio_prompt or not os.path.exists(spk_audio_prompt):
        _emit({"type": "error", "message": "参考音频不存在"})
        return

    if not text:
        _emit({"type": "error", "message": "文本不能为空"})
        return

    if not output_path:
        _emit({"type": "error", "message": "output_path 不能为空"})
        return

    try:
        tts.gr_progress = _set_progress_printer()

        kwargs: Dict[str, Any] = {
            "spk_audio_prompt": spk_audio_prompt,
            "text": text,
            "output_path": output_path,
            "verbose": False,
        }

        # 高级参数（可选）：由 GUI 下发
        if isinstance(generation_kwargs, dict) and generation_kwargs:
            kwargs["generation_kwargs"] = generation_kwargs
        if max_text_tokens_per_segment is not None:
            try:
                kwargs["max_text_tokens_per_segment"] = int(max_text_tokens_per_segment)
            except Exception:
                pass

        # 0: same-as-speaker (do nothing)
        # 2: vector mode
        if emo_mode == 2 and isinstance(emo_vector, list) and len(emo_vector) == 8:
            try:
                normalized_vec = tts.normalize_emo_vec(emo_vector, apply_bias=True)
                kwargs["emo_vector"] = normalized_vec
                kwargs["emo_alpha"] = emo_alpha
            except Exception:
                # fallback: send raw vector
                kwargs["emo_vector"] = emo_vector
                kwargs["emo_alpha"] = emo_alpha

        tts.infer(**kwargs)

        if os.path.exists(output_path):
            _emit({"type": "synthesized", "output_path": output_path, "sample_rate": 22050})
        else:
            _emit({"type": "error", "message": "推理完成但未生成文件"})

    except Exception as e:
        _emit({
            "type": "error",
            "message": f"推理失败: {e}",
            "trace": traceback.format_exc(),
        })
    finally:
        try:
            tts.gr_progress = None
        except Exception:
            pass


def main() -> int:
    _emit({"type": "ready", "pid": os.getpid()})

    state: Dict[str, Any] = {"tts": None}

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue

        try:
            msg = json.loads(raw)
        except Exception:
            _emit({"type": "error", "message": "协议错误：无法解析 JSON"})
            continue

        cmd = msg.get("cmd")
        payload = msg.get("payload") or {}

        if cmd == "ping":
            _emit({"type": "pong"})
            continue

        if cmd == "shutdown":
            _emit({"type": "bye"})
            return 0

        if cmd == "load_model":
            _handle_load(payload, state)
            continue

        if cmd == "synthesize":
            _handle_synthesize(payload, state)
            continue

        _emit({"type": "error", "message": f"未知命令: {cmd}"})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
