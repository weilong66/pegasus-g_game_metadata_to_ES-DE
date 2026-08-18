import os
import sys
import json
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import xml.etree.ElementTree as ET
from xml.dom import minidom

try:
    from pypinyin import pinyin, Style
    HAS_PINYIN = True
except ImportError:
    HAS_PINYIN = False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'pegasus_gamelist_config.json')

WRAPPING_SYMBOLS = set('《》（）【】「」『』""''()[]{}<>\"\'')
NON_PREFIX_SYMBOLS = set('&$!@#%^*+=~`|\\/:;,.?')


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
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip().lower()
        value = value.strip()

        if key == 'game':
            if current_game:
                games.append(current_game)
            current_game = {'game': value}
        elif key == 'file' and current_game is not None:
            current_game['file'] = value
        elif key == 'description' and current_game is not None:
            current_game['description'] = value
        elif key == 'developer' and current_game is not None:
            current_game['developer'] = value
        elif key == 'sort-by' and current_game is not None:
            current_game['sort-by'] = value

    if current_game:
        games.append(current_game)

    return games


def create_gamelist_xml(games, output_path, name_prefix=True):
    root = ET.Element("gameList")
    for game in games:
        game_elem = ET.SubElement(root, "game")
        file_val = game.get('file', '')
        path_elem = ET.SubElement(game_elem, "path")
        path_elem.text = "./" + file_val if file_val else "./"

        name_val = game.get('game', '')
        if name_prefix:
            name_val = get_prefixed_name(name_val)
        name_elem = ET.SubElement(game_elem, "name")
        name_elem.text = name_val

        desc_elem = ET.SubElement(game_elem, "desc")
        desc_elem.text = game.get('description', '')

        playcount_elem = ET.SubElement(game_elem, "playcount")
        playcount_elem.text = "1"

        ET.SubElement(game_elem, "lastplayed")

    rough_str = ET.tostring(root, encoding='utf-8', method='xml')
    parsed = minidom.parseString(rough_str)
    pretty_xml = parsed.toprettyxml(indent="    ", encoding='utf-8')
    xml_str = pretty_xml.decode('utf-8')

    xml_str = xml_str.replace('<?xml version="1.0" encoding="utf-8"?>',
                              "<?xml version='1.0' encoding='utf-8'?>")
    xml_str = xml_str.replace('<lastplayed/>', '<lastplayed />')
    xml_str = xml_str.replace('<playcount>1</playcount>', '<playcount>1</playcount>')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)


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


def process_media_folder(media_dir, output_base, game_name, log_func=None):
    covers_dir = os.path.join(output_base, 'covers')
    marquees_dir = os.path.join(output_base, 'marquees')
    videos_dir = os.path.join(output_base, 'videos')
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
        if log_func:
            log_func(f"  处理媒体子文件夹: {subfolder_name}")

        for filename in os.listdir(item_path):
            file_path = os.path.join(item_path, filename)
            if not os.path.isfile(file_path):
                continue
            name_without_ext, ext = os.path.splitext(filename)
            name_lower = name_without_ext.lower()

            if name_lower == 'boxfront':
                dest_path = os.path.join(covers_dir, f"{subfolder_name}{ext}")
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(covers_dir, f"{subfolder_name}_{counter}{ext}")
                    counter += 1
                shutil.copy2(file_path, dest_path)
                if log_func:
                    log_func(f"    boxFront -> covers/{subfolder_name}{ext}")
                counts['covers'] += 1

            elif name_lower == 'logo':
                dest_path = os.path.join(marquees_dir, f"{subfolder_name}{ext}")
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(marquees_dir, f"{subfolder_name}_{counter}{ext}")
                    counter += 1
                shutil.copy2(file_path, dest_path)
                if log_func:
                    log_func(f"    logo -> marquees/{subfolder_name}{ext}")
                counts['marquees'] += 1

            elif name_lower == 'video':
                dest_path = os.path.join(videos_dir, f"{subfolder_name}{ext}")
                counter = 1
                while os.path.exists(dest_path):
                    dest_path = os.path.join(videos_dir, f"{subfolder_name}_{counter}{ext}")
                    counter += 1
                shutil.copy2(file_path, dest_path)
                if log_func:
                    log_func(f"    video -> videos/{subfolder_name}{ext}")
                counts['videos'] += 1

    return counts


def get_video_duration(video_path, ffmpeg_path):
    ffprobe_path = ffmpeg_path
    if ffprobe_path.endswith('ffmpeg') or ffprobe_path.endswith('ffmpeg.exe'):
        ffprobe_path = ffprobe_path.replace('ffmpeg', 'ffprobe')

    if not shutil.which(ffprobe_path) and not os.path.isfile(ffprobe_path):
        ffprobe_path = shutil.which('ffprobe') or 'ffprobe'

    cmd = [
        ffprobe_path, '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        if result.returncode == 0:
            duration_str = result.stdout.decode('utf-8', errors='ignore').strip()
            if duration_str:
                return float(duration_str)
    except Exception:
        pass
    return None


def extract_video_frame(video_path, output_image_path, ffmpeg_path, frame_time_sec, log_func=None):
    if not os.path.isfile(video_path):
        if log_func:
            log_func(f"  视频文件不存在: {video_path}")
        return False

    duration = get_video_duration(video_path, ffmpeg_path)
    actual_time = frame_time_sec
    if duration is not None and frame_time_sec >= duration:
        actual_time = max(0, duration - 1)
        if log_func:
            log_func(f"    指定时间 {frame_time_sec}s 超出视频时长 {duration:.1f}s，调整为 {actual_time:.1f}s（最后一秒）")

    output_dir = os.path.dirname(output_image_path)
    base_name = os.path.splitext(os.path.basename(output_image_path))[0]

    candidates = [output_image_path]
    if output_image_path.endswith('.png'):
        candidates.append(os.path.join(output_dir, f"{base_name}.jpg"))
    elif output_image_path.endswith('.jpg'):
        candidates.append(os.path.join(output_dir, f"{base_name}.png"))

    last_err = ''
    for candidate in candidates:
        cmd = [
            ffmpeg_path, '-y',
            '-ss', str(actual_time),
            '-i', video_path,
            '-f', 'image2',
            '-frames:v', '1',
            '-q:v', '2',
            candidate
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if result.returncode == 0 and os.path.isfile(candidate):
                if candidate != output_image_path:
                    if os.path.isfile(output_image_path):
                        os.remove(output_image_path)
                    shutil.copy2(candidate, output_image_path)
                    os.remove(candidate)
                if log_func:
                    log_func(f"    截图成功 -> {output_image_path}")
                return True
            else:
                last_err = result.stderr.decode('utf-8', errors='ignore')[:300]
        except FileNotFoundError:
            if log_func:
                log_func(f"    ffmpeg 未找到: {ffmpeg_path}")
            return False
        except Exception as e:
            last_err = str(e)

    if log_func:
        log_func(f"    截图失败: {last_err}")
        log_func(f"    提示: 当前ffmpeg可能不支持图片输出格式，建议使用完整版ffmpeg")
    return False


def process_all(config, log_func=None):
    source_dir = config.get('source_dir', '')
    custom_output_dir = config.get('output_dir', '').strip()
    output_folder_name = config.get('output_folder', 'output')
    do_metadata = config.get('do_metadata', True)
    do_media = config.get('do_media', True)
    do_screenshots = config.get('do_screenshots', False)
    ffmpeg_path = config.get('ffmpeg_path', 'ffmpeg')
    frame_time = config.get('frame_time', 0)
    recursive = config.get('recursive', True)
    add_prefix = config.get('add_prefix', True)

    if custom_output_dir:
        output_dir = custom_output_dir
    else:
        output_dir = os.path.join(BASE_DIR, output_folder_name)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isdir(source_dir):
        if log_func:
            log_func(f"错误：源目录不存在: {source_dir}")
        return

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
        target_dir = os.path.join(output_dir, folder_name)
        os.makedirs(target_dir, exist_ok=True)

        if log_func:
            log_func(f"\n{'='*50}")
            log_func(f"处理: {folder_name}")
            log_func(f"{'='*50}")

        if do_metadata:
            if log_func:
                log_func(f"  解析 metadata.pegasus.txt ...")
            games = parse_metadata(meta_path)
            if log_func:
                log_func(f"  找到 {len(games)} 个游戏条目")

            if games:
                xml_path = os.path.join(target_dir, 'gamelist.xml')
                create_gamelist_xml(games, xml_path, name_prefix=add_prefix)
                if log_func:
                    log_func(f"  已生成 gamelist.xml")
                total_stats['games'] += len(games)

        if do_media:
            media_dir = os.path.join(meta_dir, 'media')
            if os.path.isdir(media_dir):
                if log_func:
                    log_func(f"  处理媒体文件...")
                media_base = target_dir
                counts = process_media_folder(media_dir, media_base, folder_name, log_func=log_func)
                total_stats['covers'] += counts['covers']
                total_stats['marquees'] += counts['marquees']
                total_stats['videos'] += counts['videos']
                if log_func:
                    log_func(f"    covers: {counts['covers']}, marquees: {counts['marquees']}, videos: {counts['videos']}")
            else:
                if log_func:
                    log_func(f"  未找到 media 目录")

        if do_screenshots:
            media_dir = os.path.join(meta_dir, 'media')
            screenshots_dir = os.path.join(target_dir, 'screenshots')
            os.makedirs(screenshots_dir, exist_ok=True)

            if os.path.isdir(media_dir):
                if log_func:
                    log_func(f"  提取视频截图 (帧时间: {frame_time}s)...")
                for subfolder in os.listdir(media_dir):
                    subfolder_path = os.path.join(media_dir, subfolder)
                    if not os.path.isdir(subfolder_path):
                        continue
                    for fname in os.listdir(subfolder_path):
                        if fname.lower() == 'video.mp4' or fname.lower().startswith('video'):
                            video_path = os.path.join(subfolder_path, fname)
                            if not os.path.isfile(video_path):
                                continue
                            out_img = os.path.join(screenshots_dir, f"{subfolder}.png")
                            if extract_video_frame(video_path, out_img, ffmpeg_path, frame_time, log_func=log_func):
                                total_stats['screenshots'] += 1
            else:
                if log_func:
                    log_func(f"  未找到 media 目录，跳过截图")

    if log_func:
        log_func(f"\n{'='*50}")
        log_func(f"全部完成！统计：")
        log_func(f"  游戏条目: {total_stats['games']}")
        log_func(f"  covers: {total_stats['covers']}")
        log_func(f"  marquees: {total_stats['marquees']}")
        log_func(f"  videos: {total_stats['videos']}")
        log_func(f"  screenshots: {total_stats['screenshots']}")


class PegasusConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pegasus Metadata 转换器")
        self.root.geometry("700x650")
        self.root.minsize(650, 600)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 5}

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, **pad)

        source_frame = ttk.LabelFrame(main_frame, text="源目录设置")
        source_frame.pack(fill=tk.X, **pad)

        ttk.Label(source_frame, text="源目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.source_dir_var = tk.StringVar()
        ttk.Entry(source_frame, textvariable=self.source_dir_var, width=55).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(source_frame, text="浏览...", command=self._browse_source).grid(
            row=0, column=2, padx=5, pady=5)

        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(source_frame, text="递归搜索子目录", variable=self.recursive_var).grid(
            row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        output_frame = ttk.LabelFrame(main_frame, text="输出设置")
        output_frame.pack(fill=tk.X, **pad)

        ttk.Label(output_frame, text="输出目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.output_dir_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_dir_var, width=50).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(output_frame, text="浏览...", command=self._browse_output).grid(
            row=0, column=2, padx=5, pady=5)

        ttk.Label(output_frame, text="输出文件夹名:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.output_folder_var = tk.StringVar(value="output")
        ttk.Entry(output_frame, textvariable=self.output_folder_var, width=30).grid(
            row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(output_frame, text="(未设置输出目录时，保存到脚本目录下此文件夹)", foreground='gray').grid(
            row=1, column=2, padx=5, pady=5, sticky=tk.W)

        options_frame = ttk.LabelFrame(main_frame, text="处理选项")
        options_frame.pack(fill=tk.X, **pad)

        self.do_metadata_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="解析metadata.pegasus.txt并生成gamelist.xml",
                        variable=self.do_metadata_var).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)

        self.add_prefix_var = tk.BooleanVar(value=True)
        cb = ttk.Checkbutton(options_frame, text="为游戏名称添加拼音首字母前缀 (如 H-黄金太阳)",
                             variable=self.add_prefix_var)
        cb.grid(row=1, column=0, sticky=tk.W, padx=25, pady=2)

        self.do_media_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="分类处理媒体文件 (covers/marquees/videos)",
                        variable=self.do_media_var).grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)

        self.do_screenshots_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="从视频中提取截图 (需要ffmpeg)",
                        variable=self.do_screenshots_var).grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)

        ffmpeg_frame = ttk.LabelFrame(main_frame, text="FFmpeg 设置")
        ffmpeg_frame.pack(fill=tk.X, **pad)

        ttk.Label(ffmpeg_frame, text="FFmpeg路径:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.ffmpeg_path_var = tk.StringVar(value="ffmpeg")
        ttk.Entry(ffmpeg_frame, textvariable=self.ffmpeg_path_var, width=50).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(ffmpeg_frame, text="浏览...", command=self._browse_ffmpeg).grid(
            row=0, column=2, padx=5, pady=5)

        ttk.Label(ffmpeg_frame, text="截图时间(秒):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.frame_time_var = tk.StringVar(value="1")
        ttk.Entry(ffmpeg_frame, textvariable=self.frame_time_var, width=10).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(ffmpeg_frame, text="(从视频开头算起的秒数，如 5 表示第5秒)",
                  foreground='gray').grid(row=1, column=1, columnspan=2, sticky=tk.W, padx=(80, 5), pady=5)

        if not HAS_PINYIN:
            pinyin_warn = ttk.Label(ffmpeg_frame,
                                    text="警告: 未安装pypinyin，名称前缀功能不可用。请运行: pip install pypinyin",
                                    foreground='red')
            pinyin_warn.grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, **pad)

        ttk.Button(button_frame, text="开始处理", command=self._start_processing).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="保存配置", command=self._save_config).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="加载配置", command=self._load_config).pack(
            side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="清空日志", command=self._clear_log).pack(
            side=tk.RIGHT, padx=5, pady=5)

        log_frame = ttk.LabelFrame(main_frame, text="处理日志")
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD,
                                                   font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        source_frame.columnconfigure(1, weight=1)
        output_frame.columnconfigure(1, weight=1)
        ffmpeg_frame.columnconfigure(1, weight=1)

    def _browse_source(self):
        d = filedialog.askdirectory(title="选择源目录")
        if d:
            self.source_dir_var.set(d)

    def _browse_output(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir_var.set(d)

    def _browse_ffmpeg(self):
        f = filedialog.askopenfilename(
            title="选择ffmpeg可执行文件",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
        if f:
            self.ffmpeg_path_var.set(f)

    def _log(self, msg):
        self.log_text.insert(tk.END, msg + '\n')
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _clear_log(self):
        self.log_text.delete('1.0', tk.END)

    def _get_config(self):
        try:
            frame_time = float(self.frame_time_var.get())
        except ValueError:
            frame_time = 0
        return {
            'source_dir': self.source_dir_var.get().strip(),
            'output_dir': self.output_dir_var.get().strip(),
            'output_folder': self.output_folder_var.get().strip() or 'output',
            'do_metadata': self.do_metadata_var.get(),
            'do_media': self.do_media_var.get(),
            'do_screenshots': self.do_screenshots_var.get(),
            'ffmpeg_path': self.ffmpeg_path_var.get().strip() or 'ffmpeg',
            'frame_time': frame_time,
            'recursive': self.recursive_var.get(),
            'add_prefix': self.add_prefix_var.get(),
        }

    def _save_config(self):
        config = self._get_config()
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"配置已保存到:\n{CONFIG_FILE}")
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
            self.output_dir_var.set(config.get('output_dir', ''))
            self.output_folder_var.set(config.get('output_folder', 'output'))
            self.do_metadata_var.set(config.get('do_metadata', True))
            self.do_media_var.set(config.get('do_media', True))
            self.do_screenshots_var.set(config.get('do_screenshots', False))
            self.ffmpeg_path_var.set(config.get('ffmpeg_path', 'ffmpeg'))
            self.frame_time_var.set(str(config.get('frame_time', 0)))
            self.recursive_var.set(config.get('recursive', True))
            self.add_prefix_var.set(config.get('add_prefix', True))
            self._log(f"配置已加载: {CONFIG_FILE}")
        except Exception as e:
            self._log(f"加载配置失败: {str(e)}")

    def _start_processing(self):
        config = self._get_config()
        source_dir = config.get('source_dir', '')
        if not source_dir:
            messagebox.showwarning("警告", "请选择源目录！")
            return
        if not os.path.isdir(source_dir):
            messagebox.showerror("错误", f"源目录不存在: {source_dir}")
            return

        if not config.get('do_metadata', True) and not config.get('do_media', True) and not config.get('do_screenshots', False):
            messagebox.showwarning("警告", "请至少选择一项处理选项！")
            return

        if config.get('do_screenshots', False):
            ffmpeg_exe = config.get('ffmpeg_path', 'ffmpeg')
            if not os.path.isfile(ffmpeg_exe) and not shutil.which(ffmpeg_exe):
                messagebox.showerror("错误", f"ffmpeg未找到: {ffmpeg_exe}\n请安装ffmpeg或指定ffmpeg可执行文件路径")
                return

        self._log("=" * 50)
        self._log("开始处理...")
        self._log(f"源目录: {source_dir}")
        custom_out = config.get('output_dir', '').strip()
        if custom_out:
            self._log(f"输出目录: {custom_out}")
        else:
            self._log(f"输出目录: {os.path.join(BASE_DIR, config.get('output_folder', 'output'))}")
        self._log("=" * 50)

        thread = threading.Thread(target=self._run_processing, args=(config,), daemon=True)
        thread.start()

    def _run_processing(self, config):
        try:
            process_all(config, log_func=self._log)
        except Exception as e:
            self._log(f"\n处理异常: {str(e)}")
            import traceback
            self._log(traceback.format_exc())


def main():
    root = tk.Tk()
    app = PegasusConverterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()