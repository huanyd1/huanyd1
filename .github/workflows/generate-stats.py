#!/usr/bin/env python3
"""
generate_stats.py

Gọi GitHub GraphQL API để lấy: total stars, total commits, repo count,
followers, và top languages (tính theo tỉ lệ byte code trong các repo
không phải fork). Sau đó render ra assets/github-stats.svg.

Yêu cầu biến môi trường:
  GH_TOKEN   - Personal Access Token (repo + read:user scope) hoặc
               token mặc định trong GitHub Actions (secrets.GITHUB_TOKEN
               vẫn đủ quyền đọc public data của chính user)
  GH_USERNAME - username GitHub (mặc định: huanyd1)
"""

import os
import sys
import requests

GH_API = "https://api.github.com/graphql"
USERNAME = os.environ.get("GH_USERNAME", "huanyd1")
TOKEN = os.environ.get("GH_TOKEN")

if not TOKEN:
    print("LỖI: thiếu biến môi trường GH_TOKEN", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"bearer {TOKEN}"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    followers { totalCount }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 privacy: PUBLIC) {
      totalCount
      nodes {
        stargazers { totalCount }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
      restrictedContributionsCount
    }
  }
}
"""


def fetch_data():
    resp = requests.post(
        GH_API,
        json={"query": QUERY, "variables": {"login": USERNAME}},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        print(f"LỖI GraphQL: {payload['errors']}", file=sys.stderr)
        sys.exit(1)
    return payload["data"]["user"]


def compute_stats(user):
    repos = user["repositories"]["nodes"]

    total_stars = sum(r["stargazers"]["totalCount"] for r in repos)
    repo_count = user["repositories"]["totalCount"]
    followers = user["followers"]["totalCount"]

    # Commits năm nay tính qua contributionCalendar (public + private,
    # private chỉ tính nếu token có quyền và user cho phép hiển thị)
    calendar = user["contributionsCollection"]["contributionCalendar"]
    total_commits = calendar["totalContributions"]

    # Top languages: cộng dồn "size" (byte) theo từng ngôn ngữ trên
    # toàn bộ repo, sau đó lấy tỉ lệ phần trăm
    lang_totals = {}
    lang_colors = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            lang_totals[name] = lang_totals.get(name, 0) + edge["size"]
            lang_colors[name] = edge["node"]["color"] or "#8a8a8a"

    total_bytes = sum(lang_totals.values()) or 1
    top_languages = sorted(
        lang_totals.items(), key=lambda kv: kv[1], reverse=True
    )[:5]
    top_languages = [
        {
            "name": name,
            "percent": round(size / total_bytes * 100, 1),
            "color": lang_colors[name],
        }
        for name, size in top_languages
    ]

    return {
        "stars": total_stars,
        "commits": total_commits,
        "repos": repo_count,
        "followers": followers,
        "languages": top_languages,
    }


def render_svg(stats: dict) -> str:
    width, height = 1200, 420
    font = "'Times New Roman', Times, serif"

    def stat_card(x, label, value, color):
        return f"""
  <g transform="translate({x}, 90)">
    <rect width="250" height="120" rx="14" fill="#0f172a"
          stroke="#334155" stroke-width="2"/>
    <text x="20" y="40" fill="{color}" font-size="40" font-weight="bold"
          font-family="{font}">{value}</text>
    <text x="20" y="75" fill="#94a3b8" font-size="18"
          font-family="{font}">{label}</text>
  </g>"""

    cards = "".join([
        stat_card(60, "GitHub Stars", stats["stars"], "#eab308"),
        stat_card(330, "Commits (năm nay)", stats["commits"], "#4ade80"),
        stat_card(600, "Repositories", stats["repos"], "#38bdf8"),
        stat_card(870, "Followers", stats["followers"], "#f472b6"),
    ])

    # Thanh Top Languages xếp chồng theo tỉ lệ %
    bar_x, bar_y, bar_w, bar_h = 60, 260, 1080, 34
    cursor = bar_x
    bar_segments = ""
    legend_items = ""
    for i, lang in enumerate(stats["languages"]):
        seg_w = bar_w * (lang["percent"] / 100)
        bar_segments += (
            f'<rect x="{cursor:.1f}" y="{bar_y}" width="{seg_w:.1f}" '
            f'height="{bar_h}" fill="{lang["color"]}"/>'
        )
        legend_x = bar_x + (i % 3) * 360
        legend_y = bar_y + 70 + (i // 3) * 34
        legend_items += f"""
  <circle cx="{legend_x}" cy="{legend_y - 6}" r="7" fill="{lang['color']}"/>
  <text x="{legend_x + 18}" y="{legend_y}" fill="white" font-size="18"
        font-family="{font}">{lang['name']} · {lang['percent']}%</text>"""
        cursor += seg_w

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     xmlns="http://www.w3.org/2000/svg">

  <defs>
    <radialGradient id="bgGlow2" cx="50%" cy="0%" r="80%">
      <stop offset="0%" stop-color="#0b1224"/>
      <stop offset="100%" stop-color="#020617"/>
    </radialGradient>
  </defs>

  <rect width="{width}" height="{height}" rx="20" fill="url(#bgGlow2)"/>

  <text x="60" y="50" fill="white" font-size="26" font-weight="bold"
        font-family="{font}">📊 GitHub Stats (auto-updated)</text>

  {cards}

  <text x="60" y="240" fill="#94a3b8" font-size="18"
        font-family="{font}">Top Languages</text>

  <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="10"
        fill="#1e293b"/>
  <g clip-path="url(#barClip)">
    <clipPath id="barClip">
      <rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="10"/>
    </clipPath>
    {bar_segments}
  </g>

  {legend_items}

</svg>
"""


def main():
    user = fetch_data()
    stats = compute_stats(user)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "github-stats.svg")

    svg = render_svg(stats)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Đã ghi {out_path}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()