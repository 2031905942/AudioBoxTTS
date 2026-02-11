## ADDED Requirements

### Requirement: “同步声音库”按钮提供操作说明 tips
系统 MUST 在“项目 -> 声音库”面板的“同步声音库”按钮上提供可见的 tips，用于在点击前解释该操作将对 Unity 声音库目录产生的影响。

tips 文案 MUST 明确包含以下信息（可用多行/列表表达）：
- 该操作会对比 Wwise 工程 `GeneratedSoundBanks` 与 Unity 工程声音库目录。
- 该操作会复制新增文件、同步（覆盖）内容不同的已存在文件、删除 Unity 目录中多余文件，并清理空目录。
- 该操作同步文件产物，不负责在 Wwise 中生成 SoundBank（避免用户误解）。

#### Scenario: 悬停时展示同步行为说明
- **WHEN** 用户将鼠标悬停在“同步声音库”按钮上
- **THEN** 系统展示 tips，且 tips 清晰说明“对比源/目标目录 + 复制新增 + 覆盖更新 + 删除多余 + 清理空目录”，并包含“不会生成 SoundBank，仅同步产物”的提示

### Requirement: tips 说明同步范围的关键细节
系统 MUST 在 tips 中说明同步范围的关键细节，以便用户预判可能的变更内容。

tips MUST 至少覆盖：
- 主要文件类型：`.bnk`、`.wem`，以及相关元数据 `json/xml`（例如 `SoundbanksInfo`、`PlatformInfo`、`PluginInfo`）。
- Wwise 版本差异：当 Wwise 版本为 2022+ 时可能包含 `Media/`（streamed media）目录下的 `.wem`。
- 语言范围：当用户在“语言列表”勾选语言时，同步范围 MUST 包含对应语言子目录（以及 Wwise 2022+ 时的 `Media/<language>`）。
- 外部源：若存在外部源产物（例如 `.wwopus`），tips MUST 说明其也可能在同步范围内。

#### Scenario: tips 覆盖语言与 Wwise 版本差异说明
- **WHEN** 用户查看“同步声音库”按钮的 tips
- **THEN** tips 同时说明语言勾选会改变同步范围，并提示 Wwise 2022+ 可能额外同步 `Media/` 目录内容
