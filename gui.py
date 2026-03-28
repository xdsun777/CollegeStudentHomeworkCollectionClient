#!/usr/bin/env python3
"""
网盘作业管理工具 - 图形界面（优先使用本地数据，网盘数据需手动刷新）
修正目录结构：WORKDIR/学生/学科/作业/
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
import requests
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
        self.root.geometry("850x700")
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
                'PASSWD': os.getenv('PASSWD', ''),
                'REPORT_PATH': os.getenv('REPORT_PATH', '')
            }
        return {'WORKDIR': '', 'BASE_URL': '', 'USER': '', 'PASSWD': '', 'REPORT_PATH': ''}

    def save_config(self):
        """保存配置到 .env 并更新 main 全局变量"""
        dotenv_path = Path('.env')
        if not dotenv_path.parent.exists():
            dotenv_path.parent.mkdir(parents=True, exist_ok=True)
        set_key(dotenv_path, 'WORKDIR', self.workdir_var.get())
        set_key(dotenv_path, 'BASE_URL', self.base_url_var.get())
        set_key(dotenv_path, 'USER', self.user_var.get())
        set_key(dotenv_path, 'PASSWD', self.passwd_var.get())
        set_key(dotenv_path, 'REPORT_PATH', self.report_path_var.get())  # 新增

        load_dotenv(dotenv_path, override=True)
        # 更新主脚本中的全局变量
        self._apply_config_to_main()
        messagebox.showinfo("提示", "配置已保存")

    def _apply_config_to_main(self):
        """将当前界面配置应用到 main 模块的全局变量（不写入文件）"""
        workdir = self.workdir_var.get().strip()
        base_url = self.base_url_var.get().strip().rstrip('/')
        user = self.user_var.get().strip()
        passwd = self.passwd_var.get().strip()
        if workdir:
            main.WORKDIR = Path(workdir)
        if base_url:
            main.BASE_URL = base_url
        if user:
            main.USER = user
        if passwd:
            main.PASSWD = passwd

    def apply_config(self):
        """应用当前界面配置到 main 模块，并检查完整性"""
        workdir = self.workdir_var.get().strip()
        base_url = self.base_url_var.get().strip()
        user = self.user_var.get().strip()
        passwd = self.passwd_var.get().strip()
        if not workdir:
            messagebox.showerror("错误", "请先设置本地工作目录")
            return False
        if not base_url:
            messagebox.showerror("错误", "请先设置网盘地址")
            return False
        if not user or not passwd:
            messagebox.showerror("错误", "请先设置用户名和密码")
            return False
        self._apply_config_to_main()
        return True

    def test_connection(self):
        """测试网盘连接"""
        base_url = self.base_url_var.get().strip().rstrip('/')
        user = self.user_var.get().strip()
        passwd = self.passwd_var.get().strip()
        if not base_url or not user or not passwd:
            messagebox.showwarning("警告", "请先填写完整配置")
            return
        try:
            resp = requests.get(f"{base_url}/?json", auth=(user, passwd), timeout=10)
            if resp.status_code == 200:
                messagebox.showinfo("成功", "连接成功，认证通过")
            else:
                messagebox.showerror("失败", f"连接失败，状态码: {resp.status_code}")
        except Exception as e:
            messagebox.showerror("错误", f"连接异常: {e}")

    def create_widgets(self):
        # 使用 Notebook 分页
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 配置页
        config_frame = ttk.Frame(notebook)
        notebook.add(config_frame, text="配置")

        # 功能页（带滚动条）
        func_container = ttk.Frame(notebook)
        notebook.add(func_container, text="功能")
        func_canvas = tk.Canvas(func_container)
        func_scrollbar = ttk.Scrollbar(func_container, orient="vertical", command=func_canvas.yview)
        self.func_frame = ttk.Frame(func_canvas)
        self.func_frame.bind("<Configure>", lambda e: func_canvas.configure(scrollregion=func_canvas.bbox("all")))
        func_canvas.create_window((0, 0), window=self.func_frame, anchor="nw")
        func_canvas.configure(yscrollcommand=func_scrollbar.set)
        func_canvas.pack(side="left", fill="both", expand=True)
        func_scrollbar.pack(side="right", fill="y")

        # 日志页
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="日志")

        # ---------- 配置页 ----------
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

        ttk.Label(config_frame, text="默认报告输出文件:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.report_path_var = tk.StringVar(value=self.config.get('REPORT_PATH', ''))
        report_entry = ttk.Entry(config_frame, textvariable=self.report_path_var, width=50)
        report_entry.grid(row=4, column=1, padx=5, pady=5)
        ttk.Button(config_frame, text="浏览", command=self.browse_default_report).grid(row=4, column=2, padx=5, pady=5)


        btn_frame = ttk.Frame(config_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=10)
        ttk.Button(btn_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="测试连接", command=self.test_connection).pack(side=tk.LEFT, padx=5)
        # ---------- 功能页 ----------
        # 功能选择
        ttk.Label(self.func_frame, text="选择功能:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.func_var = tk.StringVar()
        func_combo = ttk.Combobox(self.func_frame, textvariable=self.func_var, values=[
            "全量同步", "同步学科/作业", "打包作业", "生成报告", "创建作业文件夹", "删除作业文件夹"
        ], state="readonly")
        func_combo.grid(row=0, column=1, padx=5, pady=5)
        func_combo.bind("<<ComboboxSelected>>", self.on_func_selected)

        # 参数区域
        self.param_frame = ttk.LabelFrame(self.func_frame, text="参数设置")
        self.param_frame.grid(row=1, column=0, columnspan=3, sticky=tk.W+tk.E, padx=5, pady=10)

        # 动态参数控件引用
        self.param_widgets = {}
        self.course_combo = None
        self.assignment_combo = None
        self.force_var = tk.BooleanVar()
        self.target_zip_var = tk.StringVar()
        self.target_report_var = tk.StringVar()

        # 状态标签（用于显示加载中）
        self.status_label = ttk.Label(self.func_frame, text="", foreground="gray")
        self.status_label.grid(row=2, column=0, columnspan=3, pady=5)

        # 执行按钮
        self.run_btn = ttk.Button(self.func_frame, text="执行", command=self.run_task)
        self.run_btn.grid(row=3, column=1, pady=10)

        # ---------- 日志页 ----------
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=20)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        sys.stdout = RedirectText(self.log_text)



    def browse_default_report(self):
        """浏览选择默认报告输出文件"""
        file = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if file:
            self.report_path_var.set(file)
    # ---------- 本地数据获取（修正目录结构）----------
    def _get_student_dirs(self):
        """获取工作目录下所有学生目录"""
        workdir = self.workdir_var.get().strip()
        if not workdir:
            return []
        workdir_path = Path(workdir)
        if not workdir_path.exists() or not workdir_path.is_dir():
            return []
        return [d for d in workdir_path.iterdir() if d.is_dir()]

    def _get_local_courses(self):
        """从本地获取所有学科（去重）：遍历所有学生目录下的子目录名"""
        courses = set()
        for student_dir in self._get_student_dirs():
            for item in student_dir.iterdir():
                if item.is_dir():
                    courses.add(item.name)
        return sorted(courses)

    def _get_local_assignments(self, course):
        """从本地获取指定学科下的所有作业（去重）：遍历所有学生目录下该学科目录的子目录名"""
        if not course:
            return []
        assignments = set()
        for student_dir in self._get_student_dirs():
            course_dir = student_dir / course
            if course_dir.exists() and course_dir.is_dir():
                for item in course_dir.iterdir():
                    if item.is_dir():
                        assignments.add(item.name)
        return sorted(assignments)

    def load_local_courses(self, target_combo=None):
        """将本地学科列表加载到指定的 Combobox 中（默认 self.course_combo）"""
        if target_combo is None:
            target_combo = self.course_combo
        if target_combo:
            courses = self._get_local_courses()
            target_combo.config(values=courses)
            if courses:
                # 如果当前选中值不在列表中，清空选中
                if target_combo.get() not in courses:
                    target_combo.set('')
            else:
                target_combo.set('')
                self._set_status("本地工作目录下没有找到任何学科", error=True)

    def load_local_assignments(self, target_combo=None):
        """根据当前选中的科目，加载本地作业列表到指定的 Combobox 中（默认 self.assignment_combo）"""
        if target_combo is None:
            target_combo = self.assignment_combo
        if target_combo and self.course_combo:
            course = self.course_combo.get().strip()
            if course:
                assignments = self._get_local_assignments(course)
                target_combo.config(values=assignments)
                if target_combo.get() not in assignments:
                    target_combo.set('')
            else:
                target_combo.config(values=[])
                target_combo.set('')

    # ---------- 网盘数据获取（仅用于刷新）----------
    def get_courses_from_remote(self):
        """从网盘获取所有科目（去重）"""
        auth = (self.user_var.get().strip(), self.passwd_var.get().strip())
        base_url = self.base_url_var.get().strip().rstrip('/')
        if not base_url or not auth[0] or not auth[1]:
            return []
        try:
            # 获取根目录所有学生
            resp = requests.get(f"{base_url}/?json", auth=auth, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            students = [p['name'] for p in data.get('paths', []) if p['path_type'] == 'Dir' and main.is_student_dir(p['name'])]
            courses = set()
            for student in students:
                url = f"{base_url}/{student}/?json"
                try:
                    resp2 = requests.get(url, auth=auth, timeout=5)
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        for item in data2.get('paths', []):
                            if item['path_type'] == 'Dir':
                                courses.add(item['name'])
                except:
                    continue
            return sorted(courses)
        except Exception as e:
            print(f"获取科目列表失败: {e}")
            return []

    def get_assignments_from_remote(self, course):
        """获取指定科目下的所有作业（去重）"""
        if not course:
            return []
        auth = (self.user_var.get().strip(), self.passwd_var.get().strip())
        base_url = self.base_url_var.get().strip().rstrip('/')
        if not base_url or not auth[0] or not auth[1]:
            return []
        try:
            resp = requests.get(f"{base_url}/?json", auth=auth, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            students = [p['name'] for p in data.get('paths', []) if p['path_type'] == 'Dir' and main.is_student_dir(p['name'])]
            assignments = set()
            for student in students:
                url = f"{base_url}/{student}/{course}/?json"
                try:
                    resp2 = requests.get(url, auth=auth, timeout=5)
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        for item in data2.get('paths', []):
                            if item['path_type'] == 'Dir':
                                assignments.add(item['name'])
                except:
                    continue
            return sorted(assignments)
        except Exception as e:
            print(f"获取作业列表失败: {e}")
            return []

    def refresh_courses_from_remote(self):
        """从网盘刷新科目列表（后台线程）"""
        self._set_status("正在从网盘加载科目列表...")
        def _refresh():
            courses = self.get_courses_from_remote()
            self.root.after(0, lambda: self._set_status(""))
            if courses:
                self.root.after(0, lambda: self.course_combo.config(values=courses))
                if self.course_combo.get() not in courses:
                    self.root.after(0, lambda: self.course_combo.set(''))
            else:
                self.root.after(0, lambda: self._set_status("未从网盘找到任何科目，请检查连接和认证", error=True))
        threading.Thread(target=_refresh, daemon=True).start()

    def refresh_assignments_from_remote(self):
        """从网盘刷新作业列表（后台线程）"""
        course = self.course_combo.get() if self.course_combo else ""
        if not course:
            self._set_status("请先选择科目", error=True)
            return
        self._set_status(f"正在从网盘加载科目 '{course}' 下的作业列表...")
        def _refresh():
            assignments = self.get_assignments_from_remote(course)
            self.root.after(0, lambda: self._set_status(""))
            if assignments:
                self.root.after(0, lambda: self.assignment_combo.config(values=assignments))
                if self.assignment_combo.get() not in assignments:
                    self.root.after(0, lambda: self.assignment_combo.set(''))
            else:
                self.root.after(0, lambda: self._set_status(f"科目 '{course}' 下未从网盘找到任何作业", error=True))
        threading.Thread(target=_refresh, daemon=True).start()

    def on_course_selected(self, event):
        """科目选择后自动加载本地作业列表"""
        self.load_local_assignments()

    # ---------- 网盘选择窗口（创建作业文件夹用）----------
    def select_course_from_remote(self):
        """打开一个简单选择窗口选择科目（从网盘获取）"""
        self._set_status("正在从网盘获取科目列表...")
        def _get():
            courses = self.get_courses_from_remote()
            self.root.after(0, lambda: self._set_status(""))
            if not courses:
                self.root.after(0, lambda: messagebox.showinfo("提示", "未从网盘找到任何科目"))
                return
            self.root.after(0, lambda: self._select_from_list(courses, self.course_combo, "选择科目"))
        threading.Thread(target=_get, daemon=True).start()

    def select_assignment_from_remote(self):
        """打开一个简单选择窗口选择作业（从网盘获取）"""
        course = self.course_combo.get() if self.course_combo else ""
        if not course:
            messagebox.showinfo("提示", "请先选择或输入科目")
            return
        self._set_status(f"正在从网盘获取科目 '{course}' 下的作业列表...")
        def _get():
            assignments = self.get_assignments_from_remote(course)
            self.root.after(0, lambda: self._set_status(""))
            if not assignments:
                self.root.after(0, lambda: messagebox.showinfo("提示", f"科目 '{course}' 下未从网盘找到任何作业"))
                return
            self.root.after(0, lambda: self._select_from_list(assignments, self.assignment_combo, "选择作业"))
        threading.Thread(target=_get, daemon=True).start()

    def _select_from_list(self, items, target_combo, title):
        """通用列表选择窗口"""
        top = tk.Toplevel(self.root)
        top.title(title)
        top.geometry("300x400")
        listbox = tk.Listbox(top)
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        for item in items:
            listbox.insert(tk.END, item)
        def on_select():
            selection = listbox.curselection()
            if selection:
                target_combo.delete(0, tk.END)
                target_combo.insert(0, listbox.get(selection[0]))
            top.destroy()
        ttk.Button(top, text="确定", command=on_select).pack(pady=5)

    def _set_status(self, msg, error=False):
        """设置状态标签文本，error 为 True 时显示红色"""
        if error:
            self.status_label.config(text=msg, foreground="red")
        else:
            self.status_label.config(text=msg, foreground="gray")
        if error and msg:
            self.root.after(5000, lambda: self.status_label.config(text="", foreground="gray"))

    # ---------- 浏览文件/目录 ----------
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

    # ---------- 功能界面构建 ----------
    def on_func_selected(self, event):
        """根据选择的功能动态构建参数输入区域"""
        # 清除原有控件
        for widget in self.param_frame.winfo_children():
            widget.destroy()

        func = self.func_var.get()

        if func == "全量同步":
            ttk.Checkbutton(self.param_frame, text="强制覆盖已存在文件", variable=self.force_var).pack(anchor=tk.W, padx=5, pady=5)

        elif func == "打包作业":
            self._add_course_assignment_selectors()
            # 输出ZIP
            ttk.Label(self.param_frame, text="输出ZIP文件:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
            zip_entry = ttk.Entry(self.param_frame, textvariable=self.target_zip_var, width=30)
            zip_entry.grid(row=2, column=1, padx=5, pady=5)
            ttk.Button(self.param_frame, text="浏览", command=self.browse_zip).grid(row=2, column=2, padx=5, pady=5)

            ttk.Checkbutton(self.param_frame, text="强制覆盖已存在文件", variable=self.force_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

            # 初始加载本地数据
            self.load_local_courses()
            self.load_local_assignments()

        elif func == "生成报告":
            # ttk.Label(self.param_frame, text="输出Excel文件:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            # report_entry = ttk.Entry(self.param_frame, textvariable=self.target_report_var, width=30)
            # report_entry.grid(row=0, column=1, padx=5, pady=5)
            # ttk.Button(self.param_frame, text="浏览", command=self.browse_report).grid(row=0, column=2, padx=5, pady=5)
            ttk.Label(self.param_frame, text="输出Excel文件:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            report_entry = ttk.Entry(self.param_frame, textvariable=self.target_report_var, width=30)
            report_entry.grid(row=0, column=1, padx=5, pady=5)
            ttk.Button(self.param_frame, text="浏览", command=self.browse_report).grid(row=0, column=2, padx=5, pady=5)

            # 将默认路径填充到输出文件输入框
            default_report = self.report_path_var.get().strip()
            if default_report:
                self.target_report_var.set(default_report)

        elif func == "创建作业文件夹":
            # 科目输入框（可编辑，带本地下拉建议）
            ttk.Label(self.param_frame, text="科目:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
            self.course_combo = ttk.Combobox(self.param_frame, width=30)
            self.course_combo.grid(row=0, column=1, padx=5, pady=5)
            ttk.Button(self.param_frame, text="从网盘选择", command=self.select_course_from_remote).grid(row=0, column=2, padx=5, pady=5)

            # 作业输入框（可编辑，带本地下拉建议）
            ttk.Label(self.param_frame, text="作业:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
            self.assignment_combo = ttk.Combobox(self.param_frame, width=30)
            self.assignment_combo.grid(row=1, column=1, padx=5, pady=5)
            ttk.Button(self.param_frame, text="从网盘选择", command=self.select_assignment_from_remote).grid(row=1, column=2, padx=5, pady=5)

            ttk.Label(self.param_frame, text="提示: 可直接输入新名称，或点击按钮从网盘选择已有目录作为参考", foreground="gray").grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

            # 初始加载本地下拉建议
            self.load_local_courses()
            # 绑定科目变化事件，更新作业下拉建议
            self.course_combo.bind("<<ComboboxSelected>>", self.on_course_selected)

        elif func == "删除作业文件夹":
            self._add_course_assignment_selectors(readonly=True)
            # 初始加载本地数据
            self.load_local_courses()
            self.load_local_assignments()

        elif func == "同步学科/作业":
            self._add_course_assignment_selectors(assignment_optional=True)
            ttk.Checkbutton(self.param_frame, text="强制覆盖已存在文件", variable=self.force_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            # 初始加载本地数据
            self.load_local_courses()
            self.load_local_assignments()

    def _add_course_assignment_selectors(self, readonly=False, assignment_optional=False):
        """添加科目和作业选择控件（公共部分）"""
        # 科目
        ttk.Label(self.param_frame, text="科目:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.course_combo = ttk.Combobox(self.param_frame, width=30, state="readonly" if readonly else "normal")
        self.course_combo.grid(row=0, column=1, padx=5, pady=5)
        # 刷新按钮（网盘刷新）
        ttk.Button(self.param_frame, text="刷新科目", command=self.refresh_courses_from_remote).grid(row=0, column=2, padx=5, pady=5)
        self.course_combo.bind("<<ComboboxSelected>>", self.on_course_selected)

        # 作业
        ttk.Label(self.param_frame, text="作业:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.assignment_combo = ttk.Combobox(self.param_frame, width=30, state="readonly" if readonly else "normal")
        self.assignment_combo.grid(row=1, column=1, padx=5, pady=5)
        # 刷新按钮（网盘刷新）
        ttk.Button(self.param_frame, text="刷新作业", command=self.refresh_assignments_from_remote).grid(row=1, column=2, padx=5, pady=5)
        if assignment_optional:
            ttk.Label(self.param_frame, text="提示: 作业可选，留空则同步该学科下所有作业", foreground="gray").grid(row=2, column=0, columnspan=3, sticky=tk.W, padx=5, pady=2)

    # ---------- 任务执行 ----------
    def run_task(self):
        """执行选中的功能（先应用临时配置，不保存到文件）"""
        func = self.func_var.get()
        if not func:
            messagebox.showwarning("提示", "请选择功能")
            return

        # 应用当前界面配置到 main 模块（不保存文件）
        if not self.apply_config():
            return

        # 禁用执行按钮
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
                course = self.course_combo.get().strip()
                assignment = self.assignment_combo.get().strip()
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
                course = self.course_combo.get().strip()
                assignment = self.assignment_combo.get().strip()
                if not course or not assignment:
                    self.show_error("科目和作业名不能为空")
                    return
                main.new_assignment(course, assignment)

            elif func == "删除作业文件夹":
                course = self.course_combo.get().strip()
                assignment = self.assignment_combo.get().strip()
                if not course or not assignment:
                    self.show_error("科目和作业名不能为空")
                    return
                # 删除功能内部有确认
                main.delete_assignment(course, assignment, yes=False)

            elif func == "同步学科/作业":
                course = self.course_combo.get().strip()
                if not course:
                    self.show_error("学科不能为空")
                    return
                assignment = self.assignment_combo.get().strip() if self.assignment_combo else None
                force = self.force_var.get()
                main.sync_assignment(course, assignment, force)

            else:
                self.show_error("未知功能")
        except Exception as e:
            self.show_error(f"执行出错: {e}")
        finally:
            self.root.after(0, lambda: self.run_btn.config(state=tk.NORMAL))

    def show_error(self, msg):
        self.root.after(0, lambda: messagebox.showerror("错误", msg))

    def on_close(self):
        sys.stdout = sys.__stdout__
        self.root.destroy()

def main_gui():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == "__main__":
    main_gui()