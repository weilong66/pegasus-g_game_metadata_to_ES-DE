import os
import sys
import re
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, 'update_paths_config.json')


def scan_directory(directory, log_func=None):
    files_map = {}
    subfolders = set()

    if not os.path.isdir(directory):
        if log_func:
            log_func(f"目录不存在: {directory}")
        return files_map, subfolders

    for entry in os.listdir(directory):
        entry_path = os.path.join(directory, entry)
        if os.path.isfile(entry_path):
            stem = Path(entry).stem
            ext = Path(entry).suffix.lower()
            if stem not in files_map:
                files_map[stem] = []
            files_map[stem].append({
                'name': entry,
                'ext': ext,
                'path': entry_path,
            })
        elif os.path.isdir(entry_path):
            subfolders.add(entry)

    if log_func:
        log_func(f"扫描完成: 找到 {len(files_map)} 个文件名匹配, {len(subfolders)} 个子文件夹")

    return files_map, subfolders


def _resolve_gamelist_path(path, log_func=None):
    if os.path.isfile(path):
        return path
    if os.path.isdir(path):
        candidate = os.path.join(path, 'gamelist.xml')
        if os.path.isfile(candidate):
            if log_func:
                log_func(f"在目录下找到 gamelist.xml: {candidate}")
            return candidate
        if log_func:
            log_func(f"错误: 目录下未找到 gamelist.xml: {path}")
        return None
    if log_func:
        log_func(f"错误: 路径不存在: {path}")
    return None


def update_gamelist_paths(gamelist_path, target_dir, output_path=None, log_func=None):
    resolved_gamelist = _resolve_gamelist_path(gamelist_path, log_func=log_func)
    if resolved_gamelist is None:
        return False
    gamelist_path = resolved_gamelist

    if output_path is None:
        output_path = gamelist_path
    elif os.path.isdir(output_path):
        output_path = os.path.join(output_path, 'gamelist.xml')
        if log_func:
            log_func(f"输出路径为目录，将保存到: {output_path}")

    files_map, subfolders = scan_directory(target_dir, log_func=log_func)

    if log_func:
        log_func(f"解析 gamelist.xml: {gamelist_path}")

    tree = ET.parse(gamelist_path)
    root = tree.getroot()

    if log_func:
        log_func(f"找到 {len(root.findall('game'))} 个游戏条目")

    updated_count = 0
    not_found_count = 0
    subfolder_count = 0

    for game_elem in root.findall('game'):
        path_elem = game_elem.find('path')
        if path_elem is None or not path_elem.text:
            if log_func:
                log_func(f"  跳过: 无 path 元素")
            continue

        old_path = path_elem.text.strip()
        old_name = os.path.basename(old_path)
        old_stem = Path(old_name).stem

        if old_stem in files_map:
            matches = files_map[old_stem]
            if len(matches) == 1:
                new_name = matches[0]['name']
                new_path = "./" + new_name
                if new_path != old_path:
                    if log_func:
                        log_func(f"  更新: {old_path} -> {new_path}")
                    path_elem.text = new_path
                    updated_count += 1
                else:
                    if log_func:
                        log_func(f"  无需更新: {old_path} (已匹配)")
            else:
                if log_func:
                    log_func(f"  多个匹配: {old_stem} -> {[m['name'] for m in matches]}")
                best = None
                for m in matches:
                    if m['ext'] != '.md' and (best is None or m['ext'] == '.smd'):
                        best = m
                if best is None:
                    best = matches[0]
                new_name = best['name']
                new_path = "./" + new_name
                if new_path != old_path:
                    if log_func:
                        log_func(f"  选择最佳匹配: {old_path} -> {new_path} ({len(matches)} 个匹配)")
                    path_elem.text = new_path
                    updated_count += 1
                else:
                    if log_func:
                        log_func(f"  无需更新: {old_path}")
        elif old_stem in subfolders:
            new_path = "./" + old_stem + "/"
            if new_path != old_path:
                if log_func:
                    log_func(f"  更新为子文件夹: {old_path} -> {new_path}")
                path_elem.text = new_path
                updated_count += 1
                subfolder_count += 1
            else:
                if log_func:
                    log_func(f"  无需更新: {old_path} (已是子文件夹)")
        else:
            not_found_count += 1
            if log_func:
                log_func(f"  未找到匹配: {old_path} (基准名: {old_stem})")

    rough_str = ET.tostring(root, encoding='utf-8', method='xml')
    parsed = minidom.parseString(rough_str)
    pretty_xml = parsed.toprettyxml(indent="    ", encoding='utf-8')
    xml_str = pretty_xml.decode('utf-8')

    xml_str = xml_str.replace('<?xml version="1.0" encoding="utf-8"?>',
                              "<?xml version='1.0' encoding='utf-8'?>")

    lines = xml_str.split('\n')
    cleaned_lines = []
    for line in lines:
        if line.strip() == '':
            continue
        cleaned_lines.append(line)
    xml_str = '\n'.join(cleaned_lines)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    if log_func:
        log_func(f"\n{'='*50}")
        log_func(f"更新完成!")
        log_func(f"  更新路径: {updated_count}")
        log_func(f"  子文件夹匹配: {subfolder_count}")
        log_func(f"  未找到匹配: {not_found_count}")
        log_func(f"  输出文件: {output_path}")

    return True


class UpdatePathsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("gamelist.xml 路径更新器")
        self.root.geometry("650x550")
        self.root.minsize(600, 500)

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 5}

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, **pad)

        gamelist_frame = ttk.LabelFrame(main_frame, text="gamelist.xml 文件")
        gamelist_frame.pack(fill=tk.X, **pad)

        ttk.Label(gamelist_frame, text="gamelist路径:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.gamelist_path_var = tk.StringVar()
        ttk.Entry(gamelist_frame, textvariable=self.gamelist_path_var, width=55).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(gamelist_frame, text="浏览...", command=self._browse_gamelist).grid(
            row=0, column=2, padx=5, pady=5)

        target_frame = ttk.LabelFrame(main_frame, text="实际文件目录")
        target_frame.pack(fill=tk.X, **pad)

        ttk.Label(target_frame, text="目标目录:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_dir_var = tk.StringVar()
        ttk.Entry(target_frame, textvariable=self.target_dir_var, width=55).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(target_frame, text="浏览...", command=self._browse_target).grid(
            row=0, column=2, padx=5, pady=5)

        ttk.Label(target_frame, text="(包含实际游戏文件的目录，用于匹配正确的扩展名)",
                  foreground='gray').grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

        output_frame = ttk.LabelFrame(main_frame, text="输出设置")
        output_frame.pack(fill=tk.X, **pad)

        self.output_same_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(output_frame, text="覆盖原 gamelist.xml (取消则另存为)",
                        variable=self.output_same_var).grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=5)

        ttk.Label(output_frame, text="输出路径:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.output_path_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_path_var, width=55).grid(
            row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(output_frame, text="浏览...", command=self._browse_output).grid(
            row=1, column=2, padx=5, pady=5)

        self.output_path_var.set("")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, **pad)

        ttk.Button(button_frame, text="开始更新", command=self._start_processing).pack(
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

        gamelist_frame.columnconfigure(1, weight=1)
        target_frame.columnconfigure(1, weight=1)
        output_frame.columnconfigure(1, weight=1)

    def _browse_gamelist(self):
        f = filedialog.askopenfilename(
            title="选择 gamelist.xml",
            filetypes=[("XML文件", "*.xml"), ("所有文件", "*.*")])
        if f:
            self.gamelist_path_var.set(f)
            if not self.output_path_var.get():
                self.output_path_var.set(f)

    def _browse_target(self):
        d = filedialog.askdirectory(title="选择包含实际游戏文件的目录")
        if d:
            self.target_dir_var.set(d)

    def _browse_output(self):
        f = filedialog.asksaveasfilename(
            title="保存 gamelist.xml",
            defaultextension=".xml",
            filetypes=[("XML文件", "*.xml")])
        if f:
            self.output_path_var.set(f)
            self.output_same_var.set(False)

    def _log(self, msg):
        self.log_text.insert(tk.END, msg + '\n')
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _clear_log(self):
        self.log_text.delete('1.0', tk.END)

    def _get_config(self):
        return {
            'gamelist_path': self.gamelist_path_var.get().strip(),
            'target_dir': self.target_dir_var.get().strip(),
            'output_same': self.output_same_var.get(),
            'output_path': self.output_path_var.get().strip(),
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
            self.gamelist_path_var.set(config.get('gamelist_path', ''))
            self.target_dir_var.set(config.get('target_dir', ''))
            self.output_same_var.set(config.get('output_same', True))
            self.output_path_var.set(config.get('output_path', ''))
            self._log(f"配置已加载: {CONFIG_FILE}")
        except Exception as e:
            self._log(f"加载配置失败: {str(e)}")

    def _start_processing(self):
        gamelist_path = self.gamelist_path_var.get().strip()
        target_dir = self.target_dir_var.get().strip()

        if not gamelist_path:
            messagebox.showwarning("警告", "请选择 gamelist.xml 文件！")
            return

        resolved = _resolve_gamelist_path(gamelist_path)
        if resolved is None:
            messagebox.showerror("错误", f"gamelist.xml 不存在: {gamelist_path}")
            return
        gamelist_path = resolved

        if not target_dir:
            messagebox.showwarning("警告", "请选择目标目录！")
            return
        if not os.path.isdir(target_dir):
            messagebox.showerror("错误", f"目标目录不存在: {target_dir}")
            return

        if self.output_same_var.get():
            output_path = gamelist_path
        else:
            output_path = self.output_path_var.get().strip()
            if not output_path:
                messagebox.showwarning("警告", "请选择输出路径！")
                return

        self._log("=" * 50)
        self._log("开始更新路径...")
        self._log(f"gamelist.xml: {gamelist_path}")
        self._log(f"目标目录: {target_dir}")
        self._log(f"输出路径: {output_path}")
        self._log("=" * 50)

        thread = threading.Thread(target=self._run_processing,
                                  args=(gamelist_path, target_dir, output_path), daemon=True)
        thread.start()

    def _run_processing(self, gamelist_path, target_dir, output_path):
        try:
            update_gamelist_paths(gamelist_path, target_dir, output_path, log_func=self._log)
        except Exception as e:
            self._log(f"\n处理异常: {str(e)}")
            import traceback
            self._log(traceback.format_exc())


def main():
    root = tk.Tk()
    app = UpdatePathsApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()