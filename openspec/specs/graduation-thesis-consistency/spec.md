# Purpose
TBD

## Requirements

### Requirement: Terminology is consistent across all chapters
系统 MUST 确保论文中核心术语与命名在各章一致，包括系统名称、模块名称、数据/配置项称谓与流程步骤名称。

#### Scenario: Single term used everywhere
- **WHEN** 同一概念在多个章节出现（例如“角色配置”“推理服务”“音频后处理”）
- **THEN** 系统 MUST 使用一致的中文名/英文缩写（如有）并避免同义混用造成歧义

### Requirement: Section hierarchy and headings match the established outline
系统 MUST 保持 `Graduation Thesis/` 既定的章节编号与标题层级，不得无故变更标题层级或章节组织方式。

#### Scenario: Preserve header levels
- **WHEN** 章节骨架中已存在一级/二级标题
- **THEN** 系统 MUST 在相同标题层级下补全正文，并避免跳级（例如从 `#` 直接到 `###`）

### Requirement: Abstract and conclusion align with body content
系统 MUST 确保摘要对正文内容有覆盖，且“不足与优化方向”中的结论/展望与正文中描述的问题与实现相互呼应。

#### Scenario: Cross-chapter coherence
- **WHEN** 摘要与最后一章完成
- **THEN** 系统 MUST 检查摘要中的关键点均能在正文对应章节找到展开说明，且最后一章提出的不足能在实现章节中定位到原因来源
