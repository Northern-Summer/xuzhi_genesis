#!/usr/bin/env bash
# 第四阶段：知识交易与认知积分
set -euo pipefail

echo "=================================================="
echo "开始执行第四阶段：知识交易与认知积分"
echo "=================================================="

BASE_DIR="/home/summer/xuzhi_genesis"
INTEL_DIR="$BASE_DIR/centers/intelligence"
MARKET_DIR="$INTEL_DIR/knowledge_market"
AGENTS_BASE="/home/summer/.openclaw/agents"
RATINGS_JSON="/home/summer/.openclaw/centers/mind/society/ratings.json"
BACKUP_DIR="$BASE_DIR/backups/upgrade_stage4_$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"
mkdir -p "$MARKET_DIR"/{listings,purchased}
echo "✅ 创建市场目录: $MARKET_DIR"

# 备份相关文件
cp "$RATINGS_JSON" "$BACKUP_DIR/ratings.json.bak" 2>/dev/null || echo "⚠️ ratings.json 不存在"
cp "$INTEL_DIR/context_injector.py" "$BACKUP_DIR/context_injector.py.bak" 2>/dev/null || true
echo "✅ 已备份相关文件"

# 1. 初始化 ratings.json，为每个智能体添加 credit 字段（如果不存在）
python3 << EOF
import json
from pathlib import Path

ratings_file = Path("$RATINGS_JSON")
if ratings_file.exists():
    with open(ratings_file) as f:
        data = json.load(f)
    agents = data.get("agents", {})
    modified = False
    for agent_id, props in agents.items():
        if "credit" not in props:
            props["credit"] = 10  # 初始积分
            modified = True
    if modified:
        with open(ratings_file, 'w') as f:
            json.dump(data, f, indent=2)
        print("✅ 已为智能体添加初始积分(10)")
    else:
        print("✅ 积分字段已存在")
else:
    print("⚠️ ratings.json 不存在，跳过初始化")
EOF

# 2. 创建知识市场核心脚本
cat > "$INTEL_DIR/knowledge_market.py" << 'EOF'
#!/usr/bin/env python3
"""
知识交易市场：智能体可以挂牌私有知识，购买其他智能体的知识。
"""
import json
import shutil
from pathlib import Path
from datetime import datetime

MARKET_DIR = Path.home() / "xuzhi_genesis" / "centers" / "intelligence" / "knowledge_market"
LISTINGS_DIR = MARKET_DIR / "listings"
PURCHASED_DIR = MARKET_DIR / "purchased"
RATINGS_JSON = Path.home() / ".openclaw" / "centers" / "mind" / "society" / "ratings.json"
AGENTS_BASE = Path.home() / ".openclaw" / "agents"

LISTINGS_DIR.mkdir(parents=True, exist_ok=True)
PURCHASED_DIR.mkdir(parents=True, exist_ok=True)

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_agent_credit(agent_id):
    with open(RATINGS_JSON) as f:
        data = json.load(f)
    return data.get("agents", {}).get(agent_id, {}).get("credit", 0)

def update_agent_credit(agent_id, delta):
    with open(RATINGS_JSON) as f:
        data = json.load(f)
    if agent_id not in data["agents"]:
        data["agents"][agent_id] = {}
    data["agents"][agent_id]["credit"] = data["agents"][agent_id].get("credit", 10) + delta
    with open(RATINGS_JSON, 'w') as f:
        json.dump(data, f, indent=2)

def list_agent_knowledge(agent_id):
    """智能体将自己的私有知识（种子）挂牌"""
    private_dir = AGENTS_BASE / agent_id / "workspace" / "knowledge"
    if not private_dir.exists():
        print(f"❌ {agent_id} 没有知识目录")
        return
    # 假设私有知识是以 .md 文件存储
    for file in private_dir.glob("*.md"):
        listing_id = f"{agent_id}_{file.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        listing_file = LISTINGS_DIR / f"{listing_id}.json"
        # 询问价格（简化：可让用户输入，或根据文件大小等自动定价）
        price = 5  # 默认价格，可后续修改
        listing = {
            "id": listing_id,
            "seller": agent_id,
            "filename": file.name,
            "price": price,
            "description": f"私有知识：{file.stem}",
            "listed_at": datetime.now().isoformat(),
            "file_path": str(file)
        }
        with open(listing_file, 'w') as f:
            json.dump(listing, f, indent=2)
        print(f"✅ {agent_id} 挂牌知识: {file.name} 价格 {price}")

def query_market(agent_id):
    """查询市场，返回可购买的种子列表（排除自己挂牌的）"""
    listings = []
    for lf in LISTINGS_DIR.glob("*.json"):
        with open(lf) as f:
            listing = json.load(f)
        if listing["seller"] != agent_id:
            listings.append(listing)
    return listings

def buy_knowledge(buyer_id, listing_id):
    """购买知识"""
    listing_file = LISTINGS_DIR / f"{listing_id}.json"
    if not listing_file.exists():
        print("❌ 挂牌不存在")
        return
    with open(listing_file) as f:
        listing = json.load(f)
    seller = listing["seller"]
    price = listing["price"]

    buyer_credit = get_agent_credit(buyer_id)
    if buyer_credit < price:
        print(f"❌ 积分不足，当前 {buyer_credit}，需要 {price}")
        return

    # 扣除买方积分，增加卖方积分
    update_agent_credit(buyer_id, -price)
    update_agent_credit(seller, price)

    # 复制知识文件到买方目录
    src = Path(listing["file_path"])
    buyer_knowledge_dir = AGENTS_BASE / buyer_id / "workspace" / "knowledge"
    buyer_knowledge_dir.mkdir(parents=True, exist_ok=True)
    dst = buyer_knowledge_dir / src.name
    shutil.copy2(src, dst)

    # 记录交易
    record = {
        "listing_id": listing_id,
        "buyer": buyer_id,
        "seller": seller,
        "price": price,
        "time": datetime.now().isoformat(),
        "file": src.name
    }
    record_file = PURCHASED_DIR / f"{buyer_id}_{listing_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(record_file, 'w') as f:
        json.dump(record, f, indent=2)

    # 可选：从市场移除该挂牌
    # listing_file.unlink()

    print(f"✅ {buyer_id} 购买了 {src.name}，支付 {price} 积分")

def main():
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  knowledge_market.py list <agent_id>                 # 查询市场")
        print("  knowledge_market.py list-mine <agent_id>            # 查看自己的挂牌")
        print("  knowledge_market.py sell <agent_id> [price]         # 挂牌私有知识")
        print("  knowledge_market.py buy <agent_id> <listing_id>     # 购买知识")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "list" and len(sys.argv) == 3:
        agent = sys.argv[2]
        listings = query_market(agent)
        if not listings:
            print("市场为空")
        for l in listings:
            print(f"{l['id']} | {l['seller']} | {l['filename']} | 价格:{l['price']} | {l['description']}")
    elif cmd == "list-mine" and len(sys.argv) == 3:
        agent = sys.argv[2]
        for lf in LISTINGS_DIR.glob("*.json"):
            with open(lf) as f:
                l = json.load(f)
            if l["seller"] == agent:
                print(f"{l['id']} | {l['filename']} | 价格:{l['price']}")
    elif cmd == "sell" and len(sys.argv) >= 3:
        agent = sys.argv[2]
        list_agent_knowledge(agent)
    elif cmd == "buy" and len(sys.argv) == 4:
        agent = sys.argv[2]
        listing_id = sys.argv[3]
        buy_knowledge(agent, listing_id)
    else:
        print("无效命令")

if __name__ == "__main__":
    main()
EOF
chmod +x "$INTEL_DIR/knowledge_market.py"
echo "✅ 已创建知识市场脚本"

# 3. 修改 context_injector.py，在上下文中加入市场推荐
cat >> "$INTEL_DIR/context_injector.py" << 'EOF'

# ----- 第四阶段：市场推荐 -----
def get_market_recommendations(agent_id, limit=3):
    """获取市场上与智能体可能相关的知识（随机推荐）"""
    import json
    market_script = Path(__file__).parent / "knowledge_market.py"
    # 简单调用 market 脚本查询
    # 这里用 subprocess 调用 market list，但为了避免性能问题，直接读取 listings 目录
    listings_dir = Path(__file__).parent / "knowledge_market" / "listings"
    if not listings_dir.exists():
        return []
    recs = []
    for lf in list(listings_dir.glob("*.json"))[:limit]:
        with open(lf) as f:
            listing = json.load(f)
        if listing["seller"] != agent_id:
            recs.append(f"可购买知识: {listing['filename']} (卖家 {listing['seller']}, 价格 {listing['price']})")
    return recs

def inject_market_recommendations(context_lines, agent_id):
    recs = get_market_recommendations(agent_id)
    if recs:
        context_lines.append("\n## 知识市场推荐")
        context_lines.extend(recs)
    return context_lines

# 修改 generate_context 函数，在返回前调用注入
# 由于原文件可能已存在，我们通过 sed 在函数末尾添加调用
EOF

# 使用 sed 在 generate_context 函数返回前插入市场推荐
sed -i '/return context/ i\    context_lines = inject_market_recommendations(context_lines, agent_id)' "$INTEL_DIR/context_injector.py"
echo "✅ 已修改 context_injector.py，加入市场推荐"

# 4. 在 ratings.json 中确保积分字段已添加（已做）

# 5. 创建示例私有知识目录（可选）
for agent in main scientist engineer philosopher; do
    mkdir -p "$AGENTS_BASE/$agent/workspace/knowledge"
    echo "# 私有知识示例\n\n这是 $agent 的私有知识，仅供测试。" > "$AGENTS_BASE/$agent/workspace/knowledge/test_knowledge_$agent.md"
done
echo "✅ 为各智能体创建了示例私有知识文件（用于测试挂牌）"

echo "=================================================="
echo "第四阶段完成！"
echo "备份位置: $BACKUP_DIR"
echo "测试命令示例："
echo "  python3 $INTEL_DIR/knowledge_market.py list main            # 查看市场"
echo "  python3 $INTEL_DIR/knowledge_market.py sell main            # main 挂牌知识"
echo "  python3 $INTEL_DIR/knowledge_market.py buy scientist <listing_id>  # scientist 购买"
echo "  cat $AGENTS_BASE/scientist/workspace/knowledge/test_knowledge_main.md  # 查看购买的文件"
echo "=================================================="

