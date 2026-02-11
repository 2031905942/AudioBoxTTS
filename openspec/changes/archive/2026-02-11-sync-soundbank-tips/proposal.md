## Why

“同步声音库”按钮会对 Unity 工程声音库目录执行文件级同步（新增/覆盖/删除），但当前 UI 缺少明确说明。用户在点击前无法判断会影响哪些目录与文件类型，容易产生误操作（例如不期望的覆盖或删除），也不利于同步后对提交内容进行关注与核对。

## What Changes

- 为“同步声音库”按钮增加悬停 tips（tooltip/提示文案），在点击前明确说明该操作的实际影响与同步范围。
- 同步完成后输出“本次同步的具体变更明细”，让用户一目了然看到新增/更新/删除了哪些文件。
- tips 中列出同步的核心行为：对比 Wwise 工程 `GeneratedSoundBanks` 与 Unity 工程声音库目录，复制新增文件、同步（覆盖）已存在但内容不同的文件、删除 Unity 目录中多余文件，并清理空目录。
- tips 中说明会涉及的主要文件/目录形态：`.bnk` / `.wem`、`SoundbanksInfo` / `PlatformInfo` / `PluginInfo` 的 `json/xml` 元数据、Wwise 2022+ 的 `Media/`（streamed media）目录、以及 `ExternalSource` 下的 `.wwopus`。
- tips 中说明“语言列表”勾选会影响同步范围（勾选语言会纳入对应语言子目录及 `Media/<language>`）。
- 不改变现有同步算法与文件操作逻辑，仅增加用户可见说明。

## Capabilities

### New Capabilities
- `soundbank-sync-tips`: 在项目界面为“同步声音库”提供可读的 tips，解释该按钮会对哪些目录/文件执行怎样的同步动作，并提示语言勾选对范围的影响。
- `soundbank-sync-change-report`: 同步完成后展示本次同步的变更明细（新增/更新/删除的文件列表），方便用户快速核对。

### Modified Capabilities
- （无）

## Impact

- UI：`Source/UI/Interface/ProjectInterface/soundbank_sub_window.py` 为按钮增加 tips 文案展示。
- 文案：新增/调整中文提示文本（后续如需多语言可再扩展）。
- 用户工作流：降低误操作风险，提高同步后对变更内容的可预期性。
