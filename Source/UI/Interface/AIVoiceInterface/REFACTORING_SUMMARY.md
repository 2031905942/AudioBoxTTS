# AIVoiceInterface 重构说明（最新版）

> 本文用于记录 AIVoiceInterface 从“单文件巨石”到“模块化结构”的演进结果，并说明当前推荐的入口与目录组织。

## 背景

此前 AIVoiceInterface 曾长期以单个文件承载 UI、业务逻辑、对话框、历史记录与项目切换等功能（约 5,000+ 行），维护成本高、定位功能困难，也容易引入耦合与回归。

## 当前结构（真实结构）

当前 AIVoiceInterface 包目录以“职责分层”为主：

```
Source/UI/Interface/AIVoiceInterface/
├── __init__.py
├── REFACTORING_SUMMARY.md
│
├── core/
│   ├── __init__.py
│   ├── interface.py
│   ├── environment_worker.py
│   └── ui_overlays.py
│
├── controllers/
│   ├── __init__.py
│   ├── ui_builder.py
│   ├── character_operations.py
│   ├── model_management.py
│   ├── download_manager.py
│   ├── audio_operations.py
│   ├── generation_controller.py
│   ├── history_manager.py
│   ├── project_tab_controller.py
│   └── onboarding_guide.py
│
├── dialogs/
│   ├── __init__.py
│   ├── download.py
│   ├── environment.py
│   ├── model_actions.py
│   ├── online_model.py
│   ├── welcome.py
│   ├── diagnostics.py
│   ├── delete_assets.py
│   ├── character_dialog.py
│   ├── batch_delete_characters_dialog.py
│   ├── import_result_dialog.py
│   └── wwise_workunit_import_dialog.py
│
├── models/
│   ├── __init__.py
│   └── character_manager.py
│
├── widgets/
│   ├── __init__.py
│   ├── audio_player_widget.py
│   ├── character_button.py
│   └── character_list_widget.py
│
└── windows/
    ├── __init__.py
    └── history_window.py
```

## 入口与导入方式（重要）

本仓库已移除“向后兼容 facade / stub 文件”（例如旧的 ai_voice_interface.py 兼容层）。

当前推荐使用包根导入：

```python
from Source.UI.Interface.AIVoiceInterface import AIVoiceInterface
```

主类实现位于 core：

```python
from Source.UI.Interface.AIVoiceInterface.core.interface import AIVoiceInterface
```

## 设计要点

### 1) Mixin 负责拆分职责

core/interface.py 的 AIVoiceInterface 主要负责“组装与调度”，具体能力按主题分散到 controllers/* 的 mixin 中（UI 构建、下载、生成、历史、项目切换、新手引导等）。

### 2) UI 组件与窗口独立

- 可复用的小组件放在 widgets/*。
- 独立窗口（例如历史记录窗口）放在 windows/*。

### 3) 项目隔离的输出目录（已更新）

生成音频与历史记录默认写入 temp_output 下的“按项目隔离目录”。

- 旧实现：使用项目 UUID 作为目录名
- 当前实现：使用“项目名”作为目录名，并通过稳定后缀保证唯一性

例如：

```
temp_output/海航/
temp_output/海航-1a2b3c4d/
```

其中目录内会写入一个 .project_id 标记文件，用于在项目重命名时识别同一项目（尽量复用/重命名目录）。

## 维护建议

- 新增功能优先放入对应 mixin（controllers/），避免 core/interface.py 再次膨胀。
- 通用 UI 小组件放 widgets/；对话框放 dialogs/；独立窗口放 windows/。
- 项目/历史相关路径逻辑统一走 Source/Utility/tts_history_utility.py，避免散落多处。
)
```

### New Style (recommended)
```python
from Source.UI.Interface.AIVoiceInterface import AIVoiceInterface
from Source.UI.Interface.AIVoiceInterface.dialogs import (
    DownloadModelChoiceDialog,
    LocalModelActionsDialog
)
```

## Testing Recommendations

1. **Smoke Tests**
   - Launch the application
   - Create a new character
   - Import reference audio
   - Download and load model
   - Generate audio samples
   - Switch between projects
   - Open history window

2. **Integration Tests**
   - Verify all signals connect properly
   - Test drag-drop functionality
   - Test keyboard shortcuts
   - Verify dialog workflows

3. **Regression Tests**
   - Compare behavior with previous version
   - Check for any missing functionality
   - Verify error handling

## Future Enhancements

With this new structure, future improvements are easier:

1. **Add Unit Tests**
   - Each mixin can be tested independently
   - Mock dependencies easily

2. **Add Type Hints**
   - Smaller files make type checking more manageable

3. **Plugin Architecture**
   - Easy to add new controller mixins
   - Extensible dialog system

4. **Performance Optimization**
   - Lazy loading of heavy components
   - Better separation of concerns

## Credits

Refactoring completed: 2026-01-20
- Separated 13 classes into 24 focused modules
- Maintained 100% backwards compatibility
- Zero breaking changes
- All syntax verified
