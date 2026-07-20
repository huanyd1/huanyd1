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


def extract_css_class_sizes(xml_str):
    """Dò trong <style> các rule dạng .tenclass{...width:Npx;height:Mpx...}
    trả về dict {tenclass: (width, height)}. Platane/snk tối ưu dung
    lượng file bằng cách định nghĩa kích thước chung qua CSS class thay
    vì lặp lại width/height trên từng rect (vd hàng trăm ô grid contribution
    chỉ có x/y, kích thước 12x12 lấy từ CSS .c{...})."""
    sizes = {}
    for m in re.finditer(r'\.([\w-]+)\{([^}]*)\}', xml_str):
        cls, body = m.group(1), m.group(2)
        w_m = re.search(r'width:\s*([\d.]+)px', body)
        h_m = re.search(r'height:\s*([\d.]+)px', body)
        if w_m and h_m:
            sizes[cls] = (float(w_m.group(1)), float(h_m.group(1)))
    return sizes


def compute_rect_bbox(xml_str):
    """Tính bounding box THẬT của các <rect> trong content (ô grid +
    thân rắn) — dùng để scale chính xác thay vì tin vào viewBox khai
    báo của file, vì viewBox có thể có padding/margin dư không phản
    ánh đúng vùng nội dung thật (đã gặp thực tế với Platane/snk: viewBox
    khai báo rộng hơn hẳn so với nơi các ô grid thật sự kết thúc).

    Một số rect (vd ô grid contribution) chỉ khai x/y, KHÔNG khai
    width/height trực tiếp — kích thước lấy từ CSS class dùng chung
    (.c{width:12px;height:12px}) để giảm dung lượng file. Nếu bỏ qua
    những rect này, bounding box sẽ thiếu chính xác — nên cần tra CSS
    làm kích thước mặc định khi rect không khai width/height riêng."""
    css_sizes = extract_css_class_sizes(xml_str)

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    found = False
    for rect_match in re.finditer(r"<rect\b([^>]*)/?>", xml_str):
        attrs = rect_match.group(1)
        x_m = re.search(r'\bx="(-?[\d.]+)"', attrs)
        y_m = re.search(r'\by="(-?[\d.]+)"', attrs)
        w_m = re.search(r'\bwidth="([\d.]+)"', attrs)
        h_m = re.search(r'\bheight="([\d.]+)"', attrs)
        if not (x_m and y_m):
            continue
        x, y = float(x_m.group(1)), float(y_m.group(1))
        if w_m and h_m:
            w, h = float(w_m.group(1)), float(h_m.group(1))
        else:
            # Khong co width/height rieng -> tra CSS class dung chung
            cls_m = re.search(r'class="([^"]*)"', attrs)
            w = h = None
            if cls_m:
                for token in cls_m.group(1).split():
                    if token in css_sizes:
                        w, h = css_sizes[token]
                        break
            if w is None:
                continue  # khong tra duoc kich thuoc tu dau ca -> bo qua rect nay
        min_x, min_y = min(min_x, x), min(min_y, y)
        max_x, max_y = max(max_x, x + w), max(max_y, y + h)
        found = True
    return (min_x, min_y, max_x, max_y) if found else None


def get_viewbox_dimensions(root):
    """Lấy (width, height) thật từ viewBox hoặc width/height attribute
    — dùng cho snake.svg vì đây là output của action bên thứ 3
    (Platane/snk), không theo quy ước data-height mình tự đặt cho file
    tự viết. Grid contribution thật của mỗi người dùng rộng khác nhau
    (tuỳ số tuần lịch sử), nên không thể giả định cố định."""
    vb = root.get("viewBox")
    if vb:
        parts = vb.split()
        if len(parts) == 4:
            return float(parts[2]), float(parts[3])
    w = float(re.sub(r"[^\d.]", "", root.get("width", "0")) or 0)
    h = float(re.sub(r"[^\d.]", "", root.get("height", "0")) or 0)
    return w, h


def extract_fragment(root, content_id):
    """Tìm <g id="{content_id}" data-height="H"> trong root, trả về
    (fragment_xml, height). Nếu không thấy, báo lỗi kèm danh sách id
    thực sự có trong file — giúp chẩn đoán nhanh nếu 2 file bị lệch
    phiên bản với nhau (vd generate_stats.py cũ ghi id khác tên)."""
    found_ids = []
    for g in root.iter():
        gid = g.get("id")
        if gid:
            found_ids.append(gid)
        if gid == content_id:
            height = float(g.get("data-height", "0"))
            return ET.tostring(g, encoding="unicode"), height
    raise ValueError(
        f'Không tìm thấy <g id="{content_id}"> trong file. '
        f'Các id thực sự có trong file: {found_ids or "(không có id nào)"}. '
        f'Khả năng cao generate_stats.py và merge_profile.py đang lệch phiên bản '
        f'với nhau — hãy đảm bảo cả 2 file đều là bản mới nhất.'
    )


def wrap_with_trigger(xml_str, y_offset, trigger_time, trigger_id, shift_internal,
                       scale=1.0, offset_x=0.0, offset_y=0.0):
    """Bọc content trong 1 <g> với transform + opacity trigger. Thứ tự
    transform: translate(0,Y) scale(S) translate(-offset_x,-offset_y)
    — áp dụng offset trước (đưa bounding box thật về gốc 0,0), rồi
    scale, rồi mới dịch xuống vị trí Y cuối cùng. Nếu shift_internal=True
    (stats — animate one-shot), chuyển begin="Xs" tuyệt đối thành
    syncbase 'trigger_id.begin+Xs'. Nếu False (snake — lặp vô hạn),
    giữ nguyên animate bên trong, chỉ cần fade đúng lúc."""
    content = xml_str
    if shift_internal:
        def shift(m):
            return f'begin="{trigger_id}.begin+{m.group(1)}s"'
        content = BEGIN_ATTR_RE.sub(shift, content)

    transform = f"translate(0,{y_offset:.2f})"
    if scale != 1.0:
        transform += f" scale({scale:.4f})"
    if offset_x or offset_y:
        transform += f" translate({-offset_x:.2f},{-offset_y:.2f})"

    return (
        f'<g transform="{transform}" opacity="0">'
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

    # === 3. Snake: output THẬT của Platane/snk (action bên thứ 3) KHÔNG
    # có <g id="content"> bọc sẵn — đó là quy ước mình tự đặt riêng cho
    # github-stats.svg (file mình tự viết). Platane/snk trả về content
    # thuần luôn rồi, nên lấy toàn bộ children trực tiếp. Đo kích thước
    # qua BOUNDING BOX THẬT của các <rect> (ô grid + thân rắn) — KHÔNG
    # dùng viewBox khai báo, vì viewBox có thể có padding dư không
    # phản ánh đúng nơi nội dung thật sự kết thúc (đã gặp thực tế: grid
    # chỉ trải tới x≈600 dù viewBox khai báo rộng ~880).
    snake_root = ET.parse("assets/snake.svg").getroot()
    snake_fragment_xml = "".join(
        ET.tostring(c, encoding="unicode") for c in snake_root)

    bbox = compute_rect_bbox(snake_fragment_xml)
    if bbox:
        bx0, by0, bx1, by1 = bbox
    else:
        # Khong tim thay rect nao (truong hop hy huu) -> fallback ve viewBox
        vb_w, vb_h = get_viewbox_dimensions(snake_root)
        bx0, by0, bx1, by1 = 0.0, 0.0, vb_w, vb_h

    CANVAS_W = 1200
    content_w = bx1 - bx0
    content_h = by1 - by0
    snake_scale = CANVAS_W / content_w if content_w else 1.0
    snake_height = content_h * snake_scale

    snake_fragment_xml = namespace_ids(snake_fragment_xml, "snake")

    print(f"[snake] bbox_that=({bx0:.0f},{by0:.0f})-({bx1:.0f},{by1:.0f})  "
          f"content={content_w:.0f}x{content_h:.0f}  "
          f"scale={snake_scale:.3f}  scaled_height={snake_height:.0f}")

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
        snake_fragment_xml, Y_SNAKE_START, t_snake_trigger, "snake-trigger",
        shift_internal=False, scale=snake_scale, offset_x=bx0, offset_y=by0)

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