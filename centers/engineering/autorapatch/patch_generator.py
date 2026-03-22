#!/usr/bin/env python3
"""
patch_generator.py — AutoRA-Patch Phase 2
读取 failure_classifier 输出的事件 → 调用 LLM 生成补丁脚本

调用方式:
    python3 ~/autorapatch/patch_generator.py [--event-jsonl ~/failure_events.jsonl]

输出: JSONL，每行 {pattern_id, patch_script_path, confidence, rationale}
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

# MaaS LLM API (Infini-AI)
LLM_URL = "https://cloud.infini-ai.com/maas/coding/alpha/proxy/v1/chat/completions"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
PROMPT_TEMPLATE = Path("/home/summer/autorapatch/prompt_patch_gen.txt")
PATCHES_DIR = Path("/home/summer/autorapatch/patches")
PATCHES_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Prompt Template
# ============================================================================

SYSTEM_PROMPT = """你是一个高级系统工程师（Xuzhi-Lambda-Ergo），负责根据故障事件生成自动修复补丁。

要求:
1. 补丁必须是纯 Bash 脚本（.sh），放在 /home/summer/autorapatch/patches/
2. 每个补丁必须 idempotent（可重复执行，结果一致）
3. 补丁必须包含 self-check（执行后验证修复成功）
4. 高危操作（rm -rf, git push --force, truncate）必须用 # DANGEROUS 注释标记
5. 每个补丁输出 STDOUT 说明修复了什么

格式:
## 故障摘要
{summary}

## 根因分析
{root_cause}

## 补丁脚本
```bash
#!/bin/bash
# PATCH: {pattern_id}
# Generated: {timestamp}
# Confidence: {confidence}
{patch_code}
```
"""

# ============================================================================
# LLM 调用
# ============================================================================

def call_llm(pattern_id: str, summary: str, root_cause: str, confidence: float) -> str:
    """调用 MaaS LLM 生成补丁脚本"""
    if not LLM_API_KEY:
        # P0-3: 写 flag 文件而非静默跳过，使 operator 可感知系统停摆
        flag_path = PATCHES_DIR / f"nopatch_{pattern_id}.flag"
        flag_path.write_text(
            f"# {datetime.utcnow().isoformat()}Z\n"
            f"# LLM_API_KEY missing — auto-patch disabled for {pattern_id}\n"
            f"# Root cause: {root_cause}\n"
        )
        return f"# LLM_API_KEY not set — nopatch flag written: {flag_path}"

    user_prompt = SYSTEM_PROMPT.format(
        summary=summary,
        root_cause=root_cause,
        timestamp=datetime.utcnow().isoformat() + "Z",
        confidence=f"{confidence:.0%}",
        patch_code="",
    )

    payload = {
        "model": "alpha",
        "messages": [
            {"role": "system", "content": "You are Xuzhi-Lambda-Ergo, a senior systems engineer."},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }

    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "POST", LLM_URL,
             "-H", f"Authorization: Bearer {LLM_API_KEY}",
             "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=30,
        )
        resp = json.loads(result.stdout)
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        return f"# LLM call failed: {e}\n# Falling back to manual repair required."

# ============================================================================
# Parser
# ============================================================================

def extract_code_block(text: str) -> str | None:
    """从 markdown 响应中提取 bash 代码块"""
    import re
    m = re.search(r"```bash\s*(.*?)\s*```", text, re.DOTALL)
    return m.group(1).strip() if m else None

# ============================================================================
# Main
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-jsonl", default="-")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.event_jsonl == "-":
        events = [json.loads(line) for line in sys.stdin if line.strip()]
    else:
        events = [json.loads(line) for line in open(args.event_jsonl) if line.strip()]

    for event in events:
        pid = event["pattern_id"]
        summary = event.get("description", "")
        confidence = event.get("occurrence_count", 1) / 10.0  # 超过10次=100%

        # 硬编码根因分析（已知故障模式）
        root_cause_db = {
            "CRON_KIND_VIOLATION": "cron job 使用了 agentTurn payload，每次触发消耗完整 agentTurn 配额，应改为 systemEvent",
            "GATEWAY_DOWN": "Gateway 进程崩溃或无响应，需要重启",
            "CRON_DISABLED": "Gateway 重启后 cron enabled 状态丢失，需要自愈脚本重新启用",
            "GIT_UNPUSHED": "local commits 未推送到 remote，可能在系统崩溃时丢失",
        }
        root_cause = root_cause_db.get(pid, f"Unknown failure pattern: {pid}")

        print(f"# Processing {pid} (confidence={confidence:.0%})...", file=sys.stderr)

        if args.dry_run:
            print(json.dumps({
                "pattern_id": pid,
                "patch_script_path": None,
                "confidence": confidence,
                "rationale": "dry-run, no LLM call",
            }, ensure_ascii=False))
            continue

        response = call_llm(pid, summary, root_cause, confidence)
        code = extract_code_block(response)

        if code:
            patch_path = PATCHES_DIR / f"{pid}.sh"
            patch_path.write_text(code + "\n")
            os.chmod(patch_path, 0o755)
            print(json.dumps({
                "pattern_id": pid,
                "patch_script_path": str(patch_path),
                "confidence": confidence,
                "rationale": root_cause,
            }, ensure_ascii=False))
        else:
            print(json.dumps({
                "pattern_id": pid,
                "patch_script_path": None,
                "confidence": confidence,
                "rationale": response[:200],
            }, ensure_ascii=False))

if __name__ == "__main__":
    main()
