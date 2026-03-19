#!/usr/bin/env python3
"""
举报作弊：Agent 质疑某任务完成者声明的模型与事实不符。
用法: report_cheating.py --task <task_id> --accused <agent_id> --reason "<reason>"
"""
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

XUZHI_HOME = Path.home() / 'xuzhi_genesis'
REPORTS_FILE = XUZHI_HOME / 'centers' / 'mind' / 'society' / 'reports.json'
TASKS_FILE = Path.home() / '.openclaw' / 'tasks' / 'tasks.json'

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='举报任务作弊')
    parser.add_argument('--task', required=True, type=int, help='任务ID')
    parser.add_argument('--accused', required=True, help='被举报的智能体ID')
    parser.add_argument('--reason', required=True, help='举报理由')
    args = parser.parse_args()

    # 验证任务存在且已完成
    tasks = load_json(TASKS_FILE)
    task = next((t for t in tasks['tasks'] if t['id'] == args.task), None)
    if not task:
        print(f"错误: 任务 {args.task} 不存在")
        sys.exit(1)
    if task['status'] != 'completed':
        print(f"错误: 任务 {args.task} 未完成，无法举报")
        sys.exit(1)
    if args.accused not in task.get('completed_by', []):
        print(f"错误: {args.accused} 不是该任务的完成者")
        sys.exit(1)

    # 加载举报记录
    reports = load_json(REPORTS_FILE)
    new_id = reports['last_id'] + 1

    report = {
        'id': new_id,
        'task_id': args.task,
        'accused': args.accused,
        'reporter': 'unknown',  # 可从环境变量或参数传入，此处简化
        'reason': args.reason,
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'votes': {},
        'result': None,
        'executed': False
    }
    reports['reports'].append(report)
    reports['last_id'] = new_id
    save_json(REPORTS_FILE, reports)

    # 广播通知
    broadcast = Path.home() / '.openclaw' / 'workspace' / 'broadcast.md'
    with open(broadcast, 'a') as f:
        f.write(f"\n[心智中心] 收到举报：任务 {args.task} 完成者 {args.accused} 可能作弊。举报 ID {new_id}，请所有智能体投票。\n")

    print(f"举报已提交，ID: {new_id}")

if __name__ == '__main__':
    main()
