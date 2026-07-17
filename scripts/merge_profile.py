import os
import sys
import re

def generate_terminal(bg_height=1000, box_height=900):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {bg_height}" width="1200" height="{bg_height}">
    <defs>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur"/>
            <feMerge>
                <feMergeNode in="blur"/>
                <feMergeNode in="SourceGraphic"/>
            </feMerge>
        </filter>
    </defs>
    <rect width="1200" height="{bg_height}" fill="#1e1e2e"/>
    <rect x="80" y="60" width="1040" height="{box_height}" rx="12" fill="#0d0d0d" stroke="#3a3a4a" stroke-width="2"/>
    <circle cx="110" cy="90" r="8" fill="#ff5f56"/>
    <circle cx="135" cy="90" r="8" fill="#ffbd2e"/>
    <circle cx="160" cy="90" r="8" fill="#27c93f"/>
    <g transform="translate(100, 130)">
        <!-- Nội dung sẽ được chèn vào đây -->
    </g>
</svg>'''

def wrap_with_trigger(svg_content, trigger_id="trigger", shift_internal=True):
    if shift_internal:
        def replace_begin(match):
            old = match.group(1)
            parts = old.split(';')
            new_parts = []
            for part in parts:
                part = part.strip()
                if part.endswith('s') and part[:-1].replace('.', '').isdigit():
                    new_parts.append(f"{{{{ {trigger_id}.begin + {part} }}}}")
                else:
                    new_parts.append(part)
            return 'begin="' + '; '.join(new_parts) + '"'
        pattern = r'begin="([^"]*)"'
        svg_content = re.sub(pattern, replace_begin, svg_content)
    return svg_content

def merge_profile():
    stats_path = os.path.join("assets", "github-stats.svg")
    snake_path = os.path.join("assets", "snake.svg")
    if not os.path.exists(stats_path):
        print(f"LỖI: Không tìm thấy {stats_path}. Hãy chạy generate_stats.py trước.")
        sys.exit(1)
    if not os.path.exists(snake_path):
        print(f"LỖI: Không tìm thấy {snake_path}.")
        sys.exit(1)

    with open(stats_path, "r", encoding="utf-8") as f:
        stats_svg = f.read()
    with open(snake_path, "r", encoding="utf-8") as f:
        snake_svg = f.read()

    terminal_svg = generate_terminal(bg_height=1100, box_height=1000)

    stats_body = re.sub(r'<svg[^>]*>|</svg>', '', stats_svg).strip()
    snake_body = re.sub(r'<svg[^>]*>|</svg>', '', snake_svg).strip()

    terminal_svg = terminal_svg.replace(
        '<g transform="translate(100, 130)">',
        f'<g transform="translate(100, 130)">\n{stats_body}\n{snake_body}'
    )

    terminal_svg = wrap_with_trigger(terminal_svg, trigger_id="profile_trigger", shift_internal=True)

    with open("assets/profile.svg", "w", encoding="utf-8") as f:
        f.write(terminal_svg)
    print("Đã tạo assets/profile.svg")

if __name__ == "__main__":
    merge_profile()
