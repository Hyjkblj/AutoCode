from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(name, size)


def draw_gradient_background(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    top = (18, 20, 28)
    bottom = (34, 36, 46)
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> Tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> List[str]:
    text = text.replace("\n", " ")
    words = list(text)
    lines: List[str] = []
    current = ""
    for ch in words:
        trial = current + ch
        w, _ = measure_text(draw, trial, font)
        if w <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = ch
    if current:
        lines.append(current)
    return lines


def draw_centered_text(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int],
    padding_x: int = 16,
    line_gap: int = 6,
) -> None:
    left, top, right, bottom = box
    lines = wrap_text(draw, text, font, max(20, right - left - padding_x * 2))
    heights = [measure_text(draw, line, font)[1] for line in lines]
    total_h = sum(heights) + line_gap * (len(lines) - 1 if lines else 0)
    y = top + (bottom - top - total_h) // 2
    for i, line in enumerate(lines):
        w, h = measure_text(draw, line, font)
        x = left + (right - left - w) // 2
        draw.text((x, y), line, font=font, fill=fill)
        y += h + (line_gap if i < len(lines) - 1 else 0)


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: Tuple[int, int],
    end: Tuple[int, int],
    color: Tuple[int, int, int],
    width: int = 4,
    head_len: int = 14,
    head_width: int = 10,
) -> None:
    sx, sy = start
    ex, ey = end
    draw.line([start, end], fill=color, width=width)
    if sx == ex and sy == ey:
        return
    dx = ex - sx
    dy = ey - sy
    length = (dx * dx + dy * dy) ** 0.5
    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux
    bx = ex - ux * head_len
    by = ey - uy * head_len
    p1 = (ex, ey)
    p2 = (bx + px * head_width / 2, by + py * head_width / 2)
    p3 = (bx - px * head_width / 2, by - py * head_width / 2)
    draw.polygon([p1, p2, p3], fill=color)


def main() -> None:
    out_path = Path("d:/Develop/Project/AutoCode/docs/diagrams/java-control-plane-security-flow.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = 3800, 1700
    image = Image.new("RGB", (width, height), (20, 20, 26))
    draw = ImageDraw.Draw(image)
    draw_gradient_background(draw, width, height)

    title_font = load_font("msyhbd.ttc", 70)
    subtitle_font = load_font("msyh.ttc", 34)
    node_font = load_font("msyh.ttc", 28)
    branch_font = load_font("msyh.ttc", 24)
    footer_font = load_font("msyh.ttc", 22)

    title = "Java Control Plane + 安全权限真实链路图"
    subtitle = "基于你们当前策略：mTLS分域、JWT/Token双模式、审批上下文强绑定、Java策略链、事务后广播"
    tw, th = measure_text(draw, title, title_font)
    draw.text(((width - tw) // 2, 48), title, font=title_font, fill=(245, 236, 220))
    sw, sh = measure_text(draw, subtitle, subtitle_font)
    draw.text(((width - sw) // 2, 135), subtitle, font=subtitle_font, fill=(203, 206, 216))

    main_nodes = [
        "客户端请求",
        "SecurityFilterChain",
        "Agent mTLS\n分域校验",
        "认证模式\nToken/JWT",
        "方法级授权\nprojectAuthz",
        "审批上下文\n强绑定校验",
        "Sandbox + Java\n策略链校验",
        "TaskService\n事件折叠",
        "WebSocket\n事务后推送",
        "移动端更新\n任务/产物URL",
    ]

    fail_nodes = {
        2: "证书失败\n401/403 + 审计",
        3: "认证失败\n401",
        4: "授权失败\n404/403\n防资源枚举",
        5: "审批不通过\n拒绝执行 + audit",
        6: "策略拒绝\n阻断执行 + 审计",
    }

    box_w = 320
    box_h = 150
    gap = 40
    x0 = 120
    y0 = 420

    box_color = (49, 74, 132)
    box_border = (152, 188, 255)
    fail_color = (118, 49, 58)
    fail_border = (239, 139, 155)
    arrow_color = (230, 231, 238)

    node_boxes: List[Tuple[int, int, int, int]] = []
    for i, text in enumerate(main_nodes):
        left = x0 + i * (box_w + gap)
        top = y0
        right = left + box_w
        bottom = top + box_h
        node_boxes.append((left, top, right, bottom))
        draw.rounded_rectangle((left, top, right, bottom), radius=20, fill=box_color, outline=box_border, width=3)
        draw_centered_text(draw, (left, top, right, bottom), text, node_font, (245, 248, 255))

    for i in range(len(node_boxes) - 1):
        l1, t1, r1, b1 = node_boxes[i]
        l2, t2, r2, b2 = node_boxes[i + 1]
        draw_arrow(
            draw,
            (r1 + 6, (t1 + b1) // 2),
            (l2 - 8, (t2 + b2) // 2),
            color=arrow_color,
            width=5,
        )

    fail_y = 760
    fail_h = 130
    for idx, text in fail_nodes.items():
        left = node_boxes[idx][0] + 20
        right = node_boxes[idx][2] - 20
        top = fail_y
        bottom = top + fail_h
        draw.rounded_rectangle((left, top, right, bottom), radius=16, fill=fail_color, outline=fail_border, width=3)
        draw_centered_text(draw, (left, top, right, bottom), text, branch_font, (255, 236, 239))
        draw_arrow(
            draw,
            ((left + right) // 2, node_boxes[idx][3] + 6),
            ((left + right) // 2, top - 8),
            color=(255, 176, 188),
            width=4,
        )

    # Branch join label
    draw.rounded_rectangle((120, 990, width - 120, 1150), radius=20, fill=(34, 40, 52), outline=(115, 130, 160), width=2)
    summary = (
        "关键保障：审批上下文(action/tool/workspaceRef/inputsHash)一致性校验；"
        "敏感操作先审后执；失败默认拒绝；所有关键路径写入审计与事件日志。"
    )
    draw_centered_text(draw, (140, 1010, width - 140, 1130), summary, branch_font, (224, 231, 242))

    # Footer references
    refs = (
        "参考标准：RFC 6749 / RFC 6750 / RFC 7519 / RFC 8705 | "
        "NIST RBAC (2000) | OWASP Authorization Cheat Sheet"
    )
    rw, rh = measure_text(draw, refs, footer_font)
    draw.text(((width - rw) // 2, height - 80), refs, font=footer_font, fill=(176, 186, 204))

    image.save(out_path, format="PNG")
    print(str(out_path))


if __name__ == "__main__":
    main()

