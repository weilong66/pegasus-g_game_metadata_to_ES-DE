import os
import sys
import json
import shutil
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'batch_processor_config.json')

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


def process_file(file_path, target_dir, force_overwrite=False, log_func=None):
    file_name = Path(file_path).name

    if not is_archive(file_path):
        dest_path = os.path.join(target_dir, file_name)
        if os.path.exists(dest_path) and not force_overwrite:
            if log_func:
                log_func(f"  跳过: {file_name} (目标已存在)")
            return False
        if os.path.exists(dest_path) and force_overwrite:
            if log_func:
                log_func(f"  覆盖: {file_name}")
        shutil.copy2(file_path, dest_path)
        if log_func:
            log_func(f"  复制: {file_name}")
        return True

    base_name = get_archive_base_name(file_path)

    with tempfile.TemporaryDirectory() as temp_dir:
        if log_func:
            log_func(f"  解压: {file_name}")
        if not extract_archive(file_path, temp_dir, log_func=log_func):
            return False

        extracted_files = collect_files_recursive(temp_dir)
        if not extracted_files:
            if log_func:
                log_func(f"    警告: 压缩包内没有文件")
            return False

        if len(extracted_files) == 1:
            src_file = extracted_files[0]
            src_ext = Path(src_file).suffix
            new_name = f"{base_name}{src_ext}"
            dest_path = os.path.join(target_dir, new_name)

            if os.path.exists(dest_path) and not force_overwrite:
                if log_func:
                    log_func(f"    跳过: {new_name} (目标已存在)")
                return False

            shutil.copy2(src_file, dest_path)
            if log_func:
                if os.path.exists(os.path.join(target_dir, new_name)) and force_overwrite:
                    log_func(f"    覆盖: {new_name}")
                else:
                    log_func(f"    -> {new_name}")
            return True

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
            return False

    return True


def batch_process(source_dir, target_dir, force_overwrite=False, log_func=None):
    source_path = Path(source_dir)
    if not source_path.is_dir():
        if log_func:
            log_func(f"错误：源目录不存在: {source_dir}")
        return

    os.makedirs(target_dir, exist_ok=True)

    files = [f for f in source_path.iterdir() if f.is_file()]
    if not files:
        if log_func:
            log_func(f"源目录下没有文件")
        return

    if log_func:
        log_func(f"找到 {len(files)} 个文件待处理")
        if force_overwrite:
            log_func(f"模式: 强制覆盖已存在的文件")
        else:
            log_func(f"模式: 跳过已存在的文件")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for i, file_path in enumerate(files, 1):
        if log_func:
            log_func(f"\n[{i}/{len(files)}] 处理: {file_path.name}")
        try:
            result = process_file(str(file_path), target_dir, force_overwrite=force_overwrite, log_func=log_func)
            if result is True:
                success_count += 1
            elif result is False:
                skip_count += 1
        except Exception as e:
            if log_func:
                log_func(f"    处理异常: {str(e)}")
            fail_count += 1

    if log_func:
        log_func(f"\n{'='*50}")
        log_func(f"处理完成！成功: {success_count}, 跳过: {skip_count}, 失败: {fail_count}")


class BatchProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("批量文件处理器 - 压缩包解压与文件复制")
        self.root.geometry("650x600")
        self.root.minsize(600, 550)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 5}

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, **pad)

        source_frame = ttk.LabelFrame(main_frame, text="源目录")
        source_frame.pack(fill=tk.X, **pad)

        ttk.Label(source_frame, text="源目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.source_dir_var = tk.StringVar()
        ttk.Entry(source_frame, textvariable=self.source_dir_var, width=55).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(source_frame, text="浏览...", command=self._browse_source).grid(
            row=0, column=2, padx=5, pady=5)

        ttk.Label(source_frame, text="（仅处理目录下的文件，不处理子文件夹）",
                  foreground='gray').grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        target_frame = ttk.LabelFrame(main_frame, text="目标目录")
        target_frame.pack(fill=tk.X, **pad)

        ttk.Label(target_frame, text="目标目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_dir_var = tk.StringVar()
        ttk.Entry(target_frame, textvariable=self.target_dir_var, width=55).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(target_frame, text="浏览...", command=self._browse_target).grid(
            row=0, column=2, padx=5, pady=5)

        options_frame = ttk.LabelFrame(main_frame, text="处理选项")
        options_frame.pack(fill=tk.X, **pad)

        self.force_overwrite_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="强制覆盖已存在的文件（不勾选时跳过）",
                        variable=self.force_overwrite_var).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)

        info_frame = ttk.LabelFrame(main_frame, text="支持的格式")
        info_frame.pack(fill=tk.X, **pad)

        formats_text = "压缩包: .zip, .rar, .7z, .tar, .tar.gz, .tar.bz2, .tar.xz\n其他文件: 直接复制到目标目录\n单文件压缩包: 解压后重命名为压缩文件名\n多文件压缩包: 解压到以压缩文件名命名的子文件夹中"
        ttk.Label(info_frame, text=formats_text, foreground='gray').pack(
            anchor=tk.W, padx=5, pady=5)

        if not HAS_ZIP:
            ttk.Label(info_frame, text="提示: 未安装 zipfile (Python自带，应该可用)",
                      foreground='red').pack(anchor=tk.W, padx=5)
        if not HAS_RAR:
            ttk.Label(info_frame, text="可选: 未安装 rarfile，无法处理 .rar 格式。运行: pip install rarfile",
                      foreground='orange').pack(anchor=tk.W, padx=5)
        if not HAS_7Z:
            ttk.Label(info_frame, text="可选: 未安装 py7zr，无法处理 .7z 格式。运行: pip install py7zr",
                      foreground='orange').pack(anchor=tk.W, padx=5)

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

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD,
                                                   font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        source_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(1, weight=1)

    def _browse_source(self):
        d = filedialog.askdirectory(title="选择源目录")
        if d:
            self.source_dir_var.set(d)

    def _browse_target(self):
        d = filedialog.askdirectory(title="选择目标目录")
        if d:
            self.target_dir_var.set(d)

    def _log(self, msg):
        self.log_text.insert(tk.END, msg + '\n')
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _clear_log(self):
        self.log_text.delete('1.0', tk.END)

    def _get_config(self):
        return {
            'source_dir': self.source_dir_var.get().strip(),
            'target_dir': self.target_dir_var.get().strip(),
            'force_overwrite': self.force_overwrite_var.get(),
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
            self.target_dir_var.set(config.get('target_dir', ''))
            self.force_overwrite_var.set(config.get('force_overwrite', False))
            self._log(f"配置已加载: {CONFIG_FILE}")
        except Exception as e:
            self._log(f"加载配置失败: {str(e)}")

    def _start_processing(self):
        source_dir = self.source_dir_var.get().strip()
        target_dir = self.target_dir_var.get().strip()
        force_overwrite = self.force_overwrite_var.get()

        if not source_dir:
            messagebox.showwarning("警告", "请选择源目录！")
            return
        if not os.path.isdir(source_dir):
            messagebox.showerror("错误", f"源目录不存在: {source_dir}")
            return
        if not target_dir:
            messagebox.showwarning("警告", "请选择目标目录！")
            return

        self._log("=" * 50)
        self._log("开始处理...")
        self._log(f"源目录: {source_dir}")
        self._log(f"目标目录: {target_dir}")
        if force_overwrite:
            self._log("强制覆盖: 开启")
        else:
            self._log("强制覆盖: 关闭（跳过已存在的文件）")
        self._log("=" * 50)

        thread = threading.Thread(target=self._run_processing,
                                  args=(source_dir, target_dir, force_overwrite), daemon=True)
        thread.start()

    def _run_processing(self, source_dir, target_dir, force_overwrite):
        try:
            batch_process(source_dir, target_dir, force_overwrite=force_overwrite, log_func=self._log)
        except Exception as e:
            self._log(f"\n处理异常: {str(e)}")
            import traceback
            self._log(traceback.format_exc())


def main():
    root = tk.Tk()
    app = BatchProcessorApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
