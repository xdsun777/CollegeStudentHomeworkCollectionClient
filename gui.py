#!/usr/bin/env python3
"""
网盘作业管理工具 - 图形界面
依赖：python-dotenv, requests, openpyxl, tkinter (内置)
使用方法：python gui.py
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from dotenv import load_dotenv, set_key
import main  # 导入主脚本（需在同一目录）

class RedirectText:
    """将 print 输出重定向到 GUI 文本框"""
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.update_idletasks()

    def flush(self):
        pass

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("网盘作业管理工具")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        # 加载配置
        self.config = self.load_config()

        # 创建界面
        self.create_widgets()

        # 绑定关闭事件，恢复标准输出
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        """加载 .env 配置"""
        dotenv_path = Path('.env')
        if dotenv_path.exists():
            load_dotenv(dotenv_path)
            return {
                'WORKDIR': os.getenv('WORKDIR', ''),
                'BASE_URL': os.getenv('BASE_URL', ''),
                'USER': os.getenv('USER', ''),
                'PASSWD': os.getenv('PASSWD', '')
            }
        return {'WORKDIR': '', 'BASE_URL': '', 'USER': '', 'PASSWD': ''}

    def save_config(self):
        """保存配置到 .env"""
        dotenv_path = Path('.env')
        # 确保目录存在
        if not dotenv_path.parent.exists():
            dotenv_path.parent.mkdir(parents=True, exist_ok=True)
        # 写入配置
        set_key(dotenv_path, 'WORKDIR', self.workdir_var.get())
        set_key(dotenv_path, 'BASE_URL', self.base_url_var.get())
        set_key(dotenv_path, 'USER', self.user_var.get())
        set_key(dotenv_path, 'PASSWD', self.passwd_var.get())
        # 重新加载环境变量
        load_dotenv(dotenv_path, override=True)
        # 更新主脚本中的全局变量
        main.WORKDIR = Path(self.workdir_var.get())
        main.BASE_URL = self.base_url_var.get().rstrip('/')
        main.USER = self.user_var.get()
        main.PASSWD = self.passwd_var.get()
        messagebox.showinfo("提示", "配置已保存")

    def create_widgets(self):
        # 使用 Notebook 分页
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 配置页
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="配置")

        # 功能页
        func_frame = ttk.Frame(notebook)
        notebook.add(func_frame, text="功能")

        # 日志页
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="日志")

        # ---------- 配置页 ----------
        # 创建标签和输入框
        ttk.Label(config_frame, text="本地工作目录 (WORKDIR):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.workdir_var = tk.StringVar(value=self.config['WORKDIR'])
        workdir_entry = ttk.Entry(config_frame, textvariable=self.workdir_var, width=50)
        workdir_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="浏览", command=self.browse_workdir).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(config_frame, text="网盘地址 (BASE_URL):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.base_url_var = tk.StringVar(value=self.config['BASE_URL'])
        ttk.Entry(config_frame, textvariable=self.base_url_var, width=50).grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="用户名 (USER):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.user_var = tk.StringVar(value=self.config['USER'])
        ttk.Entry(config_frame, textvariable=self.user_var, width=50).grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="密码 (PASSWD):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.passwd_var = tk.StringVar(value=self.config['PASSWD'])
        ttk.Entry(config_frame, textvariable=self.passwd_var, width=50, show="*").grid(row=3, column=1, padx=5, pady=5)

        ttk.Button(config_frame, text="保存配置", command=self.save_config).grid(row=4, column=1, pady=10)

        # ---------- 功能页 ----------
        # 功能选择
        ttk.Label(func_frame, text="选择功能:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.func_var = tk.StringVar()
        func_combo = ttk.Combobox(func_frame, textvariable=self.func_var, values=[
            "全量同步", "打包作业", "生成报告", "创建作业文件夹", "删除作业文件夹"
        ], state="readonly")
        func_combo.grid(row=0, column=1, padx=5, pady=5)
        func_combo.bind("<<ComboboxSelected>>", self.on_func_selected)

        # 参数区域
        self.param_frame = ttk.LabelFrame(func_frame, text="参数设置")
        self.param_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W+tk.E, padx=5, pady=10)

        # 默认参数输入控件（会在选中功能时动态显示）
        self.course_var = tk.StringVar()
        self.assignment_var = tk.StringVar()
        self.target_zip_var = tk.StringVar()
        self.target_report_var = tk.StringVar()
        self.force_var = tk.BooleanVar()

        # 占位，稍后动态布局
        self.param_widgets = {}

        # 执行按钮
        self.run_btn = ttk.Button(func_frame, text="执行", command=self.run_task)
        self.run_btn.grid(row=2, column=1, pady=10)

        # ---------- 日志页 ----------
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 重定向 stdout
        sys.stdout = RedirectText(self.log_text)

    def on_func_selected(self, event):
        """根据选择的功能显示不同的参数输入框"""
        # 清除原有控件
        for widget in self.param_frame.winfo_children():
            widget.destroy()

        func = self.func_var.get()
        if func == "全量同步":
            # 只有 force 选项
            ttk.Checkbutton(self.param_frame, text="强制覆盖已存在文件", variable=self.force_var).pack(anchor=tk.W, padx=5, pady=5)

        elif func == "打包作业":
            # 科目、作业名、输出zip路径、force
            ttk.Label(self.param_frame, text="科目:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(self.param_frame, textvariable=self.course_var, width=30).grid(row=0, column=1, padx=5, pady=5)

            ttk.Label(self.param_frame, text="作业:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(self.param_frame, textvariable=self.assignment_var, width=30).grid(row=1, column=1, padx=5, pady=5)

            ttk.Label(self.param_frame, text="输出ZIP文件:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            zip_entry = ttk.Entry(self.param_frame, textvariable=self.target_zip_var, width=30)
            zip_entry.grid(row=2, column=1, padx=5, pady=5)
            ttk.Button(self.param_frame, text="浏览", command=self.browse_zip).grid(row=2, column=2, padx=5, pady=5)

            ttk.Checkbutton(self.param_frame, text="强制覆盖已存在文件", variable=self.force_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        elif func == "生成报告":
            # 输出excel路径
            ttk.Label(self.param_frame, text="输出Excel文件:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            report_entry = ttk.Entry(self.param_frame, textvariable=self.target_report_var, width=30)
            report_entry.grid(row=0, column=1, padx=5, pady=5)
            ttk.Button(self.param_frame, text="浏览", command=self.browse_report).grid(row=0, column=2, padx=5, pady=5)

        elif func == "创建作业文件夹":
            # 科目、作业名
            ttk.Label(self.param_frame, text="科目:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(self.param_frame, textvariable=self.course_var, width=30).grid(row=0, column=1, padx=5, pady=5)

            ttk.Label(self.param_frame, text="作业:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(self.param_frame, textvariable=self.assignment_var, width=30).grid(row=1, column=1, padx=5, pady=5)

        elif func == "删除作业文件夹":
            # 科目、作业名，带确认
            ttk.Label(self.param_frame, text="科目:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(self.param_frame, textvariable=self.course_var, width=30).grid(row=0, column=1, padx=5, pady=5)

            ttk.Label(self.param_frame, text="作业:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            ttk.Entry(self.param_frame, textvariable=self.assignment_var, width=30).grid(row=1, column=1, padx=5, pady=5)

    def browse_workdir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.workdir_var.set(directory)

    def browse_zip(self):
        file = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP files", "*.zip")])
        if file:
            self.target_zip_var.set(file)

    def browse_report(self):
        file = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file:
            self.target_report_var.set(file)

    def run_task(self):
        """在后台线程执行任务，避免界面卡死"""
        func = self.func_var.get()
        if not func:
            messagebox.showwarning("提示", "请选择功能")
            return

        # 检查配置是否完整
        if not self.workdir_var.get():
            messagebox.showerror("错误", "请先设置本地工作目录")
            return
        if not self.base_url_var.get():
            messagebox.showerror("错误", "请先设置网盘地址")
            return
        if not self.user_var.get() or not self.passwd_var.get():
            messagebox.showerror("错误", "请先设置用户名和密码")
            return

        # 保存配置（确保最新）
        self.save_config()

        # 禁用执行按钮，防止重复点击
        self.run_btn.config(state=tk.DISABLED)
        self.log_text.delete(1.0, tk.END)

        # 启动线程
        thread = threading.Thread(target=self._run_task, args=(func,))
        thread.daemon = True
        thread.start()

    def _run_task(self, func):
        try:
            if func == "全量同步":
                force = self.force_var.get()
                main.sync_all(force=force)
            elif func == "打包作业":
                course = self.course_var.get().strip()
                assignment = self.assignment_var.get().strip()
                output_zip = self.target_zip_var.get().strip()
                if not course or not assignment or not output_zip:
                    self.show_error("科目、作业名和输出文件不能为空")
                    return
                force = self.force_var.get()
                main.zip_assignment(course, assignment, Path(output_zip), force)
            elif func == "生成报告":
                output_excel = self.target_report_var.get().strip()
                if not output_excel:
                    self.show_error("输出文件不能为空")
                    return
                main.generate_report(Path(output_excel))
            elif func == "创建作业文件夹":
                course = self.course_var.get().strip()
                assignment = self.assignment_var.get().strip()
                if not course or not assignment:
                    self.show_error("科目和作业名不能为空")
                    return
                main.new_assignment(course, assignment)
            elif func == "删除作业文件夹":
                course = self.course_var.get().strip()
                assignment = self.assignment_var.get().strip()
                if not course or not assignment:
                    self.show_error("科目和作业名不能为空")
                    return
                # 删除功能需要确认，但已在函数内部处理
                main.delete_assignment(course, assignment, yes=False)
            else:
                self.show_error("未知功能")
        except Exception as e:
            self.show_error(f"执行出错: {e}")
        finally:
            # 恢复按钮
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))

    def show_error(self, msg):
        self.root.after(0, lambda: messagebox.showerror("错误", msg))

    def on_close(self):
        """关闭窗口时恢复标准输出"""
        sys.stdout = sys.__stdout__
        self.root.destroy()

def main_gui():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main_gui()