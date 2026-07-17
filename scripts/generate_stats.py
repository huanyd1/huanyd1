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


def render_fragment(stats: dict):
    """Trả về (fragment_xml, defs_xml, content_height) — CHỈ nội dung
    thuần (title, card, bar, legend), KHÔNG có canvas/box/chrome riêng.
    Thiết kế để nhúng làm 1 <g transform="translate(0,Y)"> bên trong
    khung terminal duy nhất ở file đã gộp — không phải để đứng 1 mình.
    Toạ độ X vẫn theo đúng lưới CONTENT_X=120 của terminal để không
    cần chỉnh lại khi ghép."""
    CONTENT_X = 120
    CONTENT_RIGHT = 1120  # khớp mép phải box terminal (x=80, width=1040)
    CARD_W, CARD_H, CARD_GAP = 225, 110, 15
    CARD_XS = [CONTENT_X + i * (CARD_W + CARD_GAP) for i in range(4)]
    TITLE_Y = 30
    CARDS_Y = 55
    LANG_LABEL_Y = CARDS_Y + CARD_H + 45
    BAR_Y = LANG_LABEL_Y + 20
    BAR_H = 30
    BAR_X = CONTENT_X
    BAR_W = CONTENT_RIGHT - 40 - BAR_X
    LEGEND_Y_START = BAR_Y + BAR_H + 45
    LEGEND_ROW_H = 32
    CONTENT_HEIGHT = LEGEND_Y_START + LEGEND_ROW_H + 15

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

    defs_xml = f"""<clipPath id="barClip">
      <rect x="{BAR_X}" y="{BAR_Y}" width="0" height="{BAR_H}" rx="10">
        <animate attributeName="width" from="0" to="{BAR_W}" dur="{bar_dur}s"
                 begin="{bar_begin}s" fill="freeze"/>
      </rect>
    </clipPath>"""

    fragment_xml = f"""<g id="content" data-height="{CONTENT_HEIGHT}">
  <text x="{CONTENT_X}" y="{TITLE_Y}" fill="white" font-size="22" font-weight="bold"
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
</g>"""

    return fragment_xml, defs_xml, CONTENT_HEIGHT


def render_svg(stats: dict) -> str:
    """Bản standalone (có nền + box) — CHỈ dùng để xem thử/debug độc
    lập, KHÔNG dùng khi merge vào profile.svg (merge dùng render_fragment
    trực tiếp)."""
    fragment_xml, defs_xml, content_height = render_fragment(stats)
    canvas_h = content_height + 100
    return f"""<svg width="1200" height="{canvas_h}" viewBox="0 0 1200 {canvas_h}"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="bgGlowPreview" cx="50%" cy="0%" r="80%">
      <stop offset="0%" stop-color="#0b1224"/>
      <stop offset="100%" stop-color="#020617"/>
    </radialGradient>
    {defs_xml}
  </defs>
  <rect width="1200" height="{canvas_h}" rx="20" fill="url(#bgGlowPreview)"/>
  <g transform="translate(0, 50)">
    {fragment_xml}
  </g>
</svg>
"""


def render_intermediate(stats: dict) -> str:
    """File TRUNG GIAN thật sự được commit tạm để merge_profile.py đọc
    — chỉ có defs cần thiết (barClip) + content fragment, KHÔNG có nền
    riêng, tránh việc merge script lỡ nhặt phải gradient chỉ dùng cho
    xem thử độc lập (render_svg)."""
    fragment_xml, defs_xml, content_height = render_fragment(stats)
    return f"""<svg width="1200" height="{content_height:.0f}"
     viewBox="0 0 1200 {content_height:.0f}"
     xmlns="http://www.w3.org/2000/svg">
  <defs>
    {defs_xml}
  </defs>
  {fragment_xml}
</svg>
"""


def main():
    user = fetch_data()
    stats = compute_stats(user)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "github-stats.svg")

    svg = render_intermediate(stats)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Đã ghi {out_path}")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    main()