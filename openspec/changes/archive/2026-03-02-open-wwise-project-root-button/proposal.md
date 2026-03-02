## Why

当前在“项目”页选择了 Wwise 工程文件（`.wproj`）后，用户经常需要快速进入该工程根目录（例如核对 `GeneratedSoundBanks/`、查看工程结构或执行手动操作）。目前只能在资源管理器中自行定位到该路径，操作成本高且容易选错目录。

## What Changes

- 在“选择Wwise工程文件”按钮右侧新增按钮“打开Wwise工程根目录”。
- 该按钮仅在已成功选择 Wwise 工程文件后可用；未选择时保持禁用（或不显示，最终以现有组件交互约束为准）。
- 点击按钮后，系统在 Windows 文件资源管理器中打开 Wwise 工程根目录（即所选 `.wproj` 文件所在目录）。
- 若路径不存在/不可访问，系统给出明确提示且不崩溃。

## Capabilities

### New Capabilities
- `wwise-project-root-open`: 当用户已选择 `.wproj` 工程文件时，UI 提供“打开Wwise工程根目录”入口，一键在文件资源管理器打开该工程文件所在目录。

### Modified Capabilities
- （无）

## Impact

- UI：涉及 `Source/UI/Interface/ProjectInterface/project_tab_window.py` 中“Wwise工程”相关设置卡片/按钮布局与启用态逻辑。
- 平台行为：新增 Windows 下“打开目录”的系统调用（例如 `os.startfile` 或等价实现），需与现有跨平台策略保持一致。
- 用户体验：减少在资源管理器中手动定位路径的步骤，降低误操作与查找成本。
