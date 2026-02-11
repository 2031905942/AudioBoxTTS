## 1. 定位与实现 tips

- [x] 1.1 在 `Source/UI/Interface/ProjectInterface/soundbank_sub_window.py` 定位“同步声音库”按钮初始化位置并为其添加 tooltip/tips（使用 `setToolTip`）
- [x] 1.2 编写并接入 tips 文案，覆盖 specs 中要求的关键点：对比目录、复制新增、覆盖更新、删除多余、清理空目录、且明确“不生成 SoundBank，仅同步产物”
- [x] 1.3 在 tips 文案中补充同步范围细节说明：`.bnk/.wem`、`SoundbanksInfo/PlatformInfo/PluginInfo` 的 `json/xml`、Wwise 2022+ `Media/`、语言勾选影响、以及 `.wwopus` 外部源

## 2. 校验与回归

- [x] 2.1 启动应用并进入“项目 -> 声音库”，验证悬停“同步声音库”按钮会展示多行 tips，且内容可读（不过长/不被截断到不可理解）
- [x] 2.2 快速回归：点击“同步声音库”后功能行为与结果不变（仅 UI 说明变化），并确认“清理打包声音库目录”等其他按钮不受影响

## 3. 同步变更明细输出

- [x] 3.1 在 `SoundbankUtility.sync_soundbank_job` 生成“新增/更新/删除”三类文件列表，并在同步完成后输出到结果内容中（必要时做列表截断）
- [x] 3.2 在 `SoundBankJob.job_finish` 对“同步声音库完成”结果弹出可复制的详细报告窗口，同时 InfoBar 只展示一行摘要
- [x] 3.3 手工验证：执行一次“同步声音库”，确认会展示变更明细窗口，且新增/更新/删除分类正确、可读且可复制
