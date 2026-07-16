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
    # Layout khớp style terminal.svg: canvas ngoài có glow nền, bên trong
    # là 1 "khung cửa sổ" riêng (box tối, viền, bo góc) + 3 chấm tròn +
    # label — y hệt toạ độ/màu terminal dùng, để 2 phần trông như cùng
    # 1 app đang cuộn tiếp chứ không phải 2 widget khác nhau.
    CANVAS_W, CANVAS_H = 1200, 540
    BOX_X, BOX_Y, BOX_W, BOX_H = 80, 60, 1040, 440
    CONTENT_X = 120
    CARD_W, CARD_H, CARD_GAP = 225, 110, 15
    CARD_XS = [CONTENT_X + i * (CARD_W + CARD_GAP) for i in range(4)]
    TITLE_Y = 150
    CARDS_Y = 175
    LANG_LABEL_Y = CARDS_Y + CARD_H + 45
    BAR_Y = LANG_LABEL_Y + 20
    BAR_H = 30
    BAR_X = CONTENT_X
    BAR_W = BOX_X + BOX_W - 40 - BAR_X
    LEGEND_Y_START = BAR_Y + BAR_H + 45
    LEGEND_ROW_H = 32

    font = "'Courier New', Courier, monospace"

    def count_up(x, y, final_value, font_size, color, begin, duration=1.1, steps=9):
        """Hiệu ứng đếm số chạy lên. SMIL không animate được nội dung text
        liên tục, nên xếp chồng nhiều <text> ở các mốc giá trị trung gian
        rồi bật/tắt nhanh bằng opacity (fill="freeze") để tạo cảm giác số
        đang nhảy lên, chỉ 1 giá trị hiển thị tại một thời điểm."""
        try:
            final_int = int(final_value)
        except (TypeError, ValueError):
            return (f'<text x="{x}" y="{y}" fill="{color}" font-size="{font_size}" '
                    f'font-weight="bold" font-family="{font}">{final_value}</text>')

        step_dur = duration / steps
        values = sorted(set(round(final_int * i / steps) for i in range(1, steps + 1)))
        if not values or values[-1] != final_int:
            values.append(final_int)

        out = []
        for i, v in enumerate(values):
            t_show = begin + i * step_dur
            hide = ""
            if i < len(values) - 1:
                t_hide = begin + (i + 1) * step_dur
                hide = (f'<set attributeName="opacity" to="0" '
                        f'begin="{t_hide:.2f}s" fill="freeze"/>')
            out.append(
                f'<text x="{x}" y="{y}" fill="{color}" font-size="{font_size}" '
                f'font-weight="bold" font-family="{font}" opacity="0">{v}'
                f'<animate attributeName="opacity" from="0" to="1" dur="0.08s" '
                f'begin="{t_show:.2f}s" fill="freeze"/>{hide}</text>'
            )
        return "\n".join(out)

    def stat_card(x, label, value, color, delay):
        number = count_up(20, 50, value, 34, color, begin=delay + 0.35)
        return f"""
  <g transform="translate({x}, {CARDS_Y})" opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.5s"
             begin="{delay:.2f}s" fill="freeze"/>
    <rect width="{CARD_W}" height="{CARD_H}" rx="14" fill="#0f172a"
          stroke="#334155" stroke-width="2"/>
    {number}
    <text x="20" y="85" fill="#94a3b8" font-size="15"
          font-family="{font}">{label}</text>
  </g>"""

    cards = "".join([
        stat_card(CARD_XS[0], "GitHub Stars", stats["stars"], "#eab308", delay=0.6),
        stat_card(CARD_XS[1], "Commits (năm nay)", stats["commits"], "#4ade80", delay=0.9),
        stat_card(CARD_XS[2], "Repositories", stats["repos"], "#38bdf8", delay=1.2),
        stat_card(CARD_XS[3], "Followers", stats["followers"], "#f472b6", delay=1.5),
    ])

    # Thanh Top Languages: các đoạn màu đặt cố định ở vị trí cuối cùng,
    # dùng clip-path animate width 0 -> đầy đủ để tạo hiệu ứng "vén màn"
    bar_begin, bar_dur = 2.2, 1.3
    legend_begin = bar_begin + bar_dur + 0.2

    cursor = BAR_X
    bar_segments = ""
    legend_items = ""
    for i, lang in enumerate(stats["languages"]):
        seg_w = BAR_W * (lang["percent"] / 100)
        bar_segments += (
            f'<rect x="{cursor:.1f}" y="{BAR_Y}" width="{seg_w:.1f}" '
            f'height="{BAR_H}" fill="{lang["color"]}"/>'
        )
        legend_x = BAR_X + (i % 3) * 320
        legend_y = LEGEND_Y_START + (i // 3) * LEGEND_ROW_H
        delay = legend_begin + i * 0.15
        legend_items += f"""
  <g opacity="0">
    <animate attributeName="opacity" from="0" to="1" dur="0.35s"
             begin="{delay:.2f}s" fill="freeze"/>
    <circle cx="{legend_x}" cy="{legend_y - 6}" r="7" fill="{lang['color']}"/>
    <text x="{legend_x + 18}" y="{legend_y}" fill="white" font-size="17"
          font-family="{font}">{lang['name']} · {lang['percent']}%</text>
  </g>"""
        cursor += seg_w

    return f"""<svg width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}"
     xmlns="http://www.w3.org/2000/svg">

  <defs>
    <radialGradient id="bgGlow2" cx="50%" cy="0%" r="80%">
      <stop offset="0%" stop-color="#0b1224"/>
      <stop offset="100%" stop-color="#020617"/>
    </radialGradient>
    <clipPath id="barClip">
      <rect x="{BAR_X}" y="{BAR_Y}" width="0" height="{BAR_H}" rx="10">
        <animate attributeName="width" from="0" to="{BAR_W}" dur="{bar_dur}s"

                 begin="{bar_begin}s" fill="freeze"/>
      </rect>
    </clipPath>
  </defs>

  <rect width="{CANVAS_W}" height="{CANVAS_H}" rx="20" fill="url(#bgGlow2)"/>

  <rect x="{BOX_X}" y="{BOX_Y}" width="{BOX_W}" height="{BOX_H}" rx="15"
        fill="#0f172a" stroke="#334155" stroke-width="3"/>

  <circle cx="120" cy="100" r="10" fill="#ef4444"/>
  <circle cx="155" cy="100" r="10" fill="#eab308"/>
  <circle cx="190" cy="100" r="10" fill="#22c55e"/>
  <text x="240" y="108" fill="#94a3b8" font-size="22" font-family="{font}">huanyd1-stats</text>

  <text x="{CONTENT_X}" y="{TITLE_Y}" fill="white" font-size="24" font-weight="bold"
        font-family="{font}" opacity="0">📊 GitHub Stats (auto-updated)
    <animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="0.1s" fill="freeze"/>
  </text>

  {cards}

  <text x="{CONTENT_X}" y="{LANG_LABEL_Y}" fill="#94a3b8" font-size="18"
        font-family="{font}" opacity="0">Top Languages
    <animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="2.0s" fill="freeze"/>
  </text>

  <rect x="{BAR_X}" y="{BAR_Y}" width="{BAR_W}" height="{BAR_H}" rx="10"
        fill="#1e293b"/>
  <g clip-path="url(#barClip)">
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