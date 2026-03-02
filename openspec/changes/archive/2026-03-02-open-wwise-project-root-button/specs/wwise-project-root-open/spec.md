## ADDED Requirements

### Requirement: 已选择 Wwise 工程文件时提供“打开Wwise工程根目录”入口
系统 MUST 在“项目”页的 Wwise 工程配置区域中，在“选择Wwise工程文件”按钮右侧提供“打开Wwise工程根目录”按钮，用于快速访问当前 `.wproj` 所在目录。

#### Scenario: 选择工程文件后展示可用入口
- **WHEN** 用户已通过“选择Wwise工程文件”成功选择一个 `.wproj` 文件
- **THEN** 系统展示“打开Wwise工程根目录”按钮并允许点击

#### Scenario: 未选择工程文件时入口不可用
- **WHEN** 当前未配置有效 `.wproj` 路径
- **THEN** “打开Wwise工程根目录”按钮 MUST 处于不可用状态（或不展示）且不会触发打开目录操作

### Requirement: 点击按钮在文件资源管理器中打开工程根目录
系统 MUST 在用户点击“打开Wwise工程根目录”后，打开所选 `.wproj` 文件所在目录；当目录无效时 MUST 给出明确错误提示并保持应用稳定。

#### Scenario: 正常打开工程目录
- **WHEN** 用户点击“打开Wwise工程根目录”，且 `.wproj` 所在目录存在且可访问
- **THEN** 系统在文件资源管理器中打开该目录

#### Scenario: 目录失效时提示错误
- **WHEN** 用户点击“打开Wwise工程根目录”，但 `.wproj` 所在目录不存在或无法访问
- **THEN** 系统提示目录不可用/无法打开，且应用不崩溃
