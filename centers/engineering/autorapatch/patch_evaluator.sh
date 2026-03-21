#!/bin/bash
#==============================================================================
# patch_evaluator.sh — AutoRA-Patch Phase 3
# 在 staging 环境验证补丁，输出 diff + 风险评估
#==============================================================================

set -e

PATCHES_DIR="/home/summer/autorapatch/patches"
STAGING_LOG="/home/summer/autorapatch/staging.log"
AUDIT_LOG="/home/summer/autorapatch/audit.jsonl"

mkdir -p "$PATCHES_DIR" "$(dirname "$AUDIT_LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$STAGING_LOG"; }

evaluate() {
    local patch_file="$1"
    local patch_name
    patch_name=$(basename "$patch_file" .sh)

    log "=== Evaluating: $patch_name ==="

    # 1. 静态检查：危险命令
    local dangerous
    dangerous=$(grep -cE "(rm\s+-[rf]|truncate\s+|--force|git\s+push.*--force|>\s*/dev/sd)" "$patch_file" 2>/dev/null || echo 0)
    if [[ "$dangerous" -gt 0 ]]; then
        log "  ⚠️  DANGEROUS: contains $dangerous high-risk command(s)"
        local risk="HIGH"
    else
        log "  ✅ No dangerous commands detected"
        local risk="LOW"
    fi

    # 2. Dry-run 验证（语法检查）
    local syntax_ok
    bash -n "$patch_file" 2>&1 && syntax_ok=true || syntax_ok=false
    if $syntax_ok; then
        log "  ✅ Syntax OK"
    else
        log "  ❌ Syntax error in patch"
        return 1
    fi

    # 3. 实际执行（带 timeout）
    log "  → Executing patch (timeout=30s)..."
    local patch_output
    patch_output=$(timeout 30 "$patch_file" 2>&1) && local patch_exit=0 || local patch_exit=$?
    echo "$patch_output" | head -20 >> "$STAGING_LOG"
    log "  Exit code: $patch_exit"

    # 4. 输出 JSONL 审计记录
    local audit_entry
    audit_entry=$(cat <<EOF
{"timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)", "patch": "$patch_name", "risk": "$risk", "exit": $patch_exit, "dangerous_cmds": $dangerous}
EOF)
    echo "$audit_entry" >> "$AUDIT_LOG"
    log "  Audit recorded: $audit_entry"

    if [[ $patch_exit -eq 0 ]]; then
        log "  ✅ PASSED"
    else
        log "  ❌ FAILED (exit $patch_exit)"
    fi

    log ""
}

# 主循环
if [[ -z "$1" ]]; then
    log "No patch specified — scanning $PATCHES_DIR"
    for f in "$PATCHES_DIR"/*.sh; do
        [[ -e "$f" ]] && evaluate "$f"
    done
else
    evaluate "$1"
fi
