#!/usr/bin/env python3
"""
更新 OpenClaw 模型上下文窗口配置（使用 merge 模式）
用法: update_model_config.py <model_name> <context_window>
"""
import json
import sys
from pathlib import Path

OPENCLAW_CONFIG = Path.home() / ".openclaw/openclaw.json"

def update_model(model_name, window):
    if not OPENCLAW_CONFIG.exists():
        print("❌ OpenClaw 配置文件不存在")
        return False
    with open(OPENCLAW_CONFIG) as f:
        config = json.load(f)
    # 确保使用 merge 模式
    if "models" not in config or not isinstance(config["models"], dict):
        config["models"] = {}
    if "mode" not in config["models"]:
        config["models"]["mode"] = "merge"
    # 假设模型在 providers 中定义，此处简化：直接添加 override 字段
    # 实际需根据 OpenClaw 文档调整
    if "model_overrides" not in config:
        config["model_overrides"] = {}
    config["model_overrides"][model_name] = {"context_window": window}
    with open(OPENCLAW_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✅ 已为 {model_name} 设置上下文窗口 {window}，请重启网关生效")
    return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: update_model_config.py <model_name> <context_window>")
        sys.exit(1)
    update_model(sys.argv[1], int(sys.argv[2]))
