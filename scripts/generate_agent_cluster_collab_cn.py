from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFont


W, H = 1920, 1080
img = Image.new("RGB", (W, H), (10, 18, 32))
d = ImageDraw.Draw(img)

# Background gradient
for y in range(H):
    t = y / (H - 1)
    r = int(10 * (1 - t) + 26 * t)
    g = int(18 * (1 - t) + 34 * t)
    b = int(32 * (1 - t) + 50 * t)
    d.line([(0, y), (W, y)], fill=(r, g, b))

# Subtle grid
for x in range(0, W, 80):
    d.line([(x, 0), (x, H)], fill=(24, 36, 56), width=1)
for y in range(0, H, 80):
    d.line([(0, y), (W, y)], fill=(24, 36, 56), width=1)

font_title = ImageFont.truetype("msyhbd.ttc", 52)
font_sub = ImageFont.truetype("msyh.ttc", 28)
font_node_title = ImageFont.truetype("msyhbd.ttc", 26)
font_node = ImageFont.truetype("msyh.ttc", 22)
font_small = ImageFont.truetype("msyh.ttc", 20)


def node(x1, y1, x2, y2, title, lines, fill=(35, 58, 97), edge=(134, 176, 255)):
    d.rounded_rectangle((x1, y1, x2, y2), radius=20, fill=fill, outline=edge, width=3)
    d.text((x1 + 18, y1 + 14), title, font=font_node_title, fill=(242, 249, 255))
    yy = y1 + 56
    for line in lines:
        d.text((x1 + 18, yy), line, font=font_node, fill=(216, 230, 248))
        yy += 32


def arrow(x1, y1, x2, y2, color=(220, 232, 255), width=4):
    d.line((x1, y1, x2, y2), fill=color, width=width)
    ang = math.atan2(y2 - y1, x2 - x1)
    length = 16
    spread = 0.55
    p1 = (x2 - length * math.cos(ang - spread), y2 - length * math.sin(ang - spread))
    p2 = (x2 - length * math.cos(ang + spread), y2 - length * math.sin(ang + spread))
    d.polygon([(x2, y2), p1, p2], fill=color)


# Header
title = "AutoCode 项目 Agent 集群协同关系图（参考）"
t_w = d.textlength(title, font=font_title)
d.text(((W - t_w) / 2, 28), title, font=font_title, fill=(236, 244, 255))

subtitle = "移动端任务驱动 → Control Plane 编排 → Java/Python Agent 执行 → 产物托管 URL 回传"
s_w = d.textlength(subtitle, font=font_sub)
d.text(((W - s_w) / 2, 96), subtitle, font=font_sub, fill=(184, 204, 235))

# Nodes
node(80, 190, 440, 360, "移动端 / Web端", ["任务创建与语音输入", "查看状态/审批/产物", "接收可点击 URL"])
node(
    760,
    180,
    1220,
    390,
    "Control Plane (Spring)",
    ["TaskService 状态机折叠", "AgentRegistry + 调度/租约恢复", "Artifacts/HostedSite + Audit"],
)
node(1430, 170, 1830, 350, "Java Agent 节点", ["策略链安全执行", "审批上下文校验", "工具调用与事件回传"])
node(1430, 390, 1830, 570, "Python Agent 节点", ["任务处理与脚本执行", "统一协议回传", "不绕过 Java 安全策略"])
node(
    760,
    450,
    1220,
    640,
    "数据与消息层",
    ["tasks/task_events/approvals/audit/artifacts", "Redis/Rabbit/InMemory 队列", "WebSocket 事务后推送"],
)
node(760, 700, 1220, 900, "产物交付层", ["HostedArtifactSite 托管", "URL/短链生成与分享", "移动端浏览器直达"])
node(80, 760, 440, 920, "安全与治理", ["JWT/Token 双模式", "mTLS 分域强制（agent接口）", "最小权限 + 审计哈希链"])

# Main arrows
arrow(440, 260, 760, 260)
arrow(1220, 250, 1430, 250)
arrow(1220, 300, 1430, 460)
arrow(1430, 300, 1220, 540)
arrow(1430, 500, 1220, 560)
arrow(1000, 390, 1000, 450)
arrow(1000, 640, 1000, 700)
arrow(760, 820, 440, 300)
arrow(440, 840, 760, 820)
arrow(440, 860, 760, 560)

# Labels
d.rounded_rectangle((520, 268, 710, 308), radius=12, fill=(28, 44, 72), outline=(100, 138, 200), width=2)
d.text((540, 278), "REST / WebSocket", font=font_small, fill=(214, 230, 255))

d.rounded_rectangle((1238, 522, 1408, 562), radius=12, fill=(28, 44, 72), outline=(100, 138, 200), width=2)
d.text((1262, 532), "Agent Event", font=font_small, fill=(214, 230, 255))

d.rounded_rectangle((560, 790, 730, 830), radius=12, fill=(28, 44, 72), outline=(100, 138, 200), width=2)
d.text((592, 800), "URL 回传", font=font_small, fill=(214, 230, 255))

# Legend
d.rounded_rectangle((1280, 700, 1840, 910), radius=16, fill=(25, 32, 47), outline=(96, 120, 162), width=2)
d.text((1310, 724), "关键闭环", font=font_node_title, fill=(242, 249, 255))
legend = [
    "1) 任务从移动端进入控制面",
    "2) 控制面按状态机与审批策略编排",
    "3) Java/Python Agent 并行协同执行",
    "4) 事件回流并更新任务状态",
    "5) 产物托管后返回可访问链接",
]
yy = 772
for line in legend:
    d.text((1310, yy), line, font=font_small, fill=(214, 230, 255))
    yy += 30

out = Path("d:/Develop/Project/AutoCode/docs/diagrams/agent-cluster-collaboration-reference.png")
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out, "PNG")
print(out)

