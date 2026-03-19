#!/usr/bin/env python3
"""
安全AST转换器：逐文件处理，输出修改结果或错误
"""
import ast
import sys
import os
import traceback

def transform_file(filepath, dry_run=False):
    try:
        with open(filepath, 'r') as f:
            source = f.read()

        tree = ast.parse(source)

        # 检查是否已导入权限模块
        has_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'permission_check':
                has_import = True
                break
        if not has_import:
            print(f"跳过 {filepath}: 未导入权限模块")
            return False

        # 执行转换（复用之前的PermissionTransformer）
        class PermissionTransformer(ast.NodeTransformer):
            def __init__(self):
                self.has_open = False
                self.has_path = False
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    self.has_open = True
                    new_args = [ast.Name(id='agent_id', ctx=ast.Load())] + node.args
                    return ast.Call(
                        func=ast.Name(id='safe_open', ctx=ast.Load()),
                        args=new_args,
                        keywords=node.keywords
                    )
                return node
            def visit_Attribute(self, node):
                if (isinstance(node.value, ast.Call) and 
                    isinstance(node.value.func, ast.Name) and 
                    node.value.func.id == 'Path'):
                    self.has_path = True
                    safe_path_call = ast.Call(
                        func=ast.Name(id='SafePath', ctx=ast.Load()),
                        args=[ast.Name(id='agent_id', ctx=ast.Load())] + node.value.args,
                        keywords=node.value.keywords
                    )
                    return ast.Attribute(value=safe_path_call, attr=node.attr, ctx=node.ctx)
                return node

        transformer = PermissionTransformer()
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # 在每个函数开头插入 agent_id = get_caller_agent()
        for node in ast.walk(new_tree):
            if isinstance(node, ast.FunctionDef):
                # 检查是否已有赋值
                has_assign = False
                for stmt in node.body:
                    if (isinstance(stmt, ast.Assign) and 
                        len(stmt.targets) == 1 and 
                        isinstance(stmt.targets[0], ast.Name) and 
                        stmt.targets[0].id == 'agent_id'):
                        has_assign = True
                        break
                if not has_assign:
                    assign = ast.Assign(
                        targets=[ast.Name(id='agent_id', ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id='get_caller_agent', ctx=ast.Load()),
                            args=[],
                            keywords=[]
                        )
                    )
                    node.body.insert(0, assign)

        # 生成代码
        try:
            # Python 3.9+
            new_source = ast.unparse(new_tree)
        except AttributeError:
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

    except Exception as e:
        print(f"错误处理 {filepath}: {e}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    files = [f for f in sys.argv[1:] if f != '--dry-run' and os.path.isfile(f)]
    if not files:
        sys.exit(0)
    any_modified = False
    for f in files:
        if transform_file(f, dry_run):
            any_modified = True
    if dry_run and not any_modified:
        print("没有需要修改的文件")
