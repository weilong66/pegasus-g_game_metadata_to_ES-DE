# 天马G游戏列表转换工具集

本工具集包含四个 Python GUI 脚本，用于将 Pegasus-G (天马G) 整合包中的ROM资源及相关元数据转换为 ES-DE 可用的格式，以便为 [RomM](https://docs.romm.app/latest/getting-started/metadata-providers/#es-de-gamelistxml) 提供游戏元数据。

---

## 脚本选择建议

| 场景 | 推荐脚本 | 说明 |
|------|----------|------|
| **一键完整处理** | 脚本 4（整合处理器） | 自动串联所有步骤，保证路径一致性 |
| **单独处理ROM** | 脚本 2 | 仅处理ROM压缩包解压/复制 |
| **单独生成列表** | 脚本 1 | 仅从 metadata 生成 gamelist.xml |
| **单独修正路径** | 脚本 3 | 已有 gamelist.xml 需要修正路径时使用 |

> **推荐优先使用脚本 4**，它采用 "Correct by Construction" 架构，从根源上保证路径一致性，无需事后修正。

---

## 文件列表

| 文件名 | 说明 |
| ------ | ---- |
| [4.integrated_processor.py](#脚本-4整合处理器推荐) | **整合处理器（推荐）** - 一键完成所有步骤 |
| [1.pegasus_gamelist_gui.py](#脚本-1pegasus-metadata-转换器) | Pegasus Metadata 转换器主脚本 |
| [2.batch_roms_file_processor.py](#脚本-2roms批量文件处理器) | 批量文件处理器主脚本 |
| [3.update_gamelist_paths.py](#脚本-3gamelistxml-路径更新器) | gamelist.xml 路径更新器主脚本 |
| `integrated_processor_config.json` | 脚本4的配置文件 |
| `pegasus_gamelist_config.json` | 脚本1的配置文件 |
| `batch_processor_config.json` | 脚本2的配置文件 |
| `update_paths_config.json` | 脚本3的配置文件 |

---

## 脚本 4：整合处理器（推荐）

(`4.integrated_processor.py`) 将脚本 1-3 的功能整合为一个完整的工作流，采用 **Correct by Construction**（正确构建）架构，从根源上保证 `gamelist.xml` 中的路径与实际文件完全一致。

### 核心原理

```
传统方式（易出错）：
  ROM处理 → 生成gamelist.xml → 事后修正路径 ← 可能失败

Correct by Construction（本脚本）：
  步骤1: ROM处理 → 记录 {原始名: 实际输出名} 映射
  步骤2: 生成gamelist.xml → 使用映射直接写入正确路径 ← 天生正确
  步骤3-5: 媒体处理 / 截图 / 路径验证
```

### 处理流程

1. **步骤1：处理ROM文件** - 解压/复制ROM，建立文件名映射表
2. **步骤2：生成 gamelist.xml** - 使用映射表直接写入正确的文件路径
3. **步骤3：处理媒体文件** - covers/marquees/videos 分类整理
4. **步骤4：提取视频截图**（可选）
5. **步骤5：验证路径有效性** - 检查所有路径是否存在

### 功能

- **一键完整处理**：配置好源目录后，自动完成所有步骤
- **路径一致性保证**：ROM处理后记录实际输出名，生成 gamelist.xml 时直接使用正确路径
- **智能默认值**：
  - ROM目录留空 → 自动使用源目录
  - 输出目录留空 → 自动生成到源目录下的 `output` 文件夹
- **排除 metadata.pegasus.txt**：处理ROM时自动跳过元数据文件
- **拼音前缀**：自动为游戏名称添加拼音首字母前缀
- **媒体分类**：covers/marquees/videos 自动分类
- **GUI 界面**：可视化操作，支持配置保存/加载

### 依赖

- Python 3.8+
- `pypinyin`（可选，用于拼音前缀功能）
- `Pillow`（可选，用于图片格式转换）
- `rarfile`（可选，用于解压 `.rar` 格式）
- `py7zr`（可选，用于解压 `.7z` 格式）
- `ffmpeg`（可选，用于视频截图）

```bash
pip install pypinyin Pillow rarfile py7zr
```

### 使用

```bash
python 4.integrated_processor.py
```

### 操作步骤

1. 选择**源目录**（包含 `metadata.pegasus.txt` 和ROM文件的目录）
2. 选择**ROM目录**（可留空，默认使用源目录）
3. 选择**输出目录**（可留空，默认使用源目录下的 `output` 文件夹）
4. 根据需要勾选处理选项
5. 点击 **开始处理**

### 输出目录结构

```
output/
├── 原文件夹名称/
│   ├── gamelist.xml          # 游戏列表（路径已正确匹配）
│   ├── 游戏文件.smd          # 解压/复制后的ROM
│   ├── 游戏文件夹/           # 多文件ROM解压目录
│   └── assets/
│       ├── covers/           # 封面图
│       ├── marquees/         # 横幅图
│       ├── videos/           # 视频
│       └── screenshots/      # 截图（可选）
```

### 配置文件

GUI 设置可以保存到 `integrated_processor_config.json`，下次启动自动加载。

---

## 脚本 1：Pegasus Metadata 转换器

(`1.pegasus_gamelist_gui.py`) 将 Pegasus-G 整合包里的 `metadata.pegasus.txt` 和相应多媒体文件（封面、截图、视频等）批量转换为 ES-DE 可用的 `gamelist.xml` 格式。

### 功能

- **解析 metadata.pegasus.txt** 并生成标准 `gamelist.xml`
- **多文件支持**：一个游戏对应多个文件时，自动生成多个 `<game>` 标签
- **媒体分类**：将 covers、marquees、videos 整理到 `assets/` 子目录
- **视频截图**：从游戏视频中截取帧作为截图（需 ffmpeg）
- **拼音前缀**：自动为游戏名称添加拼音首字母前缀（如 `H-黄金太阳`）
- **可选子文件夹**：可选择在目标目录下创建原文件夹，或直接将文件放入目标目录
- **GUI 界面**：可视化操作，支持配置保存/加载

### 依赖

- Python 3.8+
- `pypinyin`（可选，用于拼音前缀功能）
- `Pillow`（可选，用于图片格式转换）
- `ffmpeg`（可选，用于视频截图）

```bash
pip install pypinyin Pillow
```

### 使用

```bash
python 1.pegasus_gamelist_gui.py
```

### 操作步骤

1. 选择**源目录**（包含 `metadata.pegasus.txt` 的文件夹，支持递归搜索）
2. 选择**输出目录**（留空则默认使用脚本目录下的 `output` 文件夹）
3. 根据需要勾选选项：
   - **在目标目录下创建原文件夹**：勾选时在目标目录下创建与原文件夹同名的子文件夹，并将生成文件放其中；取消勾选则直接将生成文件放入目标目录。
   - **只生成gamelist列表文件**：仅生成 `gamelist.xml`，不处理媒体文件，以便快速测试。
4. 点击 **开始处理**

> 注意：FFmpeg 路径需要选择 `ffmpeg.exe` 文件所在位置，如果已将 ffmpeg 配置到 `Path` 环境变量，可留空或输入 `ffmpeg`。

### metadata.pegasus.txt 格式示例

```
game: 游戏名称
file: 游戏文件.zip
sort-by: 001
assets.box_front: media/游戏名/boxfront.png
assets.logo: media/游戏名/logo.png
assets.video: media/游戏名/video.mp4
description: 游戏描述文本

game: 多文件游戏
files:
  版本A.zip
  版本B.zip
sort-by: 079
assets.box_front: media/游戏名/boxfront.png
description: 游戏描述文本
```

### 输出目录结构

**勾选"创建原文件夹"时：**

```
output/
├── 原文件夹名称/
│   ├── gamelist.xml
│   └── assets/
│       ├── covers/         # 封面图
│       ├── marquees/       # 横幅图
│       ├── videos/         # 视频
│       └── screenshots/    # 截图
```

**未勾选"创建原文件夹"时：**

```
output/
├── gamelist.xml
├── assets/
│   ├── covers/
│   ├── marquees/
│   ├── videos/
│   └── screenshots/
```

### 配置文件

GUI 设置可以手动保存到 `pegasus_gamelist_config.json`。

---

## 脚本 2：Roms批量文件处理器

(`2.batch_roms_file_processor.py`) 用于批量处理指定目录下的Roms压缩文件，支持压缩包自动解压、重命名，然后拷贝到目标文件夹中。

### 功能

- **压缩包解压**：支持 `.zip`、`.rar`、`.7z`、`.tar`、`.tar.gz`、`.tar.bz2`、`.tar.xz` 等格式
- **智能处理**：
  - 单文件压缩包：解压后重命名为压缩文件名，并移动到目标目录
  - 多文件压缩包：解压到以压缩文件名命名的子文件夹，并移动到目标目录
  - 非压缩文件：直接复制到目标目录
- **覆盖控制**：可选强制覆盖已存在的文件
- **GUI 界面**：可视化操作，支持配置保存/加载

### 依赖

- Python 3.8+
- `rarfile`（可选，用于解压 `.rar` 格式）
- `py7zr`（可选，用于解压 `.7z` 格式）

```bash
pip install rarfile py7zr
```

### 使用

```bash
python 2.batch_roms_file_processor.py
```

### 操作步骤

1. 选择**源目录**（仅处理该目录下的文件，不处理子文件夹）
2. 选择**目标目录**
3. 根据需要勾选处理选项：
   - **强制覆盖已存在的文件**：不勾选时跳过目标目录中已存在的同名文件
4. 点击 **开始处理**

### 配置文件

GUI 设置可以手动保存到 `batch_processor_config.json`。

---

## 脚本 3：gamelist.xml 路径更新器

(`3.update_gamelist_paths.py`) 根据实际解压/拷贝后的文件扩展名，更新 `gamelist.xml` 中的 `<path>` 元素。
> 天马G整合包中的ROM文件大多为压缩包，RomM 无法直接加载压缩包里的 ROM 文件，需解压后才能正常使用。但压缩包内的 ROM 文件名与元数据中的文件名往往不同，后缀也不统一（如元数据中记录的是 `.md`，实际解压出来的可能是 `.smd`）。本脚本通过扫描实际文件目录，自动将 `gamelist.xml` 中的路径更新为正确的扩展名。

### 功能

- **自动匹配**：扫描目标目录中的实际文件，按文件名基准名（stem）匹配并更新 `gamelist.xml` 中的路径
- **智能选择**：同一基准名有多个文件时（如同时存在 `.md` 和 `.smd`），优先选择非 `.md` 扩展名（特别是 `.smd`）
- **子文件夹支持**：当路径对应子文件夹时，自动更新为 `./文件夹名/` 格式
- **路径容错**：gamelist 路径支持手动输入目录（自动查找 `gamelist.xml`），输出路径支持目录（自动保存为 `gamelist.xml`）
- **GUI 界面**：可视化操作，支持配置保存/加载

### 依赖

- Python 3.8+

### 使用

```bash
python 3.update_gamelist_paths.py
```

### 操作步骤

1. 选择 **gamelist.xml** 文件（或手动输入包含 `gamelist.xml` 的目录）
2. 选择 **实际文件目录**（存放解压/拷贝后游戏文件的目录）
3. 选择 **输出设置**：
   - 勾选 **覆盖原 gamelist.xml**：直接覆盖原文件
   - 取消勾选：另存为新文件（支持手动输入目录，将自动保存为 `gamelist.xml`）
4. 点击 **开始更新**

### 匹配逻辑说明

| 场景 | 处理方式 |
|------|----------|
| 单文件匹配 | 直接使用该文件名更新路径 |
| 多文件匹配（如 `.md` + `.smd`） | 优先选择非 `.md` 扩展名，特别是 `.smd` |
| 子文件夹匹配 | 更新为 `./文件夹名/` 格式 |
| 未找到匹配 | 保持原路径不变，日志中提示 |

### 配置文件

GUI 设置可以手动保存到 `update_paths_config.json`。
