# 天马G游戏列表转换工具集

本 Python GUI 脚本用于将 Pegasus-G (天马G) 整合包中的ROM资源及相关元数据转换为 [RomM](https://docs.romm.app/latest/getting-started/metadata-providers/#es-de-gamelistxml) 可用的 ES-DE 格式的元数据。

> 脚本完全使用 AI 编写，只保证能用，不保证质量。

---

## 脚本列表

| 文件 | 说明 |
|------|------|
| [pegasus-g_gamelist_processor_gui.py](#主脚本pegasus-g_gamelist_processor_guipy) | 转换主处理脚本（一体化GUI） |
| [smart_screenshot.py](#智能截图模块smart_screenshotpy) | 智能截图模块（检测纯色帧自动延后） |

---

## 主脚本：pegasus-g_gamelist_processor_gui.py

采用 **Correct by Construction**（正确构建）架构，从根源上保证 `gamelist.xml` 中的路径与实际文件完全一致。

### 处理流程

1. **步骤1：处理ROM文件** - 解压/复制ROM，建立文件名映射表。
2. **步骤2：生成 gamelist.xml** - 使用映射表直接写入正确的文件路径。（主要是写入正确的ROM文件后缀名）
3. **步骤3：处理媒体文件** - covers/marquees/videos 分类整理
4. **步骤4：提取视频截图**（可选）
5. **步骤5：验证路径有效性** - 检查所有路径是否存在

### 功能特性

- **一键完整处理**：配置好源目录后，自动完成所有步骤
- **单独处理**：步骤1-4可以单独执行。
  - 注意：如果未执行步骤1处理ROM文件，当单独执行步骤2生成gamelist.xml文件时，会使用输出目录下的文件建立文件名映射表；如果输出目录也没有ROM文件，则会直接使用原始文件名称+后缀。

- **路径一致性保证**：ROM处理后记录实际输出名，生成 gamelist.xml 时直接使用正确路径
- **智能默认值**：
  - ROM目录留空 → 自动使用源目录
  - 输出目录留空 → 自动生成到源目录下的 `output` 文件夹
- **排除 metadata.pegasus.txt**：处理并复制ROM文件时自动跳过元数据文件
- **拼音前缀**：自动为游戏名称添加拼音首字母前缀，以便可以正常按字母分组
- **媒体分类**：covers/marquees/videos 自动分类
- **智能截图**：从视频文件中截图作为游戏截图放入screenshots文件夹中，截图时支持智能检测黑屏/白屏/绿屏等纯色帧，自动延后截取正常画面
- **配置保存/加载**：GUI 设置可保存到配置文件 `pegasus_conversion_gui_config.json` 中。
- **日志导出**：支持导出日志

### GUI 选项说明

#### 目录设置

| 选项 | 说明 |
|------|------|
| 源目录 | 包含 `metadata.pegasus.txt` 和ROM文件的目录 |
| 递归搜索子目录 | 在源目录下递归查找 `metadata.pegasus.txt`，以便能够批量处理多个游戏平台的ROM文件。 |
| ROM目录 | 用于单独设置存放ROM压缩包/文件的目录（留空使用源目录） |
| 输出目录 | 处理结果输出位置（留空输出到源目录/output） |
| 直接输出到目标目录 | 勾选后不创建与源目录同名的子文件夹，而是直接输出到“输出目录”下。 |

#### 处理选项

| 选项 | 说明 |
|------|------|
| 处理ROM文件 | 解压/复制ROM文件，建立文件名映射 |
| 处理媒体文件 | 分类处理 covers/marquees/videos |
| 生成 gamelist.xml | 勾选时才生成该文件 |
| └ 为游戏名称添加拼音首字母前缀 | 依赖上方选项，为游戏名添加拼音前缀 |
| 强制覆盖已存在的文件 | 覆盖模式开关，未勾选时所有重名文件直接跳过 |
| 直接复制压缩文件 | 不解压，保留原始压缩包格式 |
| 从视频中提取截图 | 开启通过游戏视频提取游戏截图功能 |
| └ 截图时间点 | 设置提取第几秒/帧的画面（一般建议2-6秒之间） |
| └ 智能截图 | 检测画面为纯色时自动延后，直到画面正常时再截图，避免截图到黑屏、白屏等无意义画面。 |
| └ 最大延后 | 智能截图最大等待时间 |

### 依赖

- Python 3.8+
- `Pillow`（**必装**，用于图片格式转换、智能截图）
- `pypinyin`（建议安装，用于拼音前缀功能）
- `rarfile`（可选，用于解压 `.rar` 格式）
- `py7zr`（可选，用于解压 `.7z` 格式）
- `ffmpeg`（可选，用于视频截图）

```bash
#最小安装
pip install pypinyin Pillow
#全部安装
pip install pypinyin Pillow rarfile py7zr
```

### 使用

```bash
python pegasus-g_gamelist_processor_gui.py
```

### 输出目录结构

**不勾选"直接输出到目标目录"时：**

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

**勾选"直接输出到目标目录"时：**

```
output/
├── gamelist.xml
├── 游戏文件.smd
├── 游戏文件夹/
└── assets/
    ├── covers/
    ├── marquees/
    ├── videos/
    └── screenshots/
```

### 配置文件

GUI 设置可以保存到 `pegasus_gamelist_processor_config.json`，下次启动自动加载。

---

## 智能截图模块：smart_screenshot.py

提供纯色帧检测和智能延后截图功能。

### 核心功能

- **纯色帧检测**：识别黑屏、白屏、绿屏等画面（阈值80%）
- **自动延后**：检测到纯色帧时自动延后1秒重试
- **最大延后限制**：默认30秒，可配置
- **回退机制**：达到最大延后时间后使用最后一帧

### 检测算法

```python
# 像素量化（将颜色归到最近的10级色阶）
rounded = (r // 10 * 10, g // 10 * 10, b // 10 * 10)

# 统计颜色分布，找占比最高的颜色
max_ratio = max_count / total_pixels

# 判断是否为纯色帧
if max_ratio >= 0.8:  # 80%阈值
    # 识别颜色类型并延后
```

---

## metadata.pegasus.txt 格式示例

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
