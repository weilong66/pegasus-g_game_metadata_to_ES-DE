# Pegasus Metadata 转换器

将 Pegasus-G (天马G)整合包里的 `metadata.pegasus.txt` 和相应多媒体文件（封面、截图、视频等）批量转换为 ES-DE 可用的 `gamelist.xml` 格式，以便为[RomM](https://docs.romm.app/latest/getting-started/metadata-providers/#es-de-gamelistxml) 提供游戏元数据。

## 功能

- **解析 metadata.pegasus.txt** 并生成标准 `gamelist.xml`
- **多文件支持**：一个游戏对应多个文件时，自动生成多个 `<game>` 标签
- **媒体分类**：将 covers、marquees、videos 整理到 `assets/` 子目录
- **视频截图**：从游戏视频中截取帧作为截图（需 ffmpeg）
- **拼音前缀**：自动为游戏名称添加拼音首字母前缀（如 `H-黄金太阳`）
- **GUI 界面**：可视化操作，支持配置保存/加载

## 依赖

- Python 3.8+
- `pypinyin`（可选，用于拼音前缀功能）
- `ffmpeg`（可选，用于视频截图）

```bash
pip install pypinyin
```

## 使用

```bash
python pegasus_gamelist_gui.py
```

### 操作步骤

1. 选择**源目录**（包含 `metadata.pegasus.txt` 的文件夹，支持递归搜索）
2. 选择**输出目录**（留空则使用脚本目录下的 `output` 文件夹）
3. 勾选所需处理选项，点击 **开始处理**

    - 其中FFmpeg路径需要选择`ffmpeg.exe`文件所在目录，如果已经将ffmpeg配置到了`Path`环境变量，也可以留空或输入`ffmpeg`。

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

```
output/
├── 游戏A/
│   ├── gamelist.xml
│   └── assets/
│       ├── covers/         # 封面图
│       ├── marquees/       # 横幅图
│       ├── videos/         # 视频
│       └── screenshots/    # 截图
└── 游戏B/
    └── ...
```

## 配置文件

GUI 设置会自动保存到 `pegasus_gamelist_config.json`。