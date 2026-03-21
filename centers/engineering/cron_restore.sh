#!/bin/bash
#==============================================================================
# cron_restore.sh — Gateway 重启后自动重建 cron
# 读取 ~/.cron_spec.json，确保 spec 里的 cron 全部存在
# 入口：每次 self_heal.sh 触发 + Gateway 重启时
#==============================================================================

set -e

SPEC_FILE="/home/summer/.cron_spec.json"
LOG="/home/summer/.openclaw/workspace/memory/cron_restore.log"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG"; }

[[ ! -f "$SPEC_FILE" ]] && { log "FATAL: $SPEC_FILE not found"; exit 1; }

# 检查 Gateway 是否可用
GATEWAY_URL="http://localhost:8765"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$GATEWAY_URL/" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" != "200" ]]; then
    log "Gateway not ready (HTTP $HTTP_CODE) — skip this run"
    exit 0
fi

# 读取 spec
CRON_COUNT=$(python3 -c "
import json
with open('$SPEC_FILE') as f:
    data = json.load(f)
print(len(data.get('crons', [])))
" 2>/dev/null || echo "0")

log "Cron spec loaded: $CRON_COUNT crons defined"

# 获取当前 cron 列表（从 gateway API）
CURRENT_CRONS=$(curl -s "http://localhost:18789/api/cron/list" \
    -H "Authorization: Bearer sk-local" 2>/dev/null | \
    python3 -c "import sys,json; crons=json.load(sys.stdin).get('crons',[]); print('\n'.join([c.get('name','')+'|'+str(c.get('id','')) for c in crons]))" 2>/dev/null || echo "")

log "Current crons:\n$CURRENT_CRONS"

# 对每条 spec，确保存在
python3 -c "
import json, subprocess, sys

with open('$SPEC_FILE') as f:
    spec = json.load(f)

for item in spec.get('crons', []):
    name = item['name']
    schedule = item['schedule']['expr']
    command = item['command']
    kind = item['payload']['kind']
    
    # 检查是否已存在
    result = subprocess.run(
        ['curl', '-s', 'http://localhost:18789/api/cron/list', '-H', 'Authorization: Bearer sk-local'],
        capture_output=True, text=True
    )
    existing = [c for c in json.loads(result.stdout).get('crons', []) if c.get('name') == name]
    
    if existing:
        print(f'EXISTS: {name}')
    else:
        print(f'MISSING: {name} — needs creation')
        # 构建 curl 命令
        payload = {
            'name': name,
            'schedule': {'kind': 'cron', 'expr': schedule, 'tz': 'Asia/Shanghai'},
            'payload': {'kind': kind, 'text': command},
            'delivery': {'mode': 'none'},
            'sessionTarget': 'main',
            'enabled': True
        }
        cmd = [
            'curl', '-s', '-X', 'POST',
            'http://localhost:18789/api/cron/add',
            '-H', 'Authorization: Bearer sk-local',
            '-H', 'Content-Type: application/json',
            '-d', json.dumps(payload)
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(f'CREATE result: {r.stdout[:200]}')
" 2>&1 | tee -a "$LOG"

log "Cron restore complete"
