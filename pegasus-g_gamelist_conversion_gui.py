import os
import sys
import json
import uuid
import time
import shutil
import tempfile
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'pegasus_conversion_gui_config.json')

try:
    from pypinyin import pinyin, Style
    HAS_PINYIN = True
except ImportError:
    HAS_PINYIN = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from smart_screenshot import extract_video_frame_with_fallback, is_solid_color_frame, HAS_PIL as SS_HAS_PIL
    HAS_SMART_SCREENSHOT = True
except ImportError:
    HAS_SMART_SCREENSHOT = False

try:
    import zipfile
    HAS_ZIP = True
except ImportError:
    HAS_ZIP = False

try:
    import rarfile
    HAS_RAR = True
except ImportError:
    HAS_RAR = False

try:
    import py7zr
    HAS_7Z = True
except ImportError:
    HAS_7Z = False


ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z', '.tar', '.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2'}
WRAPPING_SYMBOLS = set('《》（）【】「」『』""''()[]{}<>\"\'')
NON_PREFIX_SYMBOLS = set('&$!@#%^*+=~`|\\/:;,.?')
UNIFIED_IMAGE_EXT = '.png'


def get_pinyin_initial(text):
    if not HAS_PINYIN:
        return ''
    i = 0
    while i < len(text) and text[i] in WRAPPING_SYMBOLS:
        i += 1
    if i >= len(text):
        return ''
    first_char = text[i]
    result = pinyin(first_char, style=Style.FIRST_LETTER, strict=False)
    for item in result:
        initial = item[0].upper() if item[0] else ''
        if initial:
            return initial
    return ''


def should_add_prefix(name):
    if not name:
        return False
    i = 0
    while i < len(name) and name[i] in WRAPPING_SYMBOLS:
        i += 1
    if i >= len(name):
        return False
    first_char = name[i]
    if first_char.isascii() and first_char.isalnum():
        return False
    if first_char in NON_PREFIX_SYMBOLS:
        return False
    return True


def get_prefixed_name(name):
    if not name:
        return name
    if not should_add_prefix(name):
        return name
    initial = get_pinyin_initial(name)
    if initial:
        return f"{initial}-{name}"
    return name


def parse_metadata(file_path):
    games = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

    current_game = None
    in_files_section = False

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith('#'):
            continue

        if in_files_section and ':' not in line_stripped:
            if line_stripped and current_game is not None:
                current_game.setdefault('files', []).append(line_stripped)
            continue

        if ':' not in line_stripped:
            continue

        key, value = line_stripped.split(':', 1)
        key = key.strip().lower()
        value = value.strip()

        in_files_section = False

        if key == 'game':
            if current_game:
                games.append(current_game)
            current_game = {'game': value}
        elif key == 'file' and current_game is not None:
            current_game['file'] = value
        elif key == 'files' and current_game is not None:
            if value:
                current_game.setdefault('files', []).append(value)
            in_files_section = True
        elif key == 'description' and current_game is not None:
            current_game['description'] = value
        elif key == 'developer' and current_game is not None:
            current_game['developer'] = value
        elif key == 'sort-by' and current_game is not None:
            current_game['sort-by'] = value
        elif key == 'assets.box_front' and current_game is not None:
            current_game['assets_box_front'] = value
        elif key == 'assets.logo' and current_game is not None:
            current_game['assets_logo'] = value
        elif key == 'assets.video' and current_game is not None:
            current_game['assets_video'] = value

    if current_game:
        games.append(current_game)

    return games


def is_archive(file_path):
    suffix = Path(file_path).suffix.lower()
    if suffix in ARCHIVE_EXTENSIONS:
        return True
    name = Path(file_path).name.lower()
    for ext in ['.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2']:
        if name.endswith(ext):
            return True
    return False


def get_archive_base_name(file_path):
    name = Path(file_path).name
    for ext in ['.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tbz2']:
        if name.lower().endswith(ext):
            return name[:-len(ext)]
    return Path(file_path).stem


def extract_archive(file_path, extract_to, log_func=None):
    ext = Path(file_path).suffix.lower()
    name = Path(file_path).name.lower()

    try:
        if name.endswith('.tar.gz') or name.endswith('.tgz'):
            shutil.unpack_archive(file_path, extract_to, 'gztar')
        elif name.endswith('.tar.bz2') or name.endswith('.tbz2'):
            shutil.unpack_archive(file_path, extract_to, 'bztar')
        elif name.endswith('.tar.xz'):
            shutil.unpack_archive(file_path, extract_to, 'xztar')
        elif ext == '.tar':
            shutil.unpack_archive(file_path, extract_to, 'tar')
        elif ext == '.zip' and HAS_ZIP:
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.extractall(extract_to)
        elif ext == '.rar' and HAS_RAR:
            with rarfile.RarFile(file_path, 'r') as rf:
                rf.extractall(extract_to)
        elif ext == '.7z' and HAS_7Z:
            with py7zr.SevenZipFile(file_path, mode='r') as sz:
                sz.extractall(extract_to)
        else:
            if log_func:
                log_func(f"    不支持的压缩格式: {ext}")
            return False

        if log_func:
            log_func(f"    解压成功")
        return True
    except Exception as e:
        if log_func:
            log_func(f"    解压失败: {str(e)}")
        return False


def collect_files_recursive(directory):
    files = []
    for root, dirs, filenames in os.walk(directory):
        for fname in sorted(filenames):
            files.append(os.path.join(root, fname))
    return files


def process_rom_file(file_path, target_dir, force_overwrite=False, copy_archives_directly=False, log_func=None):
    file_name = Path(file_path).name
    original_stem = Path(file_path).stem

    if copy_archives_directly:
        dest_path = os.path.join(target_dir, file_name)
        if os.path.exists(dest_path) and not force_overwrite:
            if log_func:
                log_func(f"  跳过: {file_name} (目标已存在)")
            return original_stem, None
        if os.path.exists(dest_path) and force_overwrite:
            if log_func:
                log_func(f"  覆盖: {file_name}")
        shutil.copy2(file_path, dest_path)
        if log_func:
            log_func(f"  复制: {file_name}")
        return original_stem, file_name

    if not is_archive(file_path):
        dest_path = os.path.join(target_dir, file_name)
        if os.path.exists(dest_path) and not force_overwrite:
            if log_func:
                log_func(f"  跳过: {file_name} (目标已存在)")
            return original_stem, None
        if os.path.exists(dest_path) and force_overwrite:
            if log_func:
                log_func(f"  覆盖: {file_name}")
        shutil.copy2(file_path, dest_path)
        if log_func:
            log_func(f"  复制: {file_name}")
        return original_stem, file_name

    base_name = get_archive_base_name(file_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        if log_func:
            log_func(f"  解压: {file_name}")
        if not extract_archive(file_path, temp_dir, log_func=log_func):
            return original_stem, None

        extracted_files = collect_files_recursive(temp_dir)
        if not extracted_files:
            if log_func:
                log_func(f"    警告: 压缩包内没有文件")
            return original_stem, None

        if len(extracted_files) == 1:
            src_file = extracted_files[0]
            src_ext = Path(src_file).suffix
            new_name = f"{base_name}{src_ext}"
            dest_path = os.path.join(target_dir, new_name)

            if os.path.exists(dest_path) and not force_overwrite:
                if log_func:
                    log_func(f"    跳过: {new_name} (目标已存在)")
                return original_stem, None

            shutil.copy2(src_file, dest_path)
            if log_func:
                if os.path.exists(dest_path) and force_overwrite:
                    log_func(f"    覆盖: {new_name}")
                else:
                    log_func(f"    -> {new_name}")
            return original_stem, new_name

        subfolder_name = base_name
        subfolder_path = os.path.join(target_dir, subfolder_name)
        counter = 1
        while os.path.exists(subfolder_path):
            subfolder_name = f"{base_name}_{counter}"
            subfolder_path = os.path.join(target_dir, subfolder_name)
            counter += 1

        os.makedirs(subfolder_path, exist_ok=True)
        if log_func:
            log_func(f"    创建子文件夹: {subfolder_name}/")

        success_count = 0
        for src_file in extracted_files:
            original_name = Path(src_file).name
            dest_path = os.path.join(subfolder_path, original_name)

            if os.path.exists(dest_path) and not force_overwrite:
                if log_func:
                    log_func(f"    跳过: {original_name} (已存在)")
                continue

            shutil.copy2(src_file, dest_path)
            if log_func:
                if os.path.exists(dest_path) and force_overwrite:
                    log_func(f"    覆盖: {original_name}")
                else:
                    log_func(f"    -> {original_name}")
            success_count += 1

        if success_count == 0:
            if log_func:
                log_func(f"    所有文件都已跳过或覆盖失败")
            return original_stem, None

        return original_stem, subfolder_name + "/"


def batch_process_roms(source_dir, target_dir, force_overwrite=False, copy_archives_directly=False, log_func=None):
    rom_mapping = {}

    source_path = Path(source_dir)
    if not source_path.is_dir():
        if log_func:
            log_func(f"错误：ROM源目录不存在: {source_dir}")
        return rom_mapping

    os.makedirs(target_dir, exist_ok=True)

    EXCLUDE_FILES = {'metadata.pegasus.txt'}
    files = [f for f in source_path.iterdir() if f.is_file() and f.name.lower() not in EXCLUDE_FILES]
    if not files:
        if log_func:
            log_func(f"ROM源目录下没有文件（已排除 metadata.pegasus.txt）")
        return rom_mapping

    if log_func:
        log_func(f"找到 {len(files)} 个ROM文件待处理")
        if force_overwrite:
            log_func(f"模式: 强制覆盖已存在的文件")
        else:
            log_func(f"模式: 跳过已存在的文件")
        if copy_archives_directly:
            log_func(f"压缩文件处理: 直接复制（不解压）")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, file_path in enumerate(files, 1):
        if log_func:
            log_func(f"\n[{i}/{len(files)}] 处理ROM: {file_path.name}")
        try:
            original_stem, actual_name = process_rom_file(
                str(file_path), target_dir, force_overwrite=force_overwrite,
                copy_archives_directly=copy_archives_directly, log_func=log_func)
            if actual_name is not None:
                rom_mapping[original_stem] = actual_name
                success_count += 1
            else:
                skip_count += 1
        except Exception as e:
            if log_func:
                log_func(f"    处理异常: {str(e)}")
            fail_count += 1

    if log_func:
        log_func(f"\nROM处理完成！成功: {success_count}, 跳过: {skip_count}, 失败: {fail_count}")
        log_func(f"映射表条目: {len(rom_mapping)}")

    return rom_mapping


def _get_asset_extension(asset_path, default='.png'):
    if asset_path:
        _, ext = os.path.splitext(asset_path)
        if ext:
            return ext
    return default


def _convert_image_to_png(src_path, dest_path, log_func=None):
    if not HAS_PIL:
        shutil.copy2(src_path, dest_path)
        return True

    _, src_ext = os.path.splitext(src_path)
    if src_ext.lower() == '.png':
        shutil.copy2(src_path, dest_path)
        return True

    try:
        with Image.open(src_path) as img:
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGBA')
            elif img.mode not in ('RGB',):
                img = img.convert('RGB')
            img.save(dest_path, 'PNG')
        if log_func:
            log_func(f"    格式转换: {src_ext} -> .png")
        return True
    except Exception as e:
        if log_func:
            log_func(f"    转换失败，直接复制: {str(e)}")
        shutil.copy2(src_path, dest_path)
        return False


def _build_asset_paths(game):
    game_name = game.get('game', '')
    video_path = game.get('assets_video', '')
    video_ext = _get_asset_extension(video_path, '.mp4')
    base = './assets'
    return {
        'thumbnail': f'{base}/covers/{game_name}{UNIFIED_IMAGE_EXT}',
        'marquee': f'{base}/marquees/{game_name}{UNIFIED_IMAGE_EXT}',
        'video': f'{base}/videos/{game_name}{video_ext}',
        'screenshot': f'{base}/screenshots/{game_name}{UNIFIED_IMAGE_EXT}',
        'image': f'{base}/covers/{game_name}{UNIFIED_IMAGE_EXT}',
    }


def find_metadata_files(source_dir, recursive=True):
    results = []
    if recursive:
        for root, dirs, files in os.walk(source_dir):
            if 'metadata.pegasus.txt' in files:
                results.append(os.path.join(root, 'metadata.pegasus.txt'))
    else:
        direct = os.path.join(source_dir, 'metadata.pegasus.txt')
        if os.path.isfile(direct):
            results.append(direct)
    return results


def process_media_folder(media_dir, output_base, file_to_game, force_overwrite=False, log_func=None):
    assets_dir = os.path.join(output_base, 'assets')
    covers_dir = os.path.join(assets_dir, 'covers')
    marquees_dir = os.path.join(assets_dir, 'marquees')
    videos_dir = os.path.join(assets_dir, 'videos')
    os.makedirs(covers_dir, exist_ok=True)
    os.makedirs(marquees_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)

    counts = {'covers': 0, 'marquees': 0, 'videos': 0}

    if not os.path.isdir(media_dir):
        return counts

    for item in os.listdir(media_dir):
        item_path = os.path.join(media_dir, item)
        if not os.path.isdir(item_path):
            continue
        subfolder_name = item
        target_name = file_to_game.get(subfolder_name, subfolder_name)
        if log_func:
            log_func(f"  处理媒体子文件夹: {subfolder_name} -> {target_name}")

        for filename in os.listdir(item_path):
            file_path = os.path.join(item_path, filename)
            if not os.path.isfile(file_path):
                continue
            name_without_ext, ext = os.path.splitext(filename)
            name_lower = name_without_ext.lower()

            if name_lower == 'boxfront':
                dest_path = os.path.join(covers_dir, f"{target_name}{UNIFIED_IMAGE_EXT}")
                if force_overwrite:
                    if log_func:
                        log_func(f"    覆盖: {dest_path}")
                    _convert_image_to_png(file_path, dest_path, log_func=log_func)
                else:
                    if os.path.exists(dest_path):
                        if log_func:
                            log_func(f"    跳过: {target_name}{UNIFIED_IMAGE_EXT} (已存在)")
                        continue
                    _convert_image_to_png(file_path, dest_path, log_func=log_func)
                if log_func:
                    log_func(f"    boxFront -> assets/covers/{target_name}{UNIFIED_IMAGE_EXT}")
                counts['covers'] += 1

            elif name_lower == 'logo':
                dest_path = os.path.join(marquees_dir, f"{target_name}{UNIFIED_IMAGE_EXT}")
                if force_overwrite:
                    if log_func:
                        log_func(f"    覆盖: {dest_path}")
                    _convert_image_to_png(file_path, dest_path, log_func=log_func)
                else:
                    if os.path.exists(dest_path):
                        if log_func:
                            log_func(f"    跳过: {target_name}{UNIFIED_IMAGE_EXT} (已存在)")
                        continue
                    _convert_image_to_png(file_path, dest_path, log_func=log_func)
                if log_func:
                    log_func(f"    logo -> assets/marquees/{target_name}{UNIFIED_IMAGE_EXT}")
                counts['marquees'] += 1

            elif name_lower == 'video':
                dest_path = os.path.join(videos_dir, f"{target_name}{ext}")
                if force_overwrite:
                    if log_func:
                        log_func(f"    覆盖: {dest_path}")
                    shutil.copy2(file_path, dest_path)
                else:
                    if os.path.exists(dest_path):
                        if log_func:
                            log_func(f"    跳过: {target_name}{ext} (已存在)")
                        continue
                    shutil.copy2(file_path, dest_path)
                if log_func:
                    log_func(f"    video -> assets/videos/{target_name}{ext}")
                counts['videos'] += 1

    return counts


def build_mapping_from_output_dir(target_dir, log_func=None):
    """
    从输出目录扫描已存在的文件，构建文件名映射。
    用于当未处理ROM文件时，从已有文件中推断映射关系。
    """
    mapping = {}
    if not os.path.isdir(target_dir):
        return mapping

    try:
        for entry in os.listdir(target_dir):
            entry_path = os.path.join(target_dir, entry)
            if os.path.isfile(entry_path):
                stem = Path(entry).stem
                mapping[stem] = entry
            elif os.path.isdir(entry_path) and not entry.startswith('assets'):
                mapping[entry] = entry + '/'
    except Exception as e:
        if log_func:
            log_func(f"    扫描输出目录失败: {str(e)}")

    if log_func:
        log_func(f"    从输出目录构建了 {len(mapping)} 个映射")
    return mapping


def resolve_file_path(file_val, rom_mapping=None):
    if not file_val:
        return './'
    stem = Path(file_val).stem
    if rom_mapping and stem in rom_mapping:
        actual_name = rom_mapping[stem]
        return './' + actual_name
    return './' + file_val


def create_gamelist_xml(games, output_path, name_prefix=True, rom_mapping=None):
    games_sorted = sorted(games, key=lambda g: g.get('sort-by', ''))

    root = ET.Element("gameList")
    generated_count = 0

    for game in games_sorted:
        game_name = game.get('game', '')
        files = game.get('files', [])
        if not files:
            file_val = game.get('file', '')
            if file_val:
                files = [file_val]
            else:
                files = ['']

        assets = _build_asset_paths(game)

        for file_val in files:
            game_elem = ET.SubElement(root, "game")

            resolved_path = resolve_file_path(file_val, rom_mapping)
            path_elem = ET.SubElement(game_elem, "path")
            path_elem.text = resolved_path

            if len(files) > 1:
                name_val = os.path.splitext(os.path.basename(file_val))[0]
            else:
                name_val = game_name
            if name_prefix:
                name_val = get_prefixed_name(name_val)
            name_elem = ET.SubElement(game_elem, "name")
            name_elem.text = name_val

            desc_elem = ET.SubElement(game_elem, "desc")
            desc_elem.text = game.get('description', '')

            thumbnail_elem = ET.SubElement(game_elem, "thumbnail")
            thumbnail_elem.text = assets['thumbnail']

            video_elem = ET.SubElement(game_elem, "video")
            video_elem.text = assets['video']

            screenshot_elem = ET.SubElement(game_elem, "screenshot")
            screenshot_elem.text = assets['screenshot']

            image_elem = ET.SubElement(game_elem, "image")
            image_elem.text = assets['image']

            marquee_elem = ET.SubElement(game_elem, "marquee")
            marquee_elem.text = assets['marquee']

            players_elem = ET.SubElement(game_elem, "players")
            players_elem.text = "1"

            id_elem = ET.SubElement(game_elem, "id")
            id_elem.text = str(uuid.uuid4())

            scrap_elem = ET.SubElement(game_elem, "scrap")
            scrap_elem.set('name', 'PegasusG')
            scrap_elem.set('date', time.strftime('%Y%m%dT%H%M%S'))

            generated_count += 1

    rough_str = ET.tostring(root, encoding='utf-8', method='xml')
    parsed = minidom.parseString(rough_str)
    pretty_xml = parsed.toprettyxml(indent="    ", encoding='utf-8')
    xml_str = pretty_xml.decode('utf-8')

    xml_str = xml_str.replace('<?xml version="1.0" encoding="utf-8"?>',
                              "<?xml version='1.0' encoding='utf-8'?>")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    return generated_count


def verify_gamelist_paths(gamelist_path, base_dir, log_func=None):
    if not os.path.isfile(gamelist_path):
        return

    tree = ET.parse(gamelist_path)
    root = tree.getroot()

    total = 0
    missing = 0

    for game_elem in root.findall('game'):
        path_elem = game_elem.find('path')
        if path_elem is None or not path_elem.text:
            continue

        total += 1
        rel_path = path_elem.text.strip()
        if rel_path.startswith('./'):
            rel_path = rel_path[2:]

        full_path = os.path.join(base_dir, rel_path)

        if rel_path.endswith('/'):
            if not os.path.isdir(full_path):
                missing += 1
                if log_func:
                    log_func(f"  ⚠  目录不存在: {rel_path}")
        else:
            if not os.path.isfile(full_path):
                missing += 1
                if log_func:
                    log_func(f"  ⚠  文件不存在: {rel_path}")

    if log_func:
        if missing == 0:
            log_func(f"  ✓ 路径验证通过: {total}/{total} 个路径均有效")
        else:
            log_func(f"  ✗ 路径验证: {missing}/{total} 个路径无效")


def run_integrated_process(config, log_func=None):
    source_dir = config.get('source_dir', '')
    rom_dir = config.get('rom_dir', '').strip()
    output_dir = config.get('output_dir', '').strip()
    force_overwrite = config.get('force_overwrite', False)
    add_prefix = config.get('add_prefix', True)
    do_roms = config.get('do_roms', True)
    do_media = config.get('do_media', True)
    do_gamelist = config.get('do_gamelist', True)
    do_screenshots = config.get('do_screenshots', False)
    no_subfolder = config.get('no_subfolder', False)
    recursive = config.get('recursive', True)
    copy_archives_directly = config.get('copy_archives_directly', False)
    screenshot_value_str = config.get('screenshot_value', '5')
    screenshot_unit = config.get('screenshot_unit', '秒')
    smart_screenshot = config.get('smart_screenshot', True)
    max_delay_sec_str = config.get('max_delay_sec', '30')
    ffmpeg_cmd = config.get('ffmpeg_path', 'ffmpeg').strip() or 'ffmpeg'
    solid_threshold_str = config.get('solid_threshold', '0.8')

    try:
        max_delay_sec = int(max_delay_sec_str)
        if max_delay_sec < 1:
            max_delay_sec = 1
        elif max_delay_sec > 300:
            max_delay_sec = 300
    except (ValueError, TypeError):
        max_delay_sec = 30

    try:
        screenshot_value = float(screenshot_value_str)
        if screenshot_value < 0.1:
            screenshot_value = 0.1
        elif screenshot_value > 3600:
            screenshot_value = 3600
    except ValueError:
        screenshot_value = 5.0

    try:
        solid_threshold = float(solid_threshold_str)
        if solid_threshold < 0.5:
            solid_threshold = 0.5
        elif solid_threshold > 0.99:
            solid_threshold = 0.99
    except (ValueError, TypeError):
        solid_threshold = 0.8

    if screenshot_unit == '帧':
        frame_time_sec = screenshot_value / 30.0
    else:
        frame_time_sec = screenshot_value

    if not source_dir:
        if log_func:
            log_func("错误：源目录为空，无法执行处理")
        return

    if not output_dir:
        output_dir = os.path.join(source_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isdir(source_dir):
        if log_func:
            log_func(f"错误：源目录不存在: {source_dir}")
        return

    if do_roms and not rom_dir:
        rom_dir = source_dir
        if log_func:
            log_func(f"提示：ROM目录未设置，默认使用源目录: {rom_dir}")

    metadata_files = find_metadata_files(source_dir, recursive=recursive)
    if not metadata_files:
        if log_func:
            log_func(f"未找到 metadata.pegasus.txt 文件")
        return

    if log_func:
        log_func(f"找到 {len(metadata_files)} 个 metadata.pegasus.txt 文件")

    total_stats = {'games': 0, 'covers': 0, 'marquees': 0, 'videos': 0, 'screenshots': 0}

    for meta_path in metadata_files:
        meta_dir = os.path.dirname(meta_path)
        folder_name = os.path.basename(meta_dir)

        if no_subfolder:
            target_dir = output_dir
        else:
            target_dir = os.path.join(output_dir, folder_name)
        os.makedirs(target_dir, exist_ok=True)

        if log_func:
            log_func(f"\n{'='*60}")
            log_func(f"处理: {folder_name}")
            if no_subfolder:
                log_func(f"  输出模式: 直接输出到目标目录 (不创建子文件夹)")
            log_func(f"{'='*60}")

        games = parse_metadata(meta_path)
        if not games:
            if log_func:
                log_func(f"  警告: metadata.pegasus.txt 为空或解析失败")
            continue

        if log_func:
            log_func(f"  解析到 {len(games)} 个游戏条目")

        file_to_game = {}
        for g in games:
            game_name = g.get('game', '')
            file_val = g.get('file', '')
            if file_val:
                file_base = os.path.splitext(os.path.basename(file_val))[0]
                file_to_game[file_base] = game_name
            for f in g.get('files', []):
                if f:
                    file_base = os.path.splitext(os.path.basename(f))[0]
                    file_to_game[file_base] = game_name

        rom_mapping = {}
        if do_roms and rom_dir and os.path.isdir(rom_dir):
            if log_func:
                log_func(f"\n  --- 步骤1: 处理ROM文件 (建立文件名映射) ---")
            rom_source_dir = os.path.join(rom_dir, folder_name) if os.path.isdir(os.path.join(rom_dir, folder_name)) else rom_dir
            rom_mapping = batch_process_roms(rom_source_dir, target_dir,
                                             force_overwrite=force_overwrite,
                                             copy_archives_directly=copy_archives_directly,
                                             log_func=log_func)
        else:
            if log_func:
                log_func(f"\n  --- 步骤1: 跳过ROM处理 ---")

        if do_gamelist:
            if not do_roms and rom_mapping == {}:
                if log_func:
                    log_func(f"\n  --- 补充: 从输出目录构建ROM映射 ---")
                rom_mapping = build_mapping_from_output_dir(target_dir, log_func=log_func)
                if not rom_mapping:
                    if log_func:
                        log_func(f"    输出目录为空，无映射可用，将使用原始文件名")

            if log_func:
                log_func(f"\n  --- 步骤2: 生成 gamelist.xml (使用实际输出路径) ---")

            generated = create_gamelist_xml(games, os.path.join(target_dir, 'gamelist.xml'),
                                            name_prefix=add_prefix, rom_mapping=rom_mapping)
            if log_func:
                log_func(f"  ✓ 已生成 gamelist.xml ({generated} 个游戏元素)")
            total_stats['games'] += generated
        else:
            if log_func:
                log_func(f"\n  --- 步骤2: 跳过 gamelist.xml 生成 ---")

        if do_media:
            media_dir = os.path.join(meta_dir, 'media')
            if os.path.isdir(media_dir):
                if log_func:
                    log_func(f"\n  --- 步骤3: 处理媒体文件 ---")
                counts = process_media_folder(media_dir, target_dir, file_to_game, force_overwrite=force_overwrite, log_func=log_func)
                total_stats['covers'] += counts['covers']
                total_stats['marquees'] += counts['marquees']
                total_stats['videos'] += counts['videos']
                if log_func:
                    log_func(f"    covers: {counts['covers']}, marquees: {counts['marquees']}, videos: {counts['videos']}")
            else:
                if log_func:
                    log_func(f"  未找到 media 目录，跳过媒体处理")

        if do_screenshots:
            media_dir = os.path.join(meta_dir, 'media')
            screenshots_dir = os.path.join(target_dir, 'assets', 'screenshots')
            os.makedirs(screenshots_dir, exist_ok=True)
            if os.path.isdir(media_dir):
                if log_func:
                    log_func(f"\n  --- 步骤4: 提取视频截图 ---")
                for subfolder in os.listdir(media_dir):
                    subfolder_path = os.path.join(media_dir, subfolder)
                    if not os.path.isdir(subfolder_path):
                        continue
                    target_name = file_to_game.get(subfolder, subfolder)
                    for fname in os.listdir(subfolder_path):
                        if fname.lower() == 'video.mp4' or fname.lower().startswith('video'):
                            video_path = os.path.join(subfolder_path, fname)
                            if not os.path.isfile(video_path):
                                continue
                            out_img = os.path.join(screenshots_dir, f"{target_name}.png")
                            if smart_screenshot and HAS_SMART_SCREENSHOT:
                                if extract_video_frame_with_fallback(
                                    video_path, out_img, frame_time_sec,
                                    max_delay_sec=max_delay_sec, step_sec=1,
                                    solid_threshold=solid_threshold,
                                    ffmpeg_cmd=ffmpeg_cmd,
                                    log_func=log_func):
                                    total_stats['screenshots'] += 1
                            else:
                                if extract_video_frame_simple(video_path, out_img, frame_time_sec, ffmpeg_cmd=ffmpeg_cmd, log_func=log_func):
                                    total_stats['screenshots'] += 1

        if do_gamelist:
            if log_func:
                log_func(f"\n  --- 步骤5: 验证 gamelist.xml 路径 ---")
            gamelist_path = os.path.join(target_dir, 'gamelist.xml')
            verify_gamelist_paths(gamelist_path, target_dir, log_func=log_func)

    if log_func:
        log_func(f"\n{'='*60}")
        log_func(f"全部完成！统计：")
        log_func(f"  游戏条目: {total_stats['games']}")
        log_func(f"  covers: {total_stats['covers']}")
        log_func(f"  marquees: {total_stats['marquees']}")
        log_func(f"  videos: {total_stats['videos']}")
        log_func(f"  screenshots: {total_stats['screenshots']}")


def extract_video_frame_simple(video_path, output_image_path, frame_time_sec=0, ffmpeg_cmd='ffmpeg', log_func=None):
    if not os.path.isfile(video_path):
        if log_func:
            log_func(f"  视频文件不存在: {video_path}")
        return False

    try:
        result = subprocess.run(
            [ffmpeg_cmd, '-y', '-ss', str(frame_time_sec), '-i', video_path,
             '-f', 'image2', '-frames:v', '1', '-q:v', '2', output_image_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0 and os.path.isfile(output_image_path):
            if log_func:
                log_func(f"    截图成功 -> {output_image_path}")
            return True
        else:
            if log_func:
                log_func(f"    截图失败")
            return False
    except Exception as e:
        if log_func:
            log_func(f"    截图异常: {str(e)}")
        return False


class IntegratedProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("天马G游戏元数据处理器")
        win_w, win_h = 750, 700
        screen_w = self.root.winfo_screenwidth()
        # screen_h = self.root.winfo_screenheight()
        x = (screen_w - win_w) // 2
        # y = (screen_h - win_h) // 2
        y = 10
        self.root.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.root.minsize(550, 580)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 5}

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, **pad)

        dirs_frame = ttk.LabelFrame(main_frame, text="目录设置")
        dirs_frame.pack(fill=tk.X, **pad)

        ttk.Label(dirs_frame, text="源目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.source_dir_var = tk.StringVar()
        ttk.Entry(dirs_frame, textvariable=self.source_dir_var, width=60).grid(
            row=0, column=1, padx=5, pady=3, sticky=tk.EW)
        ttk.Button(dirs_frame, text="浏览...", command=self._browse_source).grid(
            row=0, column=2, padx=5, pady=3)

        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dirs_frame, text="递归搜索子目录", variable=self.recursive_var).grid(
            row=0, column=3, padx=10, pady=3, sticky=tk.W)

        ttk.Label(dirs_frame, text="ROM目录:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.rom_dir_var = tk.StringVar()
        ttk.Entry(dirs_frame, textvariable=self.rom_dir_var, width=60).grid(
            row=1, column=1, padx=5, pady=3, sticky=tk.EW)
        ttk.Button(dirs_frame, text="浏览...", command=self._browse_rom).grid(
            row=1, column=2, padx=5, pady=3)
        ttk.Label(dirs_frame, text="(留空使用源目录)",
                  foreground='gray').grid(row=1, column=3, padx=10, pady=3, sticky=tk.W)

        ttk.Label(dirs_frame, text="输出目录:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        self.output_dir_var = tk.StringVar()
        ttk.Entry(dirs_frame, textvariable=self.output_dir_var, width=60).grid(
            row=2, column=1, padx=5, pady=3, sticky=tk.EW)
        ttk.Button(dirs_frame, text="浏览...", command=self._browse_output).grid(
            row=2, column=2, padx=5, pady=3)
        ttk.Label(dirs_frame, text="(留空输出到源目录/output)",
                  foreground='gray').grid(row=2, column=3, padx=10, pady=3, sticky=tk.W)

        self.no_subfolder_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dirs_frame, text="直接输出到目标目录 (不创建同名子文件夹)",
                        variable=self.no_subfolder_var).grid(row=3, column=0, columnspan=4, sticky=tk.W, padx=5, pady=2)

        dirs_frame.columnconfigure(1, weight=1)

        options_frame = ttk.LabelFrame(main_frame, text="处理选项")
        options_frame.pack(fill=tk.X, **pad)

        self.do_roms_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="处理ROM文件 (解压/复制，建立文件名映射)",
                        variable=self.do_roms_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)

        self.do_media_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="处理媒体文件 (covers/marquees/videos)",
                        variable=self.do_media_var).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)

        self.do_gamelist_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="生成 gamelist.xml 文件",
                        variable=self.do_gamelist_var, command=self._update_prefix_state).grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)

        self.add_prefix_var = tk.BooleanVar(value=True)
        self.add_prefix_cb = ttk.Checkbutton(options_frame, text="  └ 为游戏名称添加拼音首字母前缀",
                        variable=self.add_prefix_var)
        self.add_prefix_cb.grid(row=3, column=0, sticky=tk.W, padx=25, pady=2)
        self._update_prefix_state()

        self.force_overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="强制覆盖已存在的文件",
                        variable=self.force_overwrite_var).grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)

        self.copy_archives_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="直接复制压缩文件（不解压，保留原始压缩包）",
                        variable=self.copy_archives_var).grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)

        self.do_screenshots_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="从视频中提取截图 (需要ffmpeg)",
                        variable=self.do_screenshots_var, command=self._update_screenshot_state).grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)

        self.screenshot_frame = ttk.Frame(options_frame)
        self.screenshot_frame.grid(row=7, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

        ttk.Label(self.screenshot_frame, text="截图时间点:").pack(side=tk.LEFT, padx=(0, 5))
        self.screenshot_value_var = tk.StringVar(value="1")
        self.screenshot_value_entry = ttk.Entry(self.screenshot_frame, textvariable=self.screenshot_value_var, width=8)
        self.screenshot_value_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.screenshot_unit_var = tk.StringVar(value="秒")
        self.screenshot_radio_sec = ttk.Radiobutton(self.screenshot_frame, text="秒", variable=self.screenshot_unit_var,
                        value="秒")
        self.screenshot_radio_sec.pack(side=tk.LEFT, padx=(0, 5))
        self.screenshot_radio_frame = ttk.Radiobutton(self.screenshot_frame, text="帧", variable=self.screenshot_unit_var,
                        value="帧")
        self.screenshot_radio_frame.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(self.screenshot_frame, text="  ffmpeg路径:").pack(side=tk.LEFT, padx=(10, 2))
        self.ffmpeg_path_var = tk.StringVar(value="ffmpeg")
        self.ffmpeg_path_entry = ttk.Entry(self.screenshot_frame, textvariable=self.ffmpeg_path_var, width=20)
        self.ffmpeg_path_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.ffmpeg_browse_btn = ttk.Button(self.screenshot_frame, text="浏览", command=self._browse_ffmpeg, width=5)
        self.ffmpeg_browse_btn.pack(side=tk.LEFT)

        self.smart_screenshot_var = tk.BooleanVar(value=True)
        self.smart_frame = ttk.Frame(options_frame)
        self.smart_frame.grid(row=8, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)
        self.smart_screenshot_cb = ttk.Checkbutton(self.smart_frame, text="智能截图（检测纯色帧自动延后）",
                        variable=self.smart_screenshot_var)
        self.smart_screenshot_cb.pack(side=tk.LEFT)
        ttk.Label(self.smart_frame, text="最大延后:").pack(side=tk.LEFT, padx=(10, 2))
        self.max_delay_var = tk.StringVar(value="15")
        self.max_delay_entry = ttk.Entry(self.smart_frame, textvariable=self.max_delay_var, width=6)
        self.max_delay_entry.pack(side=tk.LEFT)
        ttk.Label(self.smart_frame, text="秒").pack(side=tk.LEFT, padx=(3, 0))
        ttk.Label(self.smart_frame, text=" 阈值:").pack(side=tk.LEFT, padx=(10, 2))
        self.solid_threshold_var = tk.StringVar(value="0.80")
        self.solid_threshold_entry = ttk.Entry(self.smart_frame, textvariable=self.solid_threshold_var, width=5)
        self.solid_threshold_entry.pack(side=tk.LEFT)
        ttk.Label(self.smart_frame, text="(0.50-0.99)").pack(side=tk.LEFT, padx=(3, 0))

        self._update_screenshot_state()

        row_idx = 9
        if not HAS_SMART_SCREENSHOT:
            ttk.Label(options_frame, text="提示: 智能截图模块未找到，将使用基础截图",
                      foreground='orange').grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=2)
            row_idx += 1
        elif not HAS_PIL:
            ttk.Label(options_frame, text="提示: 未安装Pillow，智能截图的纯色检测不可用",
                      foreground='orange').grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=2)
            row_idx += 1

        if not HAS_PINYIN:
            ttk.Label(options_frame, text="警告: 未安装pypinyin，名称前缀功能不可用",
                      foreground='red').grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=2)
            row_idx += 1

        if not HAS_PIL and HAS_SMART_SCREENSHOT:
            pass  # 已在上方提示
        elif not HAS_PIL:
            ttk.Label(options_frame, text="警告: 未安装Pillow，图片格式转换不可用",
                      foreground='red').grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=2)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, **pad)

        ttk.Button(button_frame, text="开始处理", command=self._start_processing).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="保存配置", command=self._save_config).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="加载配置", command=self._load_config).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="导出日志", command=self._export_log).pack(
            side=tk.RIGHT, padx=5, pady=5)
        ttk.Button(button_frame, text="清空日志", command=self._clear_log).pack(
            side=tk.RIGHT, padx=5, pady=5)

        log_frame = ttk.LabelFrame(main_frame, text="处理日志")
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD,
                                                   font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _browse_source(self):
        d = filedialog.askdirectory(title="选择源目录")
        if d:
            self.source_dir_var.set(d)

    def _browse_rom(self):
        d = filedialog.askdirectory(title="选择ROM文件目录")
        if d:
            self.rom_dir_var.set(d)

    def _browse_output(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir_var.set(d)

    def _log(self, msg):
        self.log_text.insert(tk.END, msg + '\n')
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _clear_log(self):
        self.log_text.delete('1.0', tk.END)

    def _export_log(self):
        log_content = self.log_text.get('1.0', tk.END).strip()
        if not log_content:
            messagebox.showinfo("提示", "日志为空，无需导出")
            return
        fpath = filedialog.asksaveasfilename(
            title="导出日志",
            defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not fpath:
            return
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(log_content)
            messagebox.showinfo("成功", f"日志已导出到:\n{fpath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出日志失败: {str(e)}")

    def _update_prefix_state(self):
        if self.do_gamelist_var.get():
            self.add_prefix_cb.config(state=tk.NORMAL)
        else:
            self.add_prefix_cb.config(state=tk.DISABLED)

    def _update_screenshot_state(self):
        state = tk.NORMAL if self.do_screenshots_var.get() else tk.DISABLED
        self.screenshot_value_entry.config(state=state)
        self.screenshot_radio_sec.config(state=state)
        self.screenshot_radio_frame.config(state=state)
        self.ffmpeg_path_entry.config(state=state)
        self.ffmpeg_browse_btn.config(state=state)
        self.smart_screenshot_cb.config(state=state)
        self.max_delay_entry.config(state=state)
        self.solid_threshold_entry.config(state=state)

    def _browse_ffmpeg(self):
        f = filedialog.askopenfilename(
            title="选择 ffmpeg 可执行文件",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
        if f:
            self.ffmpeg_path_var.set(f)

    def _get_config(self):
        return {
            'source_dir': self.source_dir_var.get().strip(),
            'rom_dir': self.rom_dir_var.get().strip(),
            'output_dir': self.output_dir_var.get().strip(),
            'do_roms': self.do_roms_var.get(),
            'do_media': self.do_media_var.get(),
            'do_gamelist': self.do_gamelist_var.get(),
            'add_prefix': self.add_prefix_var.get(),
            'force_overwrite': self.force_overwrite_var.get(),
            'copy_archives_directly': self.copy_archives_var.get(),
            'do_screenshots': self.do_screenshots_var.get(),
            'screenshot_value': self.screenshot_value_var.get().strip(),
            'screenshot_unit': self.screenshot_unit_var.get(),
            'smart_screenshot': self.smart_screenshot_var.get(),
            'max_delay_sec': self.max_delay_var.get().strip(),
            'solid_threshold': self.solid_threshold_var.get().strip(),
            'no_subfolder': self.no_subfolder_var.get(),
            'recursive': self.recursive_var.get(),
            'ffmpeg_path': self.ffmpeg_path_var.get().strip(),
        }

    def _save_config(self):
        config = self._get_config()
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"配置已保存到:\n{CONFIG_FILE}")
            self._log(f"配置已保存: {CONFIG_FILE}")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def _load_config(self):
        if not os.path.isfile(CONFIG_FILE):
            self._log("配置文件不存在，使用默认设置")
            return
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.source_dir_var.set(config.get('source_dir', ''))
            self.rom_dir_var.set(config.get('rom_dir', ''))
            self.output_dir_var.set(config.get('output_dir', ''))
            self.do_roms_var.set(config.get('do_roms', True))
            self.do_media_var.set(config.get('do_media', True))
            self.do_gamelist_var.set(config.get('do_gamelist', True))
            self.add_prefix_var.set(config.get('add_prefix', True))
            self.force_overwrite_var.set(config.get('force_overwrite', False))
            self.copy_archives_var.set(config.get('copy_archives_directly', False))
            self.do_screenshots_var.set(config.get('do_screenshots', False))
            self.screenshot_value_var.set(config.get('screenshot_value', '5'))
            self.screenshot_unit_var.set(config.get('screenshot_unit', '秒'))
            self.smart_screenshot_var.set(config.get('smart_screenshot', True))
            self.max_delay_var.set(config.get('max_delay_sec', '30'))
            self.solid_threshold_var.set(config.get('solid_threshold', '0.80'))
            self.ffmpeg_path_var.set(config.get('ffmpeg_path', 'ffmpeg'))
            self.no_subfolder_var.set(config.get('no_subfolder', False))
            self.recursive_var.set(config.get('recursive', True))
            self._update_prefix_state()
            self._update_screenshot_state()
            self._log(f"配置已加载: {CONFIG_FILE}")
        except Exception as e:
            self._log(f"加载配置失败: {str(e)}")

    def _start_processing(self):
        source_dir = self.source_dir_var.get().strip()
        if not source_dir:
            messagebox.showwarning("警告", "请选择源目录！")
            return
        if not os.path.isdir(source_dir):
            messagebox.showerror("错误", f"源目录不存在: {source_dir}")
            return

        config = self._get_config()

        rom_dir = config.get('rom_dir', '').strip() or source_dir
        output_dir = config.get('output_dir', '').strip() or os.path.join(source_dir, 'output')

        self._log("=" * 60)
        self._log("开始整合处理 (Correct by Construction)...")
        self._log(f"源目录: {source_dir}")
        self._log(f"ROM目录: {rom_dir}")
        self._log(f"输出目录: {output_dir}")
        self._log("=" * 60)

        thread = threading.Thread(target=self._run_processing, args=(config,), daemon=True)
        thread.start()

    def _run_processing(self, config):
        try:
            run_integrated_process(config, log_func=self._log)
        except Exception as e:
            self._log(f"\n处理异常: {str(e)}")
            import traceback
            self._log(traceback.format_exc())


def main():
    root = tk.Tk()
    app = IntegratedProcessorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
