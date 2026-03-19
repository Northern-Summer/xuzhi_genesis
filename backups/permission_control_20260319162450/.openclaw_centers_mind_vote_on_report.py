#!/usr/bin/env python3
"""
对举报进行投票。
用法: vote_on_report.py --report <report_id> --vote yes/no --agent <agent_id>
"""
import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

XUZHI_HOME = Path.home() / 'xuzhi_genesis'
REPORTS_FILE = XUZHI_HOME / 'centers' / 'mind' / 'society' / 'reports.json'

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='对举报投票')
    parser.add_argument('--report', required=True, type=int, help='举报ID')
    parser.add_argument('--vote', required=True, choices=['yes', 'no'], help='投票: yes=作弊成立, no=不成立')
    parser.add_argument('--agent', required=True, help='投票的智能体ID')
    args = parser.parse_args()

    reports = load_json(REPORTS_FILE)
    report = next((r for r in reports['reports'] if r['id'] == args.report), None)
    if not report:
        print(f"错误: 举报 {args.report} 不存在")
        sys.exit(1)
    if report['status'] != 'pending':
        print(f"举报已处理，无法再投票")
        sys.exit(1)

    # 记录投票
    report['votes'][args.agent] = args.vote
    save_json(REPORTS_FILE, reports)

    print(f"已为举报 {args.report} 投出 {args.vote}")

if __name__ == '__main__':
    main()
