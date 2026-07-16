#!/usr/bin/env python3
"""
merge_profile.py — gộp terminal.svg + github-stats.svg + snake.svg
thành 1 file duy nhất assets/profile.svg, với 2 thanh lệnh nối tiếp
("PS> github-stats", "PS> snake") mô phỏng một phiên terminal liền
mạch: gõ lệnh xong thì khối tương ứng bên dưới mới "được gọi ra".

Kỹ thuật: dùng SMIL syncbase timing (begin="id.begin+Xs") cho nội
dung bên trong github-stats — vì các animate trong đó là one-shot
(chạy 1 lần rồi đứng yên), nên phải neo theo thời điểm được gọi,
không thể dùng mốc tuyệt đối cố định lúc build. Snake.svg lặp vô hạn
(repeatCount="indefinite") nên chỉ cần bọc fade-in khi được gọi, giữ
nguyên animate bên trong.

Chạy: python3 merge_profile.py
"""

import re
import xml.etree.ElementTree as ET

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

FONT = "'Courier New', Courier, monospace"
CHAR_W = 24 * 0.6  # 14.4px — advance width Courier New tại font-size 24

# Mốc bắt đầu thanh lệnh 1 ("github-stats"): CỐ ĐỊNH theo yêu cầu — vì
# terminal.svg do người dùng tự canh, khung cuối của họ là 28s.
T_CONNECTOR_1_START = 28.0
SETTLE_BUFFER = 0.8     # thời gian chờ sau khi gõ xong + cursor nháy, trước khi "gọi" khối bên dưới
GAP_AFTER_SECTION = 1.5  # thời gian nghỉ sau khi 1 khối chạy xong animate, trước khi gõ lệnh tiếp theo

BEGIN_ATTR_RE = re.compile(r'begin="(\d+(?:\.\d+)?)s"')


def read_root(path):
    return ET.parse(path).getroot()


def get_dimensions(root):
    vb = root.get("viewBox")
    if vb:
        _, _, w, h = [float(v) for v in vb.split()]
        return w, h
    w = float(re.sub(r"[^\d.]", "", root.get("width", "0")) or 0)
    h = float(re.sub(r"[^\d.]", "", root.get("height", "0")) or 0)
    return w, h


def inner_xml(root):
    return "".join(ET.tostring(child, encoding="unicode") for child in root)


def namespace_ids(xml_str, prefix):
    """Đổi id="..." thành "{prefix}-..." và cập nhật mọi url(#id)/href
    trỏ tới id đó, tránh xung đột giữa 3 phần khi gộp chung 1 file."""
    ids = set(re.findall(r'id="([^"]+)"', xml_str))
    for old_id in ids:
        new_id = f"{prefix}-{old_id}"
        xml_str = re.sub(rf'id="{re.escape(old_id)}"', f'id="{new_id}"', xml_str)
        xml_str = xml_str.replace(f"url(#{old_id})", f"url(#{new_id})")
    return xml_str


def max_end_time(xml_str):
    """Tính mốc thời gian animate one-shot cuối cùng hoàn tất (dùng để
    biết khi nào 1 khối đã "chạy xong" và có thể gọi khối kế tiếp).
    Chỉ tính animate/set có begin dạng số tuyệt đối (chưa bị đổi
    thành syncbase), bỏ qua các animate repeatCount="indefinite" vì
    chúng không có điểm "kết thúc" thật sự."""
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
    """Sinh <text> gõ từng ký tự, dùng đúng lưới CHAR_W như terminal.svg
    gốc để giữ spacing nhất quán."""
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


def extend_terminal_with_commands(term_raw_text, t_line5_start):
    """Kéo dài box terminal GỐC của user (không tạo box rời), rồi chèn
    dòng lệnh 'PS> github-stats' vào ngay bên trong — dùng đúng lưới
    ký tự/màu như các dòng lệnh khác trong file để trông liền mạch
    như 1 phiên terminal đang cuộn tiếp. Lệnh 'snake' KHÔNG nằm ở đây
    nữa — nó chuyển sang 1 thanh nối riêng đặt ngay trước phần snake,
    xem build_snake_connector()."""
    OLD_VB_H, NEW_VB_H = 560, 610
    OLD_BOX_H, NEW_BOX_H = 480, 530
    OLD_BG_H, NEW_BG_H = 580, 630
    Y_LINE5 = 555

    text = term_raw_text
    text = text.replace(f'viewBox="0 0 1200 {OLD_VB_H}"',
                         f'viewBox="0 0 1200 {NEW_VB_H}"')
    text = text.replace(f'width="1200" height="{OLD_BG_H}" rx="20"',
                         f'width="1200" height="{NEW_BG_H}" rx="20"')
    text = text.replace(f'width="1040" height="{OLD_BOX_H}" rx="15"',
                         f'width="1040" height="{NEW_BOX_H}" rx="15"')

    root = ET.fromstring(text)

    def command_line_xml(command, y, t_start):
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

    line5_xml, t_stats_trigger = command_line_xml(
        "github-stats", Y_LINE5, t_line5_start)

    return root, line5_xml, t_stats_trigger


def build_snake_connector(t_start, width=1200, height=90):
    """Thanh nối nhỏ đặt ngay sau github-stats, ngay trước snake — chỉ
    chứa dòng lệnh 'PS> snake'. Dùng đúng màu nền/viền (#0f172a /
    #334155) như box terminal và box github-stats để không bị lạc
    tông, dù không cần đủ bộ chrome (3 chấm + label) vì đây chỉ là 1
    thanh mảnh, không phải 1 'cửa sổ' riêng."""
    prompt_svg, t_after_prompt, x_after_prompt = typed_chars(
        "PS>", 40, height / 2 + 8, t_start, color="#38bdf8")
    cmd_svg, t_after_cmd, x_after_cmd = typed_chars(
        "snake", x_after_prompt + CHAR_W, height / 2 + 8, t_after_prompt + 0.3, color="white")
    cursor_x = x_after_cmd + CHAR_W
    cursor_svg = (
        f'<rect x="{cursor_x:.1f}" y="{height/2-12:.1f}" width="12" height="24" '
        f'fill="#38bdf8" opacity="0">'
        f'<animate attributeName="opacity" values="1;0;1" dur="0.4s" '
        f'begin="{t_after_cmd:.2f}s" repeatCount="2"/></rect>'
    )

    svg = (
        f'<rect width="{width}" height="{height}" rx="15" fill="#0f172a" '
        f'stroke="#334155" stroke-width="3"/>'
        f'{prompt_svg}\n{cmd_svg}\n{cursor_svg}'
    )

    t_trigger = t_after_cmd + SETTLE_BUFFER
    return svg, height, t_trigger


def wrap_stats_section(xml_str, trigger_time, trigger_id="stats-trigger"):
    """Bọc nội dung github-stats trong 1 group fade-in tại trigger_time,
    và chuyển MỌI begin='Xs' tuyệt đối bên trong thành syncbase
    'trigger_id.begin+Xs' — để toàn bộ chuỗi animate one-shot bên
    trong chỉ bắt đầu đếm giờ kể từ lúc khối được gọi, không phải từ
    lúc mở file."""
    def shift(m):
        return f'begin="{trigger_id}.begin+{m.group(1)}s"'

    shifted = BEGIN_ATTR_RE.sub(shift, xml_str)

    return (
        f'<g opacity="0">'
        f'<animate id="{trigger_id}" attributeName="opacity" from="0" to="1" '
        f'dur="0.4s" begin="{trigger_time:.2f}s" fill="freeze"/>'
        f'{shifted}'
        f'</g>'
    )


def wrap_snake_section(xml_str, trigger_time, trigger_id="snake-trigger"):
    """Bọc nội dung snake trong 1 group fade-in tại trigger_time. KHÔNG
    dịch giờ bên trong vì snake lặp vô hạn (repeatCount="indefinite")
    — chỉ cần hiện ra đúng lúc, animate bên trong tự chạy tiếp bình
    thường không cần đồng bộ với thời điểm được gọi."""
    return (
        f'<g opacity="0">'
        f'<animate id="{trigger_id}" attributeName="opacity" from="0" to="1" '
        f'dur="0.4s" begin="{trigger_time:.2f}s" fill="freeze"/>'
        f'{xml_str}'
        f'</g>'
    )


def main():
    term_raw_text = open("assets/terminal.svg", encoding="utf-8").read()

    # --- Kéo dài box terminal gốc, chèn dòng lệnh "github-stats" ngay bên trong ---
    term_root, line5_xml, t_stats_trigger = extend_terminal_with_commands(
        term_raw_text, T_CONNECTOR_1_START)

    term_w, term_h = get_dimensions(term_root)
    term_xml = namespace_ids(inner_xml(term_root), "term")
    combined_term_xml = f"{term_xml}\n{line5_xml}"

    # --- Đọc github-stats, tính thời lượng animate one-shot thật của nó ---
    stats_root = read_root("assets/github-stats.svg")
    stats_w, stats_h = get_dimensions(stats_root)
    stats_xml = namespace_ids(inner_xml(stats_root), "stats")
    stats_duration = max_end_time(stats_xml)
    t_stats_done = t_stats_trigger + stats_duration
    stats_wrapped = wrap_stats_section(stats_xml, t_stats_trigger)

    # --- Thanh nối "PS> snake", đặt NGAY TRƯỚC phần snake (không còn
    # nằm trong khung terminal ở trên nữa) ---
    connector_svg, connector_h, t_snake_trigger = build_snake_connector(
        t_stats_done + GAP_AFTER_SECTION)

    snake_root = read_root("assets/snake.svg")
    snake_w, snake_h = get_dimensions(snake_root)
    snake_xml = namespace_ids(inner_xml(snake_root), "snake")
    snake_wrapped = wrap_snake_section(snake_xml, t_snake_trigger)

    print(f"[timing] line5_github-stats@{T_CONNECTOR_1_START:.1f}s  "
          f"stats_trigger@{t_stats_trigger:.2f}s  "
          f"stats_internal_dur={stats_duration:.2f}s  "
          f"stats_done@{t_stats_done:.2f}s  "
          f"connector_snake@{(t_stats_done + GAP_AFTER_SECTION):.2f}s  "
          f"snake_trigger@{t_snake_trigger:.2f}s")

    GAP = 24
    blocks = []
    cursor_y = 0.0
    max_width = max(term_w, stats_w, snake_w, 1200)

    def add_block(width, height, content_xml):
        nonlocal cursor_y
        block = (f'<svg x="0" y="{cursor_y:.1f}" width="{width:.0f}" '
                  f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">'
                  f'{content_xml}</svg>')
        blocks.append(block)
        cursor_y += height + GAP

    add_block(term_w, term_h, combined_term_xml)
    add_block(stats_w, stats_h, stats_wrapped)
    add_block(1200, connector_h, connector_svg)
    add_block(snake_w, snake_h, snake_wrapped)

    total_height = cursor_y - GAP

    merged = f"""<svg width="{max_width:.0f}" height="{total_height:.0f}"
     viewBox="0 0 {max_width:.0f} {total_height:.0f}"
     xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">

{chr(10).join(blocks)}

</svg>
"""

    with open("assets/profile.svg", "w", encoding="utf-8") as f:
        f.write(merged)
    print(f"Đã ghi assets/profile.svg — {len(merged)} ký tự, cao {total_height:.0f}px")


if __name__ == "__main__":
    main()