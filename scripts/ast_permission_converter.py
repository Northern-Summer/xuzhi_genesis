#!/usr/bin/env python3
"""
AST转换器：将文件中的 open() 和 Path 操作替换为权限检查版本
用法: ./ast_permission_converter.py <file.py> [--dry-run]
"""
import ast
import sys
import os
from pathlib import Path

class PermissionTransformer(ast.NodeTransformer):
    def __init__(self):
        self.has_open_call = False
        self.has_path_call = False
        self.has_safe_open = False
        self.has_safe_path = False

    def visit_Call(self, node):
        # 替换 open() 为 safe_open(agent_id, ...)
        if isinstance(node.func, ast.Name) and node.func.id == 'open':
            self.has_open_call = True
            # 构建 safe_open 调用：safe_open(agent_id, filename, mode)
            # 获取 agent_id 变量（需要在每个函数内注入）
            agent_var = ast.Name(id='agent_id', ctx=ast.Load())
            # 参数顺序：agent_id, filename, mode
            new_args = [agent_var] + node.args
            new_node = ast.Call(
                func=ast.Name(id='safe_open', ctx=ast.Load()),
                args=new_args,
                keywords=node.keywords
            )
            return ast.copy_location(new_node, node)
        return node

    def visit_Attribute(self, node):
        # 替换 Path(...).read_text() 等
        # 先处理 Path 构造
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'Path':
            self.has_path_call = True
            # 替换为 SafePath(agent_id, ...).read_text()
            # 构建 SafePath 调用
            safe_path_call = ast.Call(
                func=ast.Name(id='SafePath', ctx=ast.Load()),
                args=[ast.Name(id='agent_id', ctx=ast.Load())] + node.value.args,
                keywords=node.value.keywords
            )
            # 用 SafePath 对象替换原来的 Path 调用
            new_node = ast.Attribute(
                value=safe_path_call,
                attr=node.attr,
                ctx=node.ctx
            )
            return ast.copy_location(new_node, node)
        return node

def inject_agent_id_getter(tree):
    """在每个函数定义开头插入 agent_id = get_caller_agent()"""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 检查函数体是否已有 agent_id 赋值
            has_agent = any(
                isinstance(stmt, ast.Assign) and
                len(stmt.targets) == 1 and
                isinstance(stmt.targets[0], ast.Name) and
                stmt.targets[0].id == 'agent_id'
                for stmt in node.body
            )
            if not has_agent:
                assign = ast.Assign(
                    targets=[ast.Name(id='agent_id', ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id='get_caller_agent', ctx=ast.Load()),
                        args=[],
                        keywords=[]
                    )
                )
                node.body.insert(0, assign)

def has_imports(tree):
    """检查是否已导入权限模块"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'permission_check':
            return True
    return False

def add_imports(tree):
    """添加必要的导入语句"""
    # 在文件开头插入 import sys 等（如果有需要）
    # 权限模块已在上一脚本中导入，无需重复

def transform_file(filepath, dry_run=False):
    with open(filepath, 'r') as f:
        source = f.read()

    tree = ast.parse(source)
    # 检查是否已经导入权限模块（未导入则跳过，因为上一脚本已添加）
    if not has_imports(tree):
        print(f"跳过 {filepath}: 未导入权限模块，可能未被处理")
        return False

    transformer = PermissionTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    # 注入 agent_id 获取
    inject_agent_id_getter(new_tree)

    # 生成新代码
    try:
        # Python 3.9+
        new_source = ast.unparse(new_tree)
    except AttributeError:
        # 降级使用 astor
        import astor
        new_source = astor.to_source(new_tree)

    if new_source == source:
        print(f"无需修改: {filepath}")
        return False

    if dry_run:
        print(f"需要修改: {filepath}")
        return True
    else:
        # 备份
        backup_path = os.path.join(os.environ['BACKUP_DIR'], os.path.basename(filepath) + '.bak')
        import shutil
        shutil.copy2(filepath, backup_path)
        with open(filepath, 'w') as f:
            f.write(new_source)
        print(f"已修改: {filepath} (备份: {backup_path})")
        return True

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    files = [f for f in sys.argv[1:] if f != '--dry-run' and os.path.isfile(f)]
    if not files:
        print("用法: converter.py <file1.py> [file2.py ...] [--dry-run]")
        sys.exit(1)
    for f in files:
        transform_file(f, dry_run)
