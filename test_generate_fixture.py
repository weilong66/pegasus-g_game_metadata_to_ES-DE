# -*- coding: utf-8 -*-
"""
测试脚本：生成一个模拟 Pegasus-G 源目录结构的测试夹具，
用于测试 pegasus-g_gamelist_conversion_gui.py 的完整处理流程。

生成的结构：
来源目录(sourcr_dir)
├─ game_单文件/             (单文件 bin，自动生成 media)
│  ├─ metadata.pegasus.txt
│  ├─ 单文件测试.bin
│  └─ media/单文件测试/{boxfront.jpg,logo.jpg,video.mp4}
├─ game_单文件压缩包/       (单文件 zip，含 media)
│  ├─ metadata.pegasus.txt
│  ├─ 单文件压缩包测试.zip
│  └─ media/单文件压缩包测试/{boxfront.jpg,logo.jpg,video.mp4}
├─ game_多文件/             (一个 game 块下多个 files，显式 assets.*)
│  ├─ metadata.pegasus.txt
│  ├─ 多文件测试1.zip / 多文件测试2.zip / 多文件测试3.zip
│  └─ media/多文件测试/{boxFront.png,logo.png,video.mp4}
├─ game_单文件无媒体/       (单文件 7z，无 media)
│  ├─ metadata.pegasus.txt
│  └─ 单文件无媒体测试.7z
└─ sega_saturn/             (文件在数字子文件夹下，显式 assets.*)
   ├─ metadata.pegasus.txt
   ├─ 009/{Lunar 2 Eternal Blue (Japan).m3u, (DISC 1).chd, (DISC 2).chd}
   └─ media/009/{boxFront.png,logo.png,video.mp4}

用法：
    python test_generate_fixture.py                       # 仅生成夹具
    python test_generate_fixture.py --run                 # 生成后运行转换流程
"""
import os
import sys
import argparse

# 让脚本能 import 同目录下的主脚本
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# Windows GBK 控制台无法打印 ✓ 等字符，强制使用 UTF-8 输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 试导入 PIL/Pillow，用于生成真实图片；失败则写入最小占位字节
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def make_image(path, width=64, height=64, color=None, fmt='PNG'):
    """生成一张纯色小图，返回真图片文件；无 PIL 时写入最小字节。"""
    color = color or (64 + (abs(hash(path)) % 190),
                      64 + (abs(hash(path + '1')) % 190),
                      64 + (abs(hash(path + '2')) % 190))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if HAS_PIL:
        img = Image.new('RGB', (width, height), color)
        if fmt.upper() == 'PNG':
            img.save(path, 'PNG')
        else:
            img.save(path, 'JPEG')
    else:
        # 最小占位内容（非真实图片，但能被 shutil 复制）
        with open(path, 'wb') as f:
            f.write(b'\xff\xd8\xff\xe0' + b'\x00' * 64)
    return path


def make_video(path, text=''):
    """模拟视频文件（仅占位，媒体处理会原样复制；截图需真实ffmpeg）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        # 写入一个最小可辨识的 ftyp 头 + 填充，便于媒体复制测试
        f.write(b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 128)
    return path


def write_metadata(path, games):
    """
    games: [{name, file(str)|files(list), sort-by, developer, media, description}, ...]
    生成 Pegasus-G metadata.pegasus.txt 格式
    - file: 单个值写 `file: xxx`(做为字符串给出)
    - files: 列表写 `files:` 头，随后每行缩进两个空格列出各值
    - media: {assets.box_front: 相对路径, ...} 各资产写一行 `key: value`
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = []
    for g in games:
        lines.append(f'game: {g["name"]}')

        if g.get('files'):
            lines.append('files:')
            for f in g['files']:
                lines.append(f'  {f}')
        elif g.get('file'):
            if isinstance(g['file'], list):
                lines.append('file:')
                for f in g['file']:
                    lines.append(f'  {f}')
            else:
                lines.append(f'file: {g["file"]}')

        for key in ('sort-by', 'developer'):
            if g.get(key):
                lines.append(f'{key}: {g[key]}')
        for amedia, apath in (g.get('media') or {}).items():
            lines.append(f'{amedia}: {apath}')
        if g.get('description'):
            lines.append(f'description: {g["description"]}')
        lines.append('')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# 测试文件夹定义：每个游戏单独一个文件夹，便于快速定位错误
FOLDERS = [
    {
        'folder': 'game_单文件',
        'games': [
            # 单文件游戏（直接为 bin，自动按文件名生成 media）
            {'name': '单文件测试', 'file': '单文件测试.gba',
             'developer': '单文件测试', 'description': '单文件游戏测试',
             'with_media': True},
        ],
    },
    {
        'folder': 'game_单文件压缩包',
        'games': [
            # 单文件压缩包游戏（zip，含 media）
            {'name': '单文件压缩包测试', 'file': '单文件压缩包测试.zip',
             'developer': '单文件压缩包测试', 'description': '单文件压缩包游戏测试',
             'with_media': True},
        ],
    },
    {
        'folder': 'game_多文件',
        'games': [
            # 多文件游戏（一个 game 块下多个 files，显式 assets.* 媒体路径）
            {'name': '多文件测试',
             'files': ['多文件测试1.gba', '多文件测试2.gba', '多文件测试3.gba'],
             'sort-by': '050', 'developer': '多文件测试',
             'media': {
                 'assets.box_front': 'media/多文件测试/boxFront.png',
                 'assets.logo': 'media/多文件测试/logo.png',
                 'assets.video': 'media/多文件测试/video.mp4',
             },
             'description': '多文件游戏测试\\n1、无描边+残影优化\\n2、配色优化……',
             'with_media': True},
        ],
    },
    {
        'folder': 'game_单文件无媒体',
        'games': [
            # 单文件压缩包游戏（7z，无 media）
            {'name': '单文件无媒体测试', 'file': '单文件无媒体测试.gba',
             'developer': '单文件无媒体测试', 'description': '单文件压缩包游戏测试',
             'with_media': False},
        ],
    },
    {
        'folder': 'game_多文件放同一子文件夹',
        'games': [
            # 文件存放在数字子文件夹(009/)下，显式 assets.* 媒体路径
            {'name': 'game多文件',
             'files': ['gameRom/文件夹+多文件测试1.chd',
                       'gameRom/文件夹+多文件测试2.chd',
                       'gameRom/文件夹+多文件测试3.chd'],
             'media': {
                 'assets.box_front': 'media/文件夹+多文件测试/boxFront.png',
                 'assets.logo': 'media/文件夹+多文件测试/logo.png',
                 'assets.video': 'media/文件夹+多文件测试/video.mp4',
             },
             'description': '文件夹+多文件游戏测试',
             'with_media': True},
        ],
    },
]


def generate_fixture(source_dir):
    os.makedirs(source_dir, exist_ok=True)

    for folder_def in FOLDERS:
        folder = os.path.join(source_dir, folder_def['folder'])
        all_games = []

        for game in folder_def['games']:
            all_games.append(game)

            # 收集游戏文件 (file 或 files)，统一为列表；可含子文件夹路径
            files = game.get('file') or game.get('files') or []
            if isinstance(files, str):
                files = [files]
            for f in files:
                # 放在本游戏文件夹内，与 metadata 同级 —— 主脚本会排除 metadata 处理它
                make_video(os.path.join(folder, f), text=f)

            # media 文件：优先使用显式 media 映射，否则按文件名生成默认资源
            media = game.get('media')
            if media:
                for relpath in media.values():
                    p = os.path.join(folder, relpath.replace('/', os.sep))
                    if os.path.splitext(relpath)[1].lower() in ('.mp4', '.mkv', '.avi'):
                        make_video(p)
                    else:
                        make_image(p, fmt='PNG' if relpath.endswith('.png') else 'JPEG')
            elif game.get('with_media'):
                for f in files:
                    stem = os.path.splitext(os.path.basename(f))[0]
                    media_sub = os.path.join(folder, 'media', stem)
                    make_image(os.path.join(media_sub, 'boxfront.jpg'), fmt='JPEG')
                    make_image(os.path.join(media_sub, 'logo.jpg'), fmt='JPEG')
                    make_video(os.path.join(media_sub, 'video.mp4'))

        # 统一写入本文件夹的 metadata
        write_metadata(os.path.join(folder, 'metadata.pegasus.txt'), all_games)
        print(f"  ✓ 生成: {folder_def['folder']}/  (共 {len(all_games)} 个游戏条目)")

    return source_dir


def run_conversion(source_dir, output_dir):
    # 主脚本文件名含连字符，不能直接 import，用文件路径加载模块
    import importlib.machinery
    import importlib.util

    main_script = os.path.join(SCRIPT_DIR, 'pegasus-g_gamelist_conversion_gui.py')
    loader = importlib.machinery.SourceFileLoader('pegasus_gui', main_script)
    spec = importlib.util.spec_from_loader('pegasus_gui', loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    run_integrated_process = mod.run_integrated_process

    config = {
        'source_dir': source_dir,
        'rom_dir': '',            # 留空 → 默认使用源目录
        'output_dir': output_dir,
        'do_roms': True,
        'do_media': True,
        'do_gamelist': True,
        'add_prefix': True,
        'force_overwrite': True,
        'copy_archives_directly': False,
        'do_screenshots': False,  # 占位视频无真实ffmpeg帧，关闭截图避免失败噪音
        'smart_screenshot': True,
        'no_subfolder': False,
        'recursive': True,
        'ffmpeg_path': 'ffmpeg',
        'screenshot_value': '1',
        'screenshot_unit': '秒',
        'max_delay_sec': '15',
        'solid_threshold': '0.8',
    }
    print(f"\n开始运行转换…")
    print(f"  源目录 : {source_dir}")
    print(f"  输出目录: {output_dir}\n")
    run_integrated_process(config, log_func=print)
    return output_dir


def main():
    parser = argparse.ArgumentParser(description='生成天马G转换测试夹具')
    parser.add_argument('--source', default=None,
                        help='夹具源目录(默认: ./test_source)')
    parser.add_argument('--output', default=None,
                        help='输出目录(默认: ./test_output)')
    parser.add_argument('--run', action='store_true',
                        help='生成后直接运行转换流程')
    args = parser.parse_args()

    base = SCRIPT_DIR
    source_dir = args.source or os.path.join(base, 'test_source')
    output_dir = args.output or os.path.join(base, 'test_output')

    print("=" * 60)
    print("生成测试夹具")
    print("=" * 60)
    generate_fixture(source_dir)

    print("\n夹具生成完成！目录结构:")
    for root, dirs, files in os.walk(source_dir):
        level = root.replace(source_dir, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}{os.path.basename(root)}/")
        for f in files:
            print(f"{indent}  {f}")

    if args.run:
        run_conversion(source_dir, output_dir)
        print(f"\n转换完成，输出目录: {output_dir}")

    print("\n完成。")


if __name__ == '__main__':
    main()