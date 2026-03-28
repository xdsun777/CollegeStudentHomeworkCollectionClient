#!/usr/bin/env python3
"""
网盘作业管理工具
功能：
1. 全量同步网盘所有文件到本地 WORKDIR
2. 同步指定学科或学科下指定作业（每个学生）
3. 打包指定作业
4. 生成报告
5. 创建/删除作业文件夹
"""

import os
import sys
import argparse
import requests
import zipfile
import re
import base64
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

# 全局变量（默认值，命令行调用时使用）
_WORKDIR = Path(os.getenv('WORKDIR', ''))
_BASE_URL = os.getenv('BASE_URL', '').rstrip('/')
_USER = os.getenv('USER', '')
_PASSWD = os.getenv('PASSWD', '')

def encode_path(path: str) -> str:
    """对路径进行URL编码，保留斜杠"""
    if not path:
        return ''
    return '/'.join(quote(part, safe='') for part in path.split('/'))

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def is_student_dir(name: str) -> bool:
    return bool(re.match(r'^\d+-\w+$', name))

def list_remote_dir(remote_path: str, base_url=None, user=None, passwd=None):
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    auth = (user, passwd)
    url = f"{base_url}/{encode_path(remote_path)}".rstrip('/') + '/?json'
    try:
        resp = requests.get(url, auth=auth, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        entries = []
        for item in data.get('paths', []):
            name = item['name']
            entries.append({
                'name': name,
                'type': 'directory' if item['path_type'] == 'Dir' else 'file',
                'size': item.get('size', 0)
            })
        return entries
    except Exception as e:
        print(f"无法列出远程目录 {remote_path}: {e}")
        return []

def create_remote_dir(remote_path: str, base_url=None, user=None, passwd=None):
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    auth = (user, passwd)
    url = f"{base_url}/{encode_path(remote_path)}"
    try:
        resp = requests.request('MKCOL', url, auth=auth, timeout=10)
        if resp.status_code in (200, 201):
            return True
        elif resp.status_code == 409:
            return False
        else:
            print(f"  创建目录失败 {remote_path}: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  创建目录异常 {remote_path}: {e}")
        return False

def delete_remote(remote_path: str, base_url=None, user=None, passwd=None):
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    auth = (user, passwd)
    url = f"{base_url}/{encode_path(remote_path)}"
    try:
        resp = requests.delete(url, auth=auth, timeout=10)
        if resp.status_code in (200, 204):
            return True
        elif resp.status_code == 404:
            return False
        else:
            print(f"  删除失败 {remote_path}: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  删除异常 {remote_path}: {e}")
        return False

def download_file(remote_path: str, local_path: Path, force=False,
                  base_url=None, user=None, passwd=None):
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    auth = (user, passwd)
    if not force and local_path.exists():
        try:
            head = requests.head(f"{base_url}/{remote_path}", auth=auth, timeout=5)
            remote_size = int(head.headers.get('Content-Length', 0))
            if remote_size == local_path.stat().st_size:
                print(f"  已存在，跳过：{local_path}")
                return True
        except:
            pass
    url = f"{base_url}/{encode_path(remote_path)}"
    try:
        print(f"  下载: {url} -> {local_path}")
        resp = requests.get(url, auth=auth, stream=True, timeout=30)
        resp.raise_for_status()
        ensure_dir(local_path.parent)
        with open(local_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"  下载失败 {remote_path}: {e}")
        return False

def download_zip(remote_dir: str, local_dir: Path, force=False,
                 base_url=None, user=None, passwd=None):
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    auth = (user, passwd)
    if not force and local_dir.exists() and any(local_dir.iterdir()):
        print(f"  本地目录已存在且非空，跳过：{local_dir}")
        return True
    url = f"{base_url}/{remote_dir}?zip"
    try:
        print(f"  下载并解压: {url} -> {local_dir}")
        resp = requests.get(url, auth=auth, timeout=30)
        resp.raise_for_status()
        ensure_dir(local_dir)
        with zipfile.ZipFile(BytesIO(resp.content)) as zf:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                zf.extractall(tmp_path)
                extracted = list(tmp_path.iterdir())
                if len(extracted) == 1 and extracted[0].is_dir():
                    subdir = extracted[0]
                    for item in subdir.iterdir():
                        dest = local_dir / item.name
                        if dest.exists() and force:
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        shutil.move(item, dest)
                else:
                    for item in extracted:
                        dest = local_dir / item.name
                        if dest.exists() and force:
                            if dest.is_dir():
                                shutil.rmtree(dest)
                            else:
                                dest.unlink()
                        shutil.move(item, dest)
        return True
    except Exception as e:
        print(f"  下载失败 {remote_dir}: {e}")
        return False

def sync_all(force=False, workdir=None, base_url=None, user=None, passwd=None):
    """全量同步，返回统计信息字典"""
    if workdir is None:
        workdir = _WORKDIR
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    if not workdir:
        print("错误：未设置工作目录，无法执行全量同步。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}
    
    print(f"开始全量同步网盘到 {workdir}")
    stats = {'total': 0, 'success': 0, 'failed': 0, 'failures': []}

    def _sync_recursive(remote_path: str, local_path: Path):
        entries = list_remote_dir(remote_path, base_url, user, passwd)
        for entry in entries:
            name = entry['name']
            if entry['type'] == 'directory':
                new_remote = f"{remote_path}/{name}" if remote_path else name
                new_local = local_path / name
                ensure_dir(new_local)
                _sync_recursive(new_remote, new_local)
            else:
                stats['total'] += 1
                file_remote = f"{remote_path}/{name}" if remote_path else name
                file_local = local_path / name
                if download_file(file_remote, file_local, force, base_url, user, passwd):
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    stats['failures'].append(f"文件 {file_remote} -> {file_local}")

    _sync_recursive('', workdir)
    print("全量同步完成。")
    return stats

def sync_assignment(course: str, assignment: str = None, force=False,
                    workdir=None, base_url=None, user=None, passwd=None):
    """同步指定学科或作业，返回统计信息字典"""
    if workdir is None:
        workdir = _WORKDIR
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    if not workdir:
        print("错误：未设置工作目录。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}

    # 获取所有学生（优先本地，若本地无则从网盘获取）
    try:
        local_students = [d.name for d in workdir.iterdir() if d.is_dir() and is_student_dir(d.name)]
    except Exception as e:
        print(f"无法读取本地学生目录：{e}")
        local_students = []

    if not local_students:
        print("本地工作目录中未找到学生文件夹，将尝试从网盘获取学生列表。")
        remote_root = list_remote_dir('', base_url, user, passwd)
        remote_students = [e['name'] for e in remote_root if e['type'] == 'directory' and is_student_dir(e['name'])]
        if not remote_students:
            print("网盘根目录下也没有找到学生文件夹。")
            return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}
        students = remote_students
    else:
        students = local_students

    print(f"共 {len(students)} 个学生。")
    stats = {'total': len(students), 'success': 0, 'failed': 0, 'failures': []}

    for student in students:
        if assignment is None:
            remote_course_dir = f"{student}/{course}"
            local_course_dir = workdir / student / course
            if not force and local_course_dir.exists() and any(local_course_dir.iterdir()):
                print(f"  跳过 {student} 的 {course} 目录（已存在且非空）")
                stats['success'] += 1
                continue
            print(f"同步 {student} 的 {course} 目录...")
            if download_zip(remote_course_dir, local_course_dir, force, base_url, user, passwd):
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['failures'].append(f"{student}/{course}")
        else:
            remote_job_dir = f"{student}/{course}/{assignment}"
            local_job_dir = workdir / student / course / assignment
            if not force and local_job_dir.exists() and any(local_job_dir.iterdir()):
                print(f"  跳过 {student} 的 {course}/{assignment}（已存在且非空）")
                stats['success'] += 1
                continue
            print(f"同步 {student} 的 {course}/{assignment}...")
            if download_zip(remote_job_dir, local_job_dir, force, base_url, user, passwd):
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['failures'].append(f"{student}/{course}/{assignment}")

    print("同步完成。")
    return stats

def fetch_assignment(course: str, assignment: str, force=False,
                     workdir=None, base_url=None, user=None, passwd=None):
    """确保本地存在该作业，返回统计信息字典"""
    if workdir is None:
        workdir = _WORKDIR
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    if not workdir:
        print("错误：未设置工作目录。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}

    try:
        local_students = [d.name for d in workdir.iterdir() if d.is_dir() and is_student_dir(d.name)]
    except Exception as e:
        print(f"无法读取本地学生目录：{e}")
        local_students = []

    if not local_students:
        print("本地工作目录中未找到学生文件夹，将尝试从网盘获取学生列表。")
        remote_root = list_remote_dir('', base_url, user, passwd)
        remote_students = [e['name'] for e in remote_root if e['type'] == 'directory' and is_student_dir(e['name'])]
        if not remote_students:
            print("网盘根目录下也没有找到学生文件夹。")
            return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}
        students = remote_students
    else:
        students = local_students

    print(f"共 {len(students)} 个学生。")
    stats = {'total': len(students), 'success': 0, 'failed': 0, 'failures': []}

    for student in students:
        local_job_dir = workdir / student / course / assignment
        remote_job_dir = f"{student}/{course}/{assignment}"
        need_download = force
        if not need_download:
            if not local_job_dir.exists() or not any(local_job_dir.iterdir()):
                need_download = True
        if need_download:
            print(f"下载 {student} 的作业...")
            if download_zip(remote_job_dir, local_job_dir, force, base_url, user, passwd):
                stats['success'] += 1
            else:
                stats['failed'] += 1
                stats['failures'].append(f"{student}/{course}/{assignment}")
        else:
            print(f"  跳过 {student} 的 {course}/{assignment}（已存在且非空）")
            stats['success'] += 1

    return stats

def zip_assignment(course: str, assignment: str, output_zip: Path, force=False,
                   workdir=None, base_url=None, user=None, passwd=None):
    """打包作业，返回统计信息字典（打包过程中的统计）"""
    if workdir is None:
        workdir = _WORKDIR
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    if not workdir:
        print("错误：未设置工作目录。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}

    # 先确保所有学生都有该作业
    fetch_stats = fetch_assignment(course, assignment, force, workdir, base_url, user, passwd)

    students = []
    try:
        for d in workdir.iterdir():
            if d.is_dir() and is_student_dir(d.name):
                students.append(d)
    except Exception as e:
        print(f"无法读取本地学生目录：{e}")

    if not students:
        print("没有找到任何学生文件夹，无法打包。")
        return fetch_stats

    ensure_dir(output_zip.parent)
    packed_students = []
    skipped = []
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student_dir in students:
            student_name = student_dir.name
            job_dir = student_dir / course / assignment
            if not job_dir.exists() or not any(job_dir.iterdir()):
                print(f"跳过 {student_name}：无此作业")
                skipped.append(student_name)
                continue
            for file_path in job_dir.rglob('*'):
                if file_path.is_file():
                    rel_path = file_path.relative_to(job_dir)
                    arcname = f"{student_name}/{rel_path}"
                    zf.write(file_path, arcname)
            packed_students.append(student_name)
            print(f"已添加 {student_name} 的作业")

    print(f"打包完成：{output_zip}")
    # 返回打包统计
    pack_stats = {
        'total': len(students),
        'success': len(packed_students),
        'failed': len(skipped),
        'failures': [f"无作业: {s}" for s in skipped]
    }
    # 合并之前的 fetch 统计（可选择性显示）
    pack_stats['fetch_stats'] = fetch_stats
    return pack_stats

def generate_report(output_excel: Path, workdir=None):
    """生成报告，返回简单统计"""
    if workdir is None:
        workdir = _WORKDIR
    if not workdir:
        print("错误：未设置工作目录。")
        return {'success': False, 'error': '未设置工作目录'}

    student_data = {}
    courses = {}

    student_dirs = [d for d in workdir.iterdir() if d.is_dir() and is_student_dir(d.name)]
    if not student_dirs:
        print("没有找到任何学生文件夹，无法生成报告。")
        return {'success': False, 'error': '没有找到任何学生文件夹'}

    for student_dir in student_dirs:
        student_name = student_dir.name
        student_data[student_name] = {}
        for course_dir in student_dir.iterdir():
            if not course_dir.is_dir():
                continue
            course_name = course_dir.name
            student_data[student_name][course_name] = {}
            if course_name not in courses:
                courses[course_name] = set()
            for assignment_dir in course_dir.iterdir():
                if not assignment_dir.is_dir():
                    continue
                assignment_name = assignment_dir.name
                has_files = any(assignment_dir.iterdir())
                student_data[student_name][course_name][assignment_name] = has_files
                courses[course_name].add(assignment_name)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
    except ImportError:
        print("请安装 openpyxl: pip install openpyxl")
        return {'success': False, 'error': '缺少 openpyxl 库'}

    wb = Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)

    for course_name, assignments in sorted(courses.items()):
        if not assignments:
            continue
        ws = wb.create_sheet(title=course_name)
        headers = ["学号", "姓名"] + sorted(assignments)
        ws.append(headers)

        header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center")

        for student_name in sorted(student_data.keys()):
            parts = student_name.split('-', 1)
            student_id = parts[0] if len(parts) > 0 else ''
            student_real_name = parts[1] if len(parts) > 1 else ''
            row = [student_id, student_real_name]
            for assignment in sorted(assignments):
                completed = student_data.get(student_name, {}).get(course_name, {}).get(assignment, False)
                row.append("√" if completed else "")
            ws.append(row)

        for col in ws.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[col_letter].width = adjusted_width

    if not courses:
        ws = wb.create_sheet(title="无数据")
        ws.append(["提示"])
        ws.append(["未找到任何科目或作业文件夹"])

    ensure_dir(output_excel.parent)
    wb.save(output_excel)
    print(f"报告已生成：{output_excel}")
    return {'success': True, 'file': str(output_excel), 'course_count': len(courses)}

def new_assignment(course: str, assignment: str,
                   base_url=None, user=None, passwd=None):
    """创建作业文件夹，返回统计信息字典"""
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    print("正在获取学生列表...")
    remote_root = list_remote_dir('', base_url, user, passwd)
    students = [e['name'] for e in remote_root if e['type'] == 'directory' and is_student_dir(e['name'])]
    if not students:
        print("未找到任何学生文件夹。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}
    print(f"共 {len(students)} 个学生。")
    stats = {'total': len(students), 'success': 0, 'failed': 0, 'failures': []}
    for student in students:
        course_path = f"{student}/{course}"
        print(f"处理 {student}...")
        if not create_remote_dir(course_path, base_url, user, passwd):
            pass
        assignment_path = f"{course_path}/{assignment}"
        if create_remote_dir(assignment_path, base_url, user, passwd):
            print(f"  已创建: {assignment_path}")
            stats['success'] += 1
        else:
            print(f"  目录已存在或创建失败: {assignment_path}")
            stats['failed'] += 1
            stats['failures'].append(assignment_path)
    print("完成。")
    return stats

def delete_assignment(course: str, assignment: str, yes=False,
                      base_url=None, user=None, passwd=None):
    """删除作业文件夹，返回统计信息字典"""
    if base_url is None:
        base_url = _BASE_URL
    if user is None or passwd is None:
        user, passwd = _USER, _PASSWD
    print("正在获取学生列表...")
    remote_root = list_remote_dir('', base_url, user, passwd)
    students = [e['name'] for e in remote_root if e['type'] == 'directory' and is_student_dir(e['name'])]
    if not students:
        print("未找到任何学生文件夹。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}
    paths_to_delete = []
    for student in students:
        job_path = f"{student}/{course}/{assignment}"
        url = f"{base_url}/{job_path}"
        try:
            resp = requests.head(url, auth=(user, passwd), timeout=5)
            if resp.status_code == 200:
                paths_to_delete.append(job_path)
        except:
            pass
    if not paths_to_delete:
        print("没有找到任何要删除的作业文件夹。")
        return {'total': 0, 'success': 0, 'failed': 0, 'failures': []}
    print(f"将删除以下 {len(paths_to_delete)} 个作业文件夹：")
    for p in paths_to_delete:
        print(f"  {p}")
    if not yes:
        confirm = input("确认删除以上所有文件夹及其内容？(y/N): ").strip().lower()
        if confirm not in ('y', 'yes'):
            print("取消删除。")
            return {'total': len(paths_to_delete), 'success': 0, 'failed': 0, 'failures': [], 'cancelled': True}
    print("开始删除...")
    stats = {'total': len(paths_to_delete), 'success': 0, 'failed': 0, 'failures': []}
    for p in paths_to_delete:
        if delete_remote(p, base_url, user, passwd):
            print(f"  已删除: {p}")
            stats['success'] += 1
        else:
            print(f"  删除失败: {p}")
            stats['failed'] += 1
            stats['failures'].append(p)
    print("删除完成。")
    return stats

def main():
    parser = argparse.ArgumentParser(description="网盘作业管理工具")
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    sync_parser = subparsers.add_parser('sync', help='同步网盘到本地')
    sync_parser.add_argument('--force', '-f', action='store_true', help='强制覆盖已存在文件')
    sync_parser.add_argument('-c', '--course', help='学科名称（可选，不填则全量同步）')
    sync_parser.add_argument('-a', '--assignment', help='作业名称（可选，需与 -c 配合使用）')

    pack_parser = subparsers.add_parser('pack', help='打包指定作业')
    pack_parser.add_argument('-c', '--course', required=True, help='科目名称')
    pack_parser.add_argument('-a', '--assignment', required=True, help='作业名称')
    pack_parser.add_argument('-t', '--target-zip', required=True, help='输出 ZIP 文件路径')
    pack_parser.add_argument('--force', '-f', action='store_true', help='强制覆盖已存在文件')

    report_parser = subparsers.add_parser('report', help='生成统计报告')
    report_parser.add_argument('-r', '--report', required=True, help='输出 Excel 文件路径')

    new_parser = subparsers.add_parser('new', help='为所有学生创建作业文件夹')
    new_parser.add_argument('-c', '--course', required=True, help='科目名称')
    new_parser.add_argument('-a', '--assignment', required=True, help='作业名称')

    delete_parser = subparsers.add_parser('delete', help='删除所有学生的指定作业文件夹')
    delete_parser.add_argument('-c', '--course', required=True, help='科目名称')
    delete_parser.add_argument('-a', '--assignment', required=True, help='作业名称')
    delete_parser.add_argument('--yes', action='store_true', help='跳过确认直接删除')

    args = parser.parse_args()

    if args.command == 'sync':
        if args.course:
            sync_assignment(args.course, args.assignment, force=args.force)
        else:
            sync_all(force=args.force)
    elif args.command == 'pack':
        zip_assignment(args.course, args.assignment, Path(args.target_zip), args.force)
    elif args.command == 'report':
        generate_report(Path(args.report))
    elif args.command == 'new':
        new_assignment(args.course, args.assignment)
    elif args.command == 'delete':
        delete_assignment(args.course, args.assignment, yes=args.yes)
    else:
        # 兼容旧版无子命令
        if hasattr(args, 'course') and args.course:
            sync_assignment(args.course, getattr(args, 'assignment', None), force=getattr(args, 'force', False))
        elif hasattr(args, 'report') and args.report:
            generate_report(Path(args.report))
        else:
            sync_all(force=getattr(args, 'force', False))

if __name__ == '__main__':
    main()