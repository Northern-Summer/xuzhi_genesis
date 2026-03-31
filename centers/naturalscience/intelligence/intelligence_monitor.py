#!/usr/bin/env python3
"""
AI4S Multi-Source Intelligence Monitor | Gamma
综合监控Reddit, GitHub, Discord, X等平台
提取成功/失败经验、工具趋势、未解难题
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
DATA_DIR = Path("/home/summer/xuzhi_genesis/centers/naturalscience/intelligence")
DB_PATH = DATA_DIR / "intelligence.db"

# Monitoring targets
REDDIT_TARGETS = [
    "chemoinformatics",
    "MachineLearning", 
    "drugdiscovery",
    "bioinformatics"
]

GITHUB_TARGETS = [
    ("rdkit", "rdkit"),           # org/repo
    ("deepchem", "deepchem"),
    ("openbabel", "openbabel"),
    ("pandegroup", "openmm")
]

DISCORD_TARGETS = [
    "rdkit-community",  # placeholder
    "comp-chem"
]

class IntelligenceDB:
    """SQLite database for storing intelligence"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Reddit posts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reddit_posts (
                id TEXT PRIMARY KEY,
                subreddit TEXT,
                title TEXT,
                content TEXT,
                author TEXT,
                score INTEGER,
                num_comments INTEGER,
                created_utc TIMESTAMP,
                url TEXT,
                category TEXT,  -- success, failure, question, tool, trend
                extracted_insights TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # GitHub discussions and issues
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS github_discussions (
                id TEXT PRIMARY KEY,
                repo TEXT,
                title TEXT,
                body TEXT,
                author TEXT,
                state TEXT,
                comments INTEGER,
                created_at TIMESTAMP,
                url TEXT,
                category TEXT,
                extracted_insights TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Intelligence summaries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summaries (
                date TEXT PRIMARY KEY,
                source TEXT,
                summary TEXT,
                key_insights TEXT,
                trends TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"[DB] Initialized at {self.db_path}")
    
    def insert_reddit_post(self, post_data):
        """Insert Reddit post"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO reddit_posts 
                (id, subreddit, title, content, author, score, num_comments, 
                 created_utc, url, category, extracted_insights)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post_data['id'],
                post_data['subreddit'],
                post_data['title'],
                post_data.get('content', ''),
                post_data['author'],
                post_data['score'],
                post_data['num_comments'],
                post_data['created_utc'],
                post_data['url'],
                post_data.get('category', 'uncategorized'),
                post_data.get('extracted_insights', '')
            ))
            conn.commit()
        except Exception as e:
            print(f"[DB Error] {e}")
        finally:
            conn.close()


def analyze_content(title, content):
    """Analyze content to extract category and insights"""
    title_lower = title.lower()
    content_lower = content.lower() if content else ''
    
    # Category detection
    category = 'uncategorized'
    insights = []
    
    # Success patterns
    if any(word in title_lower for word in ['solved', 'worked', 'success', 'finally', 'working']):
        category = 'success'
        insights.append("Success case identified")
    
    # Failure patterns
    elif any(word in title_lower for word in ['error', 'fail', 'issue', 'problem', 'bug', 'crash']):
        category = 'failure'
        insights.append("Failure/Error case identified")
    
    # Tool discussion
    elif any(word in title_lower for word in ['tool', 'library', 'package', 'recommend']):
        category = 'tool'
        insights.append("Tool discussion")
    
    # Questions
    elif any(word in title_lower for word in ['how to', 'help', 'question', 'what is']):
        category = 'question'
    
    # Extract specific tools mentioned
    tools = []
    if 'rdkit' in content_lower:
        tools.append('RDKit')
    if 'openbabel' in content_lower:
        tools.append('OpenBabel')
    if 'deepchem' in content_lower:
        tools.append('DeepChem')
    if 'pytorch' in content_lower or 'torch' in content_lower:
        tools.append('PyTorch')
    if 'tensorflow' in content_lower:
        tools.append('TensorFlow')
    
    if tools:
        insights.append(f"Tools mentioned: {', '.join(tools)}")
    
    return category, ' | '.join(insights) if insights else ''


def fetch_reddit_manual():
    """
    Manual Reddit data collection via web search
    (API requires auth, using search as proxy)
    """
    print("[Reddit] Collecting via web search...")
    
    posts = []
    
    # Use searxng to find recent Reddit posts
    # This is a placeholder - in production would use PRAW or pushshift
    
    print(f"[Reddit] Collected {len(posts)} posts")
    return posts


def fetch_github_discussions_manual():
    """
    Fetch GitHub discussions via API (no auth needed for public)
    """
    print("[GitHub] Collecting discussions...")
    
    import urllib.request
    import urllib.error
    
    discussions = []
    
    for org, repo in GITHUB_TARGETS[:2]:  # Start with top 2
        try:
            # GitHub API for issues (discussions API requires auth)
            url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page=10"
            
            req = urllib.request.Request(url)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'Gamma-AI4S-Monitor')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode())
                
                for item in data:
                    # Skip pull requests
                    if 'pull_request' in item:
                        continue
                    
                    category, insights = analyze_content(
                        item.get('title', ''),
                        item.get('body', '')
                    )
                    
                    discussions.append({
                        'id': str(item['id']),
                        'repo': f"{org}/{repo}",
                        'title': item['title'],
                        'body': item.get('body', '')[:1000],  # Truncate
                        'author': item['user']['login'],
                        'state': item['state'],
                        'comments': item['comments'],
                        'created_at': item['created_at'],
                        'url': item['html_url'],
                        'category': category,
                        'extracted_insights': insights
                    })
                    
        except Exception as e:
            print(f"[GitHub Error] {org}/{repo}: {e}")
    
    print(f"[GitHub] Collected {len(discussions)} discussions")
    return discussions


def generate_daily_summary(db_path, date_str=None):
    """Generate daily intelligence summary"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get today's data
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM reddit_posts 
        WHERE date(collected_at) = ?
        GROUP BY category
    ''', (date_str,))
    reddit_stats = cursor.fetchall()
    
    cursor.execute('''
        SELECT category, COUNT(*) as count 
        FROM github_discussions 
        WHERE date(collected_at) = ?
        GROUP BY category
    ''', (date_str,))
    github_stats = cursor.fetchall()
    
    # Get top insights
    cursor.execute('''
        SELECT title, extracted_insights, url
        FROM reddit_posts
        WHERE date(collected_at) = ? AND category IN ('success', 'failure')
        ORDER BY score DESC
        LIMIT 5
    ''', (date_str,))
    top_insights = cursor.fetchall()
    
    conn.close()
    
    summary = {
        'date': date_str,
        'reddit_stats': dict(reddit_stats),
        'github_stats': dict(github_stats),
        'top_insights': [
            {'title': t, 'insights': i, 'url': u}
            for t, i, u in top_insights
        ]
    }
    
    return summary


def main():
    """Main monitoring routine"""
    print("="*60)
    print("AI4S Intelligence Monitor | Gamma")
    print("="*60)
    print(f"Started at: {datetime.now()}")
    
    # Initialize database
    db = IntelligenceDB(DB_PATH)
    
    # Collect data
    print("\n[1/3] Collecting Reddit intelligence...")
    reddit_posts = fetch_reddit_manual()
    for post in reddit_posts:
        db.insert_reddit_post(post)
    
    print("\n[2/3] Collecting GitHub intelligence...")
    github_discussions = fetch_github_discussions_manual()
    # TODO: Insert to DB
    
    print("\n[3/3] Generating summary...")
    summary = generate_daily_summary(DB_PATH)
    
    # Save summary
    summary_path = DATA_DIR / "reports" / f"daily_summary_{datetime.now().strftime('%Y%m%d')}.json"
    summary_path.parent.mkdir(exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n[Done] Summary saved to: {summary_path}")
    print(f"Reddit stats: {summary['reddit_stats']}")
    print(f"GitHub stats: {summary['github_stats']}")


if __name__ == "__main__":
    main()
