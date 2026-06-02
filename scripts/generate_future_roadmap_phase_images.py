from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("msyhbd.ttc" if bold else "msyh.ttc", size)


def gradient_bg(img: Image.Image, top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.ImageFont, width: int):
    chars = list(text)
    lines = []
    cur = ""
    for c in chars:
        t = cur + c
        if draw.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = c
    if cur:
        lines.append(cur)
    return lines


def make_phase_image(
    out: Path,
    phase: str,
    title: str,
    subtitle: str,
    bullets: list[str],
) -> None:
    img = Image.new("RGB", (1280, 720), (20, 24, 32))
    gradient_bg(img, (20, 24, 32), (40, 28, 20))
    d = ImageDraw.Draw(img)

    # main card
    d.rounded_rectangle((60, 50, 1220, 670), radius=28, fill=(20, 22, 30), outline=(222, 186, 117), width=4)
    d.rounded_rectangle((90, 90, 1190, 210), radius=22, fill=(56, 44, 30), outline=(240, 212, 156), width=3)

    d.text((120, 118), phase, font=font(44, True), fill=(246, 226, 168))
    d.text((320, 118), title, font=font(46, True), fill=(248, 248, 248))
    d.text((120, 240), subtitle, font=font(34), fill=(223, 228, 238))

    y = 320
    for b in bullets:
        d.ellipse((120, y + 14, 136, y + 30), fill=(245, 201, 115))
        lines = wrap(d, b, font(30), 980)
        for i, line in enumerate(lines):
            d.text((160, y + i * 40), line, font=font(30), fill=(238, 241, 247))
        y += max(54, len(lines) * 40 + 12)

    # badge
    d.rounded_rectangle((900, 560, 1160, 640), radius=16, fill=(31, 66, 122), outline=(134, 182, 255), width=2)
    d.text((932, 585), "AutoCode", font=font(32, True), fill=(230, 241, 255))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def main() -> None:
    out_dir = Path("d:/Develop/Project/AutoCode/docs/diagrams/future-roadmap")
    make_phase_image(
        out_dir / "phase-1-baseline.png",
        "阶段一",
        "控制面与移动端打通",
        "完成任务创建、状态同步、历史任务与产物链路验证",
        [
            "统一服务端口与连接策略，建立基础交互通道",
            "移动端可查看任务状态、事件流与历史产物",
            "初步形成“创建任务-执行-回传”闭环",
        ],
    )
    make_phase_image(
        out_dir / "phase-2-sync-reliability.png",
        "阶段二",
        "双通道状态同步",
        "WebSocket实时推送 + 轮询兜底，降低断连与状态停滞",
        [
            "Token过期后触发重鉴权提示与连接恢复",
            "弱网与切后台场景下维持状态连续性",
            "任务执行过程对用户可见、可跟踪",
        ],
    )
    make_phase_image(
        out_dir / "phase-3-security-approval.png",
        "阶段三",
        "安全权限闭环",
        "认证、鉴权、审批上下文强绑定，关键操作可治理",
        [
            "mTLS分域、JWT/Token双模式兼容",
            "敏感操作先审批再执行，防止上下文漂移",
            "策略链拦截高风险命令并写入审计",
        ],
    )
    make_phase_image(
        out_dir / "phase-4-artifact-url-delivery.png",
        "阶段四",
        "产物托管与URL交付",
        "产物自动托管，移动端返回可点击链接并支持预览",
        [
            "支持短链与分享链接回传，提升交付效率",
            "任务-产物-发布记录关联，便于回溯",
            "发布后用户可直接浏览器访问成果",
        ],
    )
    make_phase_image(
        out_dir / "phase-5-observability-ops.png",
        "阶段五",
        "稳定运营与可观测",
        "建立告警、审计、恢复与运营指标，进入持续优化阶段",
        [
            "租约恢复与失败重试，提升任务完成率",
            "审计链路与事件序列保障可追溯性",
            "形成可复盘、可迭代的工程运营体系",
        ],
    )

    print(str(out_dir))


if __name__ == "__main__":
    main()

