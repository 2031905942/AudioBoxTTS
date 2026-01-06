## SVN 忽略说明

本文件用于记录建议在 SVN 中忽略的本地/缓存文件，避免把个人环境差异与运行生成物提交到仓库。

### 必须忽略（本地生成/个人数据）

- `config/characters.json`
	- 本地角色列表覆盖文件：当用户在默认列表上进行新增/编辑/删除等写操作时自动生成
	- 每个人的内容不同，不应提交

### 应提交（默认数据）

- `config/characters.default.json`
	- 默认角色列表：仓库应保留一个“开箱即用”的默认角色
	- 新用户拉取后，在没有本地 `characters.json` 时会读取它

### 建议忽略（缓存/临时输出）

```
__pycache__/
*.pyc
*.pyo

temp_output/

checkpoints/
.venv/

.idea/
.vscode/
*.swp
*.swo
```

提示：SVN 的忽略规则需要通过 `svn:ignore` 属性或客户端（如 TortoiseSVN / SmartSVN）配置，本文件本身不会自动生效。
