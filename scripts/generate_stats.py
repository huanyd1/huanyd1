import requests
import json
import os
import sys
from datetime import datetime

def get_github_stats(username):
    url = f"https://api.github.com/users/{username}"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Lỗi khi lấy dữ liệu: {response.status_code}")
        sys.exit(1)
    data = response.json()
    return {
        "repos": data.get("public_repos", 0),
        "followers": data.get("followers", 0),
        "following": data.get("following", 0),
        "gists": data.get("public_gists", 0),
        "created": data.get("created_at", ""),
    }

def count_up(x, y, value, color, font_size=24, duration=2, font="Arial"):
    begin = 0.5
    values = [str(i) for i in range(0, int(value) + 1, max(1, int(value)//20))]
    if int(value) not in [int(v) for v in values if v.isdigit()]:
        values.append(str(value))
    step_dur = duration / len(values)
    out = []
    for i, v in enumerate(values):
        t_show = begin + i * step_dur
        if i < len(values) - 1:
            t_hide = begin + (i + 1) * step_dur
            out.append(
                f'<text x="{x}" y="{y}" font-size="{font_size}" '
                f'fill="{color}" font-family="{font}" opacity="0">'
                f'<animate attributeName="opacity" from="0" to="1" '
                f'begin="{t_show}s" dur="0.1s" fill="freeze"/>'
                f'<animate attributeName="opacity" from="1" to="0" '
                f'begin="{t_hide}s" dur="0.01s" fill="freeze"/>'
                f'{v}'
                f'</text>'
            )
        else:
            out.append(
                f'<text x="{x}" y="{y}" font-size="{font_size}" '
                f'fill="{color}" font-family="{font}" opacity="0">'
                f'<animate attributeName="opacity" from="0" to="1" '
                f'begin="{t_show}s" dur="0.01s" fill="freeze"/>'
                f'{v}'
                f'</text>'
            )
    return "\n".join(out)

def stat_card(x, y, label, value, color, icon="", font="Arial"):
    return f"""
    <g transform="translate({x}, {y})">
        <rect x="0" y="0" width="200" height="80" rx="8" fill="#1e1e2e" stroke="#3a3a4a" stroke-width="1"/>
        <text x="20" y="30" font-size="14" fill="#a0a0b0" font-family="{font}">{icon} {label}</text>
        {count_up(100, 55, value, color, font_size=28, font=font)}
    </g>
    """

def render_svg(stats):
    colors = {
        "repos": "#38bdf8",
        "followers": "#f472b6",
        "following": "#a78bfa",
        "gists": "#34d399",
    }
    icons = {
        "repos": "📁",
        "followers": "👥",
        "following": "👤",
        "gists": "📄",
    }
    cards = []
    y = 100
    for key in ["repos", "followers", "following", "gists"]:
        cards.append(stat_card(50, y, key.capitalize(), stats[key], colors[key], icons.get(key, "")))
        y += 100

    created_date = datetime.strptime(stats["created"], "%Y-%m-%dT%H:%M:%SZ").strftime("%d/%m/%Y")
    footer = f'<text x="600" y="{y+30}" text-anchor="middle" font-size="14" fill="#6b7280" font-family="Arial">Tham gia từ {created_date}</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" width="1200" height="600">
    <rect width="1200" height="600" fill="#0d0d14"/>
    <text x="600" y="50" text-anchor="middle" font-size="36" fill="#ffffff" font-family="Arial" font-weight="bold">📊 GitHub Stats</text>
    {''.join(cards)}
    {footer}
</svg>"""

def main():
    username = "huanyd1"
    stats = get_github_stats(username)
    svg_content = render_svg(stats)
    os.makedirs("assets", exist_ok=True)
    with open("assets/github-stats.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("Đã tạo assets/github-stats.svg")

if __name__ == "__main__":
    main()
