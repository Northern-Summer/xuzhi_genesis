#!/usr/bin/env python3
"""
AI4S Multi-Source Intelligence Monitor | Gamma
综合监控Reddit, GitHub, Discord, X等平台
提取成功/失败经验、工具趋势、未解难题

Updated: 2026-03-30 - Added Reddit and Discord support
"""

import os
import json
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path

# Configuration
DATA_DIR = Path("/home/summer/xuzhi_genesis/centers/naturalscience/intelligence")
DB_PATH = DATA_DIR / "intelligence.db"

# Reddit Configuration (Pushshift API - no auth required)
REDDIT_TARGETS = [
    "chemoinformatics",
    "MachineLearning",
    "drugdiscovery",
    "bioinformatics",
    "computational_chemistry",
    "chemistry"
]

# GitHub Targets
GITHUB_TARGETS = [
    ("rdkit", "rdkit"),
    ("deepchem", "deepchem"),
    ("openbabel", "openbabel"),
    ("pandegroup", "openmm")
]

# Discord Webhooks (to be configured)
DISCORD_WEBHOOKS = {
    "rdkit": None,  # To be filled
    "comp_chem": None  # To be filled
}


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
                category TEXT,
                extracted_insights TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # GitHub discussions
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

        # Discord messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discord_messages (
                id TEXT PRIMARY KEY,
                server TEXT,
                channel TEXT,
                author TEXT,
                content TEXT,
                timestamp TIMESTAMP,
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
            print(f"[DB Error Reddit] {e}")
        finally:
            conn.close()

    def insert_github_discussion(self, disc_data):
        """Insert GitHub discussion"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO github_discussions
                (id, repo, title, body, author, state, comments,
                 created_at, url, category, extracted_insights)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                disc_data['id'],
                disc_data['repo'],
                disc_data['title'],
                disc_data.get('body', ''),
                disc_data['author'],
                disc_data['state'],
                disc_data['comments'],
                disc_data['created_at'],
                disc_data['url'],
                disc_data.get('category', 'uncategorized'),
                disc_data.get('extracted_insights', '')
            ))
            conn.commit()
        except Exception as e:
            print(f"[DB Error GitHub] {e}")
        finally:
            conn.close()

    def insert_discord_message(self, msg_data):
        """Insert Discord message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO discord_messages
                (id, server, channel, author, content, timestamp, category, extracted_insights)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                msg_data['id'],
                msg_data['server'],
                msg_data['channel'],
                msg_data['author'],
                msg_data['content'],
                msg_data['timestamp'],
                msg_data.get('category', 'uncategorized'),
                msg_data.get('extracted_insights', '')
            ))
            conn.commit()
        except Exception as e:
            print(f"[DB Error Discord] {e}")
        finally:
            conn.close()


def analyze_content(title, content):
    """Analyze content to extract category and insights"""
    title_lower = title.lower() if title else ''
    content_lower = content.lower() if content else ''

    category = 'uncategorized'
    insights = []

    # Success patterns
    if any(word in title_lower for word in ['solved', 'worked', 'success', 'finally', 'working', 'thank']):
        category = 'success'
        insights.append("Success case identified")

    # Failure patterns
    elif any(word in title_lower for word in ['error', 'fail', 'issue', 'problem', 'bug', 'crash', 'broken']):
        category = 'failure'
        insights.append("Failure/Error case identified")

    # Tool discussion
    elif any(word in title_lower for word in ['tool', 'library', 'package', 'recommend', 'alternative']):
        category = 'tool'
        insights.append("Tool discussion")

    # Questions
    elif any(word in title_lower for word in ['how to', 'help', 'question', 'what is', 'how do', 'tutorial']):
        category = 'question'

    # Career/Job
    elif any(word in title_lower for word in ['job', 'career', 'hiring', 'position', 'phd', 'internship']):
        category = 'career'

    # Extract tools mentioned
    tools = []
    if 'rdkit' in content_lower:
        tools.append('RDKit')
    if 'openbabel' in content_lower:
        tools.append('OpenBabel')
    if 'deepchem' in content_lower:
        tools.append('DeepChem')
    if 'pytorch' in content_lower or 'torch' in content_lower:
        tools.append('PyTorch')
    if 'tensorflow' in content_lower or 'tf.' in content_lower:
        tools.append('TensorFlow')
    if 'scikit' in content_lower or 'sklearn' in content_lower:
        tools.append('scikit-learn')

    if tools:
        insights.append(f"Tools: {', '.join(tools)}")

    return category, ' | '.join(insights) if insights else ''


def fetch_reddit_pushshift(subreddit, limit=10):
    """Fetch Reddit posts using Pushshift API (no auth required)"""
    posts = []

    try:
        # Pushshift API endpoint
        url = f"https://api.pullpush.io/reddit/submission/search/?subreddit={subreddit}&sort=desc&sort_type=created_utc&size={limit}"

        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Gamma-AI4S-Monitor/1.0')

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

            for item in data.get('data', []):
                category, insights = analyze_content(
                    item.get('title', ''),
                    item.get('selftext', '')
                )

                posts.append({
                    'id': str(item['id']),
                    'subreddit': subreddit,
                    'title': item.get('title', ''),
                    'content': item.get('selftext', '')[:2000],
                    'author': item.get('author', 'unknown'),
                    'score': item.get('score', 0),
                    'num_comments': item.get('num_comments', 0),
                    'created_utc': datetime.fromtimestamp(item.get('created_utc', 0)).isoformat(),
                    'url': f"https://reddit.com{item.get('permalink', '')}",
                    'category': category,
                    'extracted_insights': insights
                })

    except Exception as e:
        print(f"[Reddit Error] {subreddit}: {e}")

    return posts


def fetch_github_issues(org, repo, limit=10):
    """Fetch GitHub issues"""
    discussions = []

    try:
        url = f"https://api.github.com/repos/{org}/{repo}/issues?state=all&per_page={limit}"

        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/vnd.github.v3+json')
        req.add_header('User-Agent', 'Gamma-AI4S-Monitor/1.0')

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

            for item in data:
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
                    'body': item.get('body', '')[:1500],
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

    return discussions


def fetch_discord_via_webhook(webhook_url, limit=50):
    """Fetch Discord messages via webhook (placeholder)"""
    # Discord webhook is for sending only
    # To receive messages, need bot token and gateway connection
    # This is a placeholder for future implementation
    print(f"[Discord] Webhook fetch not implemented yet")
    return []


def generate_daily_summary(db_path, date_str=None):
    """Generate daily intelligence summary"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get stats
    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM reddit_posts
        WHERE date(collected_at) = ?
        GROUP BY category
    ''', (date_str,))
    reddit_stats = dict(cursor.fetchall())

    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM github_discussions
        WHERE date(collected_at) = ?
        GROUP BY category
    ''', (date_str,))
    github_stats = dict(cursor.fetchall())

    cursor.execute('''
        SELECT category, COUNT(*) as count
        FROM discord_messages
        WHERE date(collected_at) = ?
        GROUP BY category
    ''', (date_str,))
    discord_stats = dict(cursor.fetchall())

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
        'reddit_stats': reddit_stats,
        'github_stats': github_stats,
        'discord_stats': discord_stats,
        'top_insights': [
            {'title': t, 'insights': i, 'url': u}
            for t, i, u in top_insights
        ]
    }

    return summary


def main():
    """Main monitoring routine"""
    print("="*70)
    print("AI4S Intelligence Monitor | Gamma")
    print("="*70)
    print(f"Started at: {datetime.now()}")

    # Initialize database
    db = IntelligenceDB(DB_PATH)

    # Collect Reddit data
    print("\n[1/3] Collecting Reddit intelligence...")
    total_reddit = 0
    for subreddit in REDDIT_TARGETS[:3]:  # Start with top 3
        print(f"  Fetching r/{subreddit}...")
        posts = fetch_reddit_pushshift(subreddit, limit=10)
        for post in posts:
            db.insert_reddit_post(post)
        total_reddit += len(posts)
        print(f"    Collected {len(posts)} posts")
    print(f"[Reddit] Total: {total_reddit} posts")

    # Collect GitHub data
    print("\n[2/3] Collecting GitHub intelligence...")
    total_github = 0
    for org, repo in GITHUB_TARGETS[:2]:
        print(f"  Fetching {org}/{repo}...")
        discussions = fetch_github_issues(org, repo, limit=10)
        for disc in discussions:
            db.insert_github_discussion(disc)
        total_github += len(discussions)
        print(f"    Collected {len(discussions)} issues")
    print(f"[GitHub] Total: {total_github} discussions")

    # Collect Discord data (placeholder)
    print("\n[3/3] Collecting Discord intelligence...")
    print("  [Discord] Bot integration required - skipped")
    print("[Discord] To enable: Configure bot token and gateway connection")

    # Generate summary
    print("\n[4/4] Generating summary...")
    summary = generate_daily_summary(DB_PATH)

    # Save summary
    summary_path = DATA_DIR / "reports" / f"daily_summary_{datetime.now().strftime('%Y%m%d')}.json"
    summary_path.parent.mkdir(exist_ok=True)
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    print(f"Reddit:   {total_reddit} posts collected")
    print(f"GitHub:   {total_github} issues collected")
    print(f"Discord:  Bot integration pending")
    print(f"\nReport:   {summary_path}")
    print("="*70)


if __name__ == "__main__":
    main()
