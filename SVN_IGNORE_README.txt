# SVN 忽略文件说明

本文档说明了在 SVN 提交时应该忽略的文件和目录。

## 必须忽略的目录/文件

### 1. Python 缓存
```
__pycache__/
*.pyc
*.pyo
```

### 2. 临时输出
```
temp_output/
test_outputs/
```

### 3. 用户本地数据（重要！）
```
config/characters.json    # 用户创建的角色数据（每个人独立）
```

### 4. 大文件目录（建议忽略，通过其他方式分发）
```
checkpoints/              # IndexTTS2 模型文件 (~5GB)
Python3/Lib/site-packages/ # Python 依赖包 (~3GB)
```

### 5. IDE 配置
```
.idea/
.vscode/
*.swp
*.swo
```

## SVN 忽略配置方法

### 方法一：全局忽略（推荐）
编辑 SVN 全局配置文件：
- Windows: `%APPDATA%\Subversion\config`
- Linux/Mac: `~/.subversion/config`

在 `[miscellany]` 部分添加：
```ini
global-ignores = __pycache__ *.pyc *.pyo temp_output .idea .vscode
```

### 方法二：目录级忽略
在特定目录上右键 → TortoiseSVN → Properties → New → svn:ignore

### 方法三：使用 SmartSVN
Project → Ignore Patterns

## 关于大文件的处理建议

1. **checkpoints/ (~5GB)**
   - 建议：不纳入 SVN，由用户自行下载
   - 替代方案：放到公司内网共享盘，新用户复制

2. **Python3/Lib/site-packages/ (~3GB)**
   - 建议：不纳入 SVN，由用户运行 install_indextts_deps.bat 安装
   - 替代方案：打包成 zip 放到共享盘

3. **config/characters.json**
   - **必须忽略**：每个用户的角色是独立的，不应共享
