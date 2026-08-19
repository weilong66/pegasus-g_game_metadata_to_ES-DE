# 天马G游戏列表转换工具集

本工具集包含两个 Python GUI 脚本，用于将 Pegasus-G (天马G) 整合包中的ROM资源及相关元数据转换为 ES-DE 可用的格式，以便为 [RomM](https://docs.romm.app/latest/getting-started/metadata-providers/#es-de-gamelistxml) 提供游戏元数据。

---

## 脚本 1：Pegasus Metadata 转换器 (`1.pegasus_gamelist_gui.py`)

将 Pegasus-G 整合包里的 `metadata.pegasus.txt` 和相应多媒体文件（封面、截图、视频等）批量转换为 ES-DE 可用的 `gamelist.xml` 格式。

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

## 脚本 2：Roms批量文件处理器 (`2.batch_roms_file_processor.py`)

用于批量处理指定目录下的Roms压缩文件，支持压缩包自动解压、重命名，然后拷贝到目标文件夹中。

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

## 文件列表

| 文件名 | 说明 |
|--------|------|
| `1.pegasus_gamelist_gui.py` | Pegasus Metadata 转换器主脚本 |
| `2.batch_roms_file_processor.py` | 批量文件处理器主脚本 |
| `pegasus_gamelist_config.json` | 脚本1的配置文件 |
| `batch_processor_config.json` | 脚本2的配置文件 |
