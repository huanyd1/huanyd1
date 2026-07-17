#!/usr/bin/env python3
"""
merge_profile.py — gộp terminal.svg + github-stats.svg + snake.svg
thành 1 file duy nhất assets/profile.svg, với TOÀN BỘ nội dung nằm
trong CÙNG MỘT khung terminal (1 box, 1 viền, 1 chrome ở đầu) — không
phải 3 "cửa sổ" xếp chồng. Stats/snake được coi như output được lệnh
terminal "in ra", giống ls/cat/ps trong terminal thật.

Cách làm: chỉ có terminal.svg giữ nguyên box/chrome gốc (được kéo dài
cho vừa). github-stats.svg và snake.svg chỉ đóng góp phần NỘI DUNG
thuần (đọc qua <g id="...-content" data-height="...">, không có
canvas/box/nền riêng), được nhúng vào giữa khung terminal bằng
<g transform="translate(0,Y)"> — không tạo <svg> con, không tạo box
mới, để mọi thứ trôi chung 1 hệ toạ độ, 1 khung duy nhất.

Timing: dùng SMIL syncbase (begin="id.begin+Xs") cho stats vì animate
trong đó one-shot (chạy 1 lần rồi đứng yên) — phải neo theo lúc được
gọi. Snake lặp vô hạn nên không cần dịch giờ bên trong, chỉ cần fade
đúng lúc.

Chạy: python3 merge_profile.py
"""

import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

FONT = "'Courier New', Courier, monospace"
CHAR_W = 24 * 0.6  # 14.4px — advance width Courier New tại font-size 24

T_LINE5_START = 28.0     # mốc bắt đầu gõ "github-stats", cố định theo terminal.svg gốc của user
SETTLE_BUFFER = 0.8      # thời gian chờ sau khi gõ xong 1 lệnh + cursor nháy, trước khi "gọi" nội dung
GAP_AFTER_SECTION = 1.5  # thời gian nghỉ sau khi 1 khối chạy xong animate, trước khi gõ lệnh tiếp theo

Y_MARGIN_BEFORE_CONTENT = 45   # khoảng cách từ dòng lệnh xuống nội dung bên dưới
Y_MARGIN_BEFORE_COMMAND = 45   # khoảng cách từ cuối nội dung xuống dòng lệnh tiếp theo
BOX_BOTTOM_PADDING = 30
VIEWBOX_BOTTOM_PADDING = 20
BG_EXTRA_PADDING = 20

BEGIN_ATTR_RE = re.compile(r'begin="(\d+(?:\.\d+)?)s"')


def collect_ids(xml_str):
    return set(re.findall(r'id="([^"]+)"', xml_str))


def apply_id_map(xml_str, id_map):
    for old_id, new_id in id_map.items():
        xml_str = re.sub(rf'id="{re.escape(old_id)}"', f'id="{new_id}"', xml_str)
        xml_str = xml_str.replace(f"url(#{old_id})", f"url(#{new_id})")
    return xml_str


def namespace_ids(xml_str, prefix):
    """Đổi id="..." thành "{prefix}-..." và cập nhật mọi url(#id) trỏ
    tới id đó, tránh xung đột giữa các phần khi gộp chung 1 file."""
    id_map = {old: f"{prefix}-{old}" for old in collect_ids(xml_str)}
    return apply_id_map(xml_str, id_map)


def max_end_time(xml_str):
    """Tính mốc thời gian animate one-shot cuối cùng hoàn tất — dùng để
    biết khi nào 1 khối đã "chạy xong" và có thể gọi khối kế tiếp. Bỏ
    qua animate repeatCount="indefinite" vì không có điểm kết thúc thật."""
    ends = []
    for m in re.finditer(r'<(animate|set)([^>]*)/>', xml_str):
        tag_attrs = m.group(2)
        if 'repeatCount="indefinite"' in tag_attrs:
            continue
        begin_m = re.search(r'begin="(\d+(?:\.\d+)?)s"', tag_attrs)
        dur_m = re.search(r'dur="(\d+(?:\.\d+)?)s"', tag_attrs)
        if begin_m:
            begin = float(begin_m.group(1))
            dur = float(dur_m.group(1)) if dur_m else 0.0
            ends.append(begin + dur)
    return max(ends) if ends else 0.0


def typed_chars(text, x_start, y, begin_start, step=0.1, color="white"):
    """Sinh <text> gõ từng ký tự theo lưới CHAR_W, khớp spacing terminal gốc."""
    out = []
    for i, ch in enumerate(text):
        x = x_start + i * CHAR_W
        begin = begin_start + i * step
        display_ch = "&gt;" if ch == ">" else ch
        out.append(
            f'<text x="{x:.1f}" y="{y}" fill="{color}" font-size="24" '
            f'font-family="{FONT}" opacity="0">{display_ch}'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.06s" '
            f'begin="{begin:.2f}s" fill="freeze"/></text>'
        )
    end_time = begin_start + len(text) * step
    end_x = x_start + len(text) * CHAR_W
    return "\n".join(out), end_time, end_x


def command_line(command, y, t_start):
    """1 dòng 'PS> {command}' tại vị trí y trong hệ toạ độ CHUNG của
    terminal. Trả về (xml, t_trigger) — t_trigger là mốc nên "gọi"
    nội dung phía sau."""
    prompt_svg, t_after_prompt, x_after_prompt = typed_chars(
        "PS>", 120, y, t_start, color="#38bdf8")
    cmd_svg, t_after_cmd, x_after_cmd = typed_chars(
        command, x_after_prompt + CHAR_W, y, t_after_prompt + 0.3, color="white")
    cursor_x = x_after_cmd + CHAR_W
    cursor_svg = (
        f'<rect x="{cursor_x:.1f}" y="{y-20}" width="12" height="24" '
        f'fill="#38bdf8" opacity="0">'
        f'<animate attributeName="opacity" values="1;0;1" dur="0.4s" '
        f'begin="{t_after_cmd:.2f}s" repeatCount="2"/></rect>'
    )
    t_trigger = t_after_cmd + SETTLE_BUFFER
    return f"{prompt_svg}\n{cmd_svg}\n{cursor_svg}", t_trigger


def extract_fragment(root, content_id):
    """Tìm <g id="{content_id}" data-height="H"> trong root, trả về
    (fragment_xml, height)."""
    for g in root.iter():
        if g.get("id") == content_id:
            height = float(g.get("data-height", "0"))
            return ET.tostring(g, encoding="unicode"), height
    raise ValueError(f'Không tìm thấy <g id="{content_id}"> trong file')


def wrap_with_trigger(xml_str, y_offset, trigger_time, trigger_id, shift_internal):
    """Bọc content trong <g transform="translate(0,Y)" opacity="0"> với
    1 animate trigger tại trigger_time. Nếu shift_internal=True (dùng
    cho stats — animate one-shot), chuyển mọi begin="Xs" tuyệt đối bên
    trong thành syncbase 'trigger_id.begin+Xs' để chuỗi animate chỉ
    bắt đầu đếm giờ từ lúc được gọi. Nếu False (snake — lặp vô hạn),
    giữ nguyên animate bên trong, chỉ cần fade đúng lúc."""
    content = xml_str
    if shift_internal:
        def shift(m):
            return f'begin="{trigger_id}.begin+{m.group(1)}s"'
        content = BEGIN_ATTR_RE.sub(shift, content)

    return (
        f'<g transform="translate(0,{y_offset:.1f})" opacity="0">'
        f'<animate id="{trigger_id}" attributeName="opacity" from="0" to="1" '
        f'dur="0.4s" begin="{trigger_time:.2f}s" fill="freeze"/>'
        f'{content}'
        f'</g>'
    )


def main():
    # === 1. Terminal gốc: giữ nguyên nội dung boot sequence ===
    term_raw = open("assets/terminal.svg", encoding="utf-8").read()
    term_root = ET.fromstring(term_raw)
    term_inner = "".join(ET.tostring(c, encoding="unicode") for c in term_root)
    term_inner = namespace_ids(term_inner, "term")

    # === 2. Stats: gộp defs + fragment thành 1 khối TRƯỚC khi đổi id,
    # để tham chiếu url(#barClip) không bị lệch tên với định nghĩa ===
    stats_root = ET.parse("assets/github-stats.svg").getroot()
    stats_defs_el = stats_root.find(f"{{{SVG_NS}}}defs")
    stats_defs_xml = (
        "".join(ET.tostring(c, encoding="unicode") for c in stats_defs_el)
        if stats_defs_el is not None else ""
    )
    stats_fragment_xml, stats_height = extract_fragment(stats_root, "content")
    stats_combined = stats_defs_xml + stats_fragment_xml
    stats_duration = max_end_time(stats_combined)
    stats_combined = namespace_ids(stats_combined, "stats")

    # === 3. Snake: chỉ có fragment, không có defs riêng (đã bỏ khi xoá nền) ===
    snake_root = ET.parse("assets/snake.svg").getroot()
    snake_fragment_xml, snake_height = extract_fragment(snake_root, "content")
    snake_fragment_xml = namespace_ids(snake_fragment_xml, "snake")

    # === 4. Tính toạ độ Y cho từng phần theo đúng chiều cao THẬT ===
    Y_LINE5 = 555
    line5_xml, t_stats_trigger = command_line("github-stats", Y_LINE5, T_LINE5_START)

    Y_STATS_START = Y_LINE5 + Y_MARGIN_BEFORE_CONTENT
    Y_STATS_END = Y_STATS_START + stats_height
    t_stats_done = t_stats_trigger + stats_duration

    Y_LINE6 = Y_STATS_END + Y_MARGIN_BEFORE_COMMAND
    t_line6_start = t_stats_done + GAP_AFTER_SECTION
    line6_xml, t_snake_trigger = command_line("snake", Y_LINE6, t_line6_start)

    Y_SNAKE_START = Y_LINE6 + Y_MARGIN_BEFORE_CONTENT
    Y_SNAKE_END = Y_SNAKE_START + snake_height

    print(f"[timing] line5@{T_LINE5_START:.1f}s  stats_trigger@{t_stats_trigger:.2f}s  "
          f"stats_dur={stats_duration:.2f}s  stats_done@{t_stats_done:.2f}s  "
          f"line6@{t_line6_start:.2f}s  snake_trigger@{t_snake_trigger:.2f}s")
    print(f"[layout] Y_STATS={Y_STATS_START:.0f}-{Y_STATS_END:.0f}  "
          f"Y_LINE6={Y_LINE6:.0f}  Y_SNAKE={Y_SNAKE_START:.0f}-{Y_SNAKE_END:.0f}")

    # === 5. Kích thước box/canvas cuối cùng, bao trọn mọi nội dung ===
    BOX_TOP = 60
    BOX_BOTTOM = Y_SNAKE_END + BOX_BOTTOM_PADDING
    BOX_HEIGHT = BOX_BOTTOM - BOX_TOP
    VIEWBOX_H = BOX_BOTTOM + VIEWBOX_BOTTOM_PADDING
    BG_H = VIEWBOX_H + BG_EXTRA_PADDING

    # === 6. Bọc stats/snake với trigger + dịch toạ độ Y ===
    stats_wrapped = wrap_with_trigger(
        stats_combined, Y_STATS_START, t_stats_trigger, "stats-trigger", shift_internal=True)
    snake_wrapped = wrap_with_trigger(
        snake_fragment_xml, Y_SNAKE_START, t_snake_trigger, "snake-trigger", shift_internal=False)

    # === 7. Kéo dài đúng box/nền GỐC bên trong terminal (không tạo box mới) ===
    term_inner = term_inner.replace(
        'width="1200" height="580" rx="20"', f'width="1200" height="{BG_H:.0f}" rx="20"')
    term_inner = term_inner.replace(
        'width="1040" height="480" rx="15"', f'width="1040" height="{BOX_HEIGHT:.0f}" rx="15"')

    # === 8. Ghép tất cả vào 1 <svg> duy nhất, 1 hệ toạ độ, 1 khung ===
    merged = f"""<svg width="1200" height="{VIEWBOX_H:.0f}"
     viewBox="0 0 1200 {VIEWBOX_H:.0f}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">

{term_inner}
{line5_xml}
{stats_wrapped}
{line6_xml}
{snake_wrapped}

</svg>
"""

    with open("assets/profile.svg", "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"Đã ghi assets/profile.svg — {len(merged)} ký tự, cao {VIEWBOX_H:.0f}px")


if __name__ == "__main__":
    main()