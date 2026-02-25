## ADDED Requirements

### Requirement: Thesis chapters are fully authored in Markdown
系统 MUST 在 `Graduation Thesis/` 目录下输出并维护一组 Markdown 论文正文文件，并遵循该目录中既定章节文件名与标题结构。

#### Scenario: Fill existing chapter skeletons
- **WHEN** `Graduation Thesis/` 目录内存在章节骨架文件（例如 `0.摘要.md` 至 `6.不足与优化方向.md`）
- **THEN** 系统 MUST 在不更改既有章节文件路径的前提下补全每个文件的正文内容

### Requirement: Content remains consistent with repository implementation
论文对系统架构、模块划分、数据与配置的描述 MUST 与仓库中可观察到的实现保持一致；若存在不确定细节，文本 MUST 采用范围化表述并避免给出不可证实的结论。

#### Scenario: Architecture references existing modules
- **WHEN** 论文描述系统模块与目录结构
- **THEN** 文本 MUST 以仓库中存在的目录/文件（如 `Source/`、`server/`、`config/`、`checkpoints/` 等）为依据组织叙述，且不引入不存在的模块名

### Requirement: Writing uses original wording while referencing attachments
论文在可引用附件要点的前提下 MUST 使用原创表述完成正文，并避免对附件内容的逐句复刻。

#### Scenario: Use attachments as factual basis only
- **WHEN** 论文需要说明研究背景、技术原理或开题范围
- **THEN** 文本 MUST 仅抽取附件中的事实与要点并以新的组织结构与措辞表达

### Requirement: No additional front-matter fields are introduced
本次输出的论文正文 MUST 不包含学校/作者/导师等封面字段页面，仅包含章节内容。

#### Scenario: Skip cover metadata
- **WHEN** 生成摘要与正文
- **THEN** 文本 MUST 不增加“封面信息/致谢/声明”等非既定章节内容
