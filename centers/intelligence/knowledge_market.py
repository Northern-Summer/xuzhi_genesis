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
