"""Generate a 3-slide progress report PPT for professor presentation."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

DARK = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT = RGBColor(0x00, 0x6D, 0x77)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF0)
BODY_COLOR = RGBColor(0x33, 0x33, 0x33)
MUTED = RGBColor(0x88, 0x88, 0x88)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
W = prs.slide_width
H = prs.slide_height


def set_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(slide, left, top, width, height, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_text(slide, left, top, width, height, text, size=18, bold=False,
             color=BODY_COLOR, align=PP_ALIGN.LEFT, font_name="Calibri"):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.alignment = align
    return tf


def add_bullet_group(slide, left, top, width, items, size=16,
                     color=BODY_COLOR, spacing=Pt(8)):
    txBox = slide.shapes.add_textbox(left, top, width, Inches(5))
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = item
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.name = "Calibri"
        p.space_after = spacing
        p.level = 0


# ── Slide 1: Title ──
s1 = prs.slides.add_slide(prs.slide_layouts[6])  # blank
set_bg(s1, DARK)

add_rect(s1, Inches(0), Inches(0), W, Inches(0.06), ACCENT)

add_text(s1, Inches(0.9), Inches(1.5), Inches(11), Inches(1.2),
         "AI Physics Experiment Platform",
         size=40, bold=True, color=WHITE)

add_text(s1, Inches(0.9), Inches(2.6), Inches(11), Inches(0.8),
         "GPU-Accelerated Physics Lab  \u2014  Browser-Based Interactive Simulation",
         size=20, color=RGBColor(0xAA, 0xCC, 0xCC))

add_rect(s1, Inches(0.9), Inches(3.7), Inches(1.8), Inches(0.04), ACCENT)

add_text(s1, Inches(0.9), Inches(4.2), Inches(10), Inches(0.5),
         "PHY 1002 Physics Laboratory  |  Weekly Progress Report",
         size=16, color=MUTED)

add_text(s1, Inches(0.9), Inches(4.8), Inches(10), Inches(0.5),
         "The Chinese University of Hong Kong, Shenzhen",
         size=14, color=MUTED)

add_text(s1, Inches(0.9), Inches(5.7), Inches(10), Inches(0.5),
         "2026.03.27 \u2013 2026.03.30",
         size=14, color=MUTED)


# ── Slide 2: What I Did ──
s2 = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s2, WHITE)

add_rect(s2, Inches(0), Inches(0), W, Inches(0.06), ACCENT)

add_text(s2, Inches(0.8), Inches(0.4), Inches(10), Inches(0.8),
         "\u672C\u5468\u5DE5\u4F5C\u603B\u7ED3",  # 本周工作总结
         size=32, bold=True, color=DARK)

add_rect(s2, Inches(0.8), Inches(1.15), Inches(1.2), Inches(0.04), ACCENT)

COL_L = Inches(0.8)
COL_R = Inches(6.8)
COL_W = Inches(5.5)

add_text(s2, COL_L, Inches(1.6), COL_W, Inches(0.5),
         "\u2460  \u5E73\u53F0\u642D\u5EFA\u4E0E\u6A21\u578B\u96C6\u6210",  # ① 平台搭建与模型集成
         size=20, bold=True, color=ACCENT)
add_bullet_group(s2, COL_L, Inches(2.15), COL_W, [
    "\u2022  \u62FF\u5230\u5B66\u957F\u63D0\u4F9B\u7684 8 \u4E2A\u5B9E\u9A8C USD 3D \u6A21\u578B",
    # 拿到学长提供的 8 个实验 USD 3D 模型
    "\u2022  \u5C06\u6A21\u578B\u63A5\u5165 Isaac Sim \u7269\u7406\u5F15\u64CE\uFF0C\u89E3\u51B3\u4E86",
    # 将模型接入 Isaac Sim 物理引擎，解决了
    "    \u591A\u8F6E RigidPrim \u521D\u59CB\u5316\u5D29\u6E83\u548C\u7EB9\u7406\u517C\u5BB9\u95EE\u9898",
    # 多轮 RigidPrim 初始化崩溃和纹理兼容问题
], size=15, color=BODY_COLOR)

add_text(s2, COL_L, Inches(3.65), COL_W, Inches(0.5),
         "\u2461  \u5168\u6808\u7CFB\u7EDF\u96C6\u6210",  # ② 全栈系统集成
         size=20, bold=True, color=ACCENT)
add_bullet_group(s2, COL_L, Inches(4.2), COL_W, [
    "\u2022  \u642D\u5EFA React + WebRTC + WebSocket \u5168\u6808\u67B6\u6784",
    # 搭建 React + WebRTC + WebSocket 全栈架构
    "\u2022  \u5B9E\u73B0\u6D4F\u89C8\u5668\u5B9E\u65F6\u89C6\u9891\u63A8\u6D41 + \u5B9E\u9A8C\u53C2\u6570\u63A7\u5236",
    # 实现浏览器实时视频推流 + 实验参数控制
    "\u2022  \u4E00\u952E\u90E8\u7F72\u811A\u672C\uFF0C\u6253\u5F00\u6D4F\u89C8\u5668\u5373\u53EF\u64CD\u4F5C\u5B9E\u9A8C",
    # 一键部署脚本，打开浏览器即可操作实验
], size=15, color=BODY_COLOR)

add_text(s2, COL_R, Inches(1.6), COL_W, Inches(0.5),
         "\u2462  \u5B9E\u9A8C 1 \u6DF1\u5EA6\u5B9E\u73B0",  # ③ 实验 1 深度实现
         size=20, bold=True, color=ACCENT)
add_bullet_group(s2, COL_R, Inches(2.15), COL_W, [
    "\u2022  \u5B8C\u6210\u89D2\u52A8\u91CF\u5B88\u6052\u5B9E\u9A8C\u7684\u5B8C\u6574\u4EA4\u4E92\u5DE5\u4F5C\u6D41",
    # 完成角动量守恒实验的完整交互工作流
    "\u2022  4 \u8BD5\u6B21\u72B6\u6001\u673A: Spin \u2192 Drop \u2192 Record \u2192 Next",
    # 4 试次状态机: Spin → Drop → Record → Next
    "\u2022  \u7CBE\u786E\u7269\u7406\u8BA1\u7B97\uFF08\u8F6C\u52A8\u60EF\u91CF\u3001\u89D2\u52A8\u91CF\u3001\u52A8\u80FD\u3001\u8BEF\u5DEE\u4F20\u64AD\uFF09",
    # 精确物理计算（转动惯量、角动量、动能、误差传播）
], size=15, color=BODY_COLOR)

add_text(s2, COL_R, Inches(3.65), COL_W, Inches(0.5),
         "\u2463  \u5B66\u672F\u7EA7 PDF \u62A5\u544A\u81EA\u52A8\u751F\u6210",
         # ④ 学术级 PDF 报告自动生成
         size=20, bold=True, color=ACCENT)
add_bullet_group(s2, COL_R, Inches(4.2), COL_W, [
    "\u2022  \u4E00\u952E\u751F\u6210\u7B26\u5408\u5B66\u6821\u6A21\u677F\u7684\u5B8C\u6574\u5B9E\u9A8C\u62A5\u544A",
    # 一键生成符合学校模板的完整实验报告
    "\u2022  \u5305\u542B\u5C01\u9762\u3001\u7406\u8BBA\u63A8\u5BFC\u3001\u6570\u636E\u8868\u683C\u3001\u8BEF\u5DEE\u5206\u6790\u3001\u7ED3\u8BBA",
    # 包含封面、理论推导、数据表格、误差分析、结论
    "\u2022  LaTeX \u516C\u5F0F\u6E32\u67D3\uFF0820 \u6761\u65B9\u7A0B\uFF09\uFF0C8 \u5F20\u4E13\u4E1A\u6570\u636E\u8868",
    # LaTeX 公式渲染（20 条方程），8 张专业数据表
], size=15, color=BODY_COLOR)

add_rect(s2, Inches(0.8), Inches(6.1), Inches(11.7), Inches(0.8), LIGHT_GRAY)
add_text(s2, Inches(1.0), Inches(6.2), Inches(11.3), Inches(0.6),
         "\u6838\u5FC3\u6210\u679C\uFF1A\u5B66\u751F\u5728\u6D4F\u89C8\u5668\u4E2D\u64CD\u4F5C\u7269\u7406\u5B9E\u9A8C \u2192 \u5B9E\u65F6\u89C2\u5BDF GPU \u4EFF\u771F\u753B\u9762 \u2192 \u81EA\u52A8\u8BB0\u5F55\u6570\u636E \u2192 \u4E00\u952E\u5BFC\u51FA\u5B66\u672F\u62A5\u544A",
         # 核心成果：学生在浏览器中操作物理实验 → 实时观察 GPU 仿真画面 → 自动记录数据 → 一键导出学术报告
         size=15, bold=True, color=DARK, align=PP_ALIGN.CENTER)


# ── Slide 3: Status & Next Steps ──
s3 = prs.slides.add_slide(prs.slide_layouts[6])
set_bg(s3, WHITE)

add_rect(s3, Inches(0), Inches(0), W, Inches(0.06), ACCENT)

add_text(s3, Inches(0.8), Inches(0.4), Inches(10), Inches(0.8),
         "\u5F53\u524D\u72B6\u6001\u4E0E\u4E0B\u4E00\u6B65\u8BA1\u5212",  # 当前状态与下一步计划
         size=32, bold=True, color=DARK)
add_rect(s3, Inches(0.8), Inches(1.15), Inches(1.2), Inches(0.04), ACCENT)

# --- Status table ---
TABLE_LEFT = Inches(0.8)
TABLE_TOP = Inches(1.6)
TABLE_W = Inches(7.0)
ROW_H = Inches(0.42)

headers = ["\u5B9E\u9A8C", "\u5EFA\u6A21", "\u524D\u7AEF", "\u540E\u7AEF", "PDF"]
col_ws = [Inches(2.6), Inches(0.9), Inches(0.9), Inches(0.9), Inches(0.9)]
data = [
    ["1 \u89D2\u52A8\u91CF\u5B88\u6052", "\u2705", "\u2705", "\u2705", "\u2705"],
    ["2 \u5927\u6446", "\u2705", "\u2705", "\u2705", "\u2014"],
    ["7 \u52A8\u91CF\u5B88\u6052", "\u2705", "\u2705", "\u2014", "\u2014"],
    ["3\u20136, 8 \u5176\u4F59\u4E94\u4E2A", "\u2705", "\U0001F512", "\u2014", "\u2014"],
]

def draw_table_row(slide, y, values, widths, is_header=False):
    x = TABLE_LEFT
    for val, w in zip(values, widths):
        tb = slide.shapes.add_textbox(x, y, w, ROW_H)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.text = val
        p.font.size = Pt(13)
        p.font.bold = is_header
        p.font.color.rgb = WHITE if is_header else BODY_COLOR
        p.font.name = "Calibri"
        p.alignment = PP_ALIGN.CENTER if val != values[0] else PP_ALIGN.LEFT
        x += w

# Header bg
add_rect(s3, TABLE_LEFT, TABLE_TOP, TABLE_W, ROW_H, ACCENT)
draw_table_row(s3, TABLE_TOP, headers, col_ws, is_header=True)

for i, row in enumerate(data):
    y = TABLE_TOP + ROW_H * (i + 1)
    if i % 2 == 1:
        add_rect(s3, TABLE_LEFT, y, TABLE_W, ROW_H, LIGHT_GRAY)
    draw_table_row(s3, y, row, col_ws)

# Bottom border
add_rect(s3, TABLE_LEFT, TABLE_TOP + ROW_H * 5, TABLE_W, Inches(0.025), ACCENT)

# --- Next Steps ---
add_text(s3, Inches(8.4), Inches(1.6), Inches(4.2), Inches(0.5),
         "\u4E0B\u4E00\u6B65\u8BA1\u5212",  # 下一步计划
         size=22, bold=True, color=ACCENT)

add_rect(s3, Inches(8.4), Inches(2.15), Inches(0.8), Inches(0.03), ACCENT)

add_bullet_group(s3, Inches(8.4), Inches(2.5), Inches(4.2), [
    "1.  \u9010\u6B65\u89E3\u9501\u5269\u4F59 5 \u4E2A\u5B9E\u9A8C\u7684",
    # 逐步解锁剩余 5 个实验的
    "     \u670D\u52A1\u7AEF\u7269\u7406\u63A7\u5236\u4E0E\u524D\u7AEF\u4EA4\u4E92",
    # 服务端物理控制与前端交互
    "",
    "2.  \u4E3A\u6BCF\u4E2A\u5B9E\u9A8C\u590D\u7528 PDF \u62A5\u544A\u6846\u67B6\uFF0C",
    # 为每个实验复用 PDF 报告框架，
    "     \u751F\u6210\u5BF9\u5E94\u7684\u5B66\u672F\u62A5\u544A",
    # 生成对应的学术报告
    "",
    "3.  \u63A2\u7D22 VR \u6A21\u5F0F\u96C6\u6210\uFF0C",
    # 探索 VR 模式集成，
    "     \u652F\u6301\u5934\u663E\u6CBF\u6D78\u5F0F\u5B9E\u9A8C\u64CD\u4F5C",
    # 支持头显沉浸式实验操作
], size=15, color=BODY_COLOR, spacing=Pt(3))

# --- Architecture diagram (simplified text version) ---
add_text(s3, Inches(0.8), Inches(4.5), Inches(11.5), Inches(0.5),
         "\u7CFB\u7EDF\u67B6\u6784",  # 系统架构
         size=22, bold=True, color=ACCENT)
add_rect(s3, Inches(0.8), Inches(5.05), Inches(0.8), Inches(0.03), ACCENT)

boxes = [
    (Inches(0.8),  Inches(5.4), Inches(3.2), Inches(1.4),
     "\U0001F310  \u6D4F\u89C8\u5668\u7AEF\nReact + Tailwind\n\u5B9E\u9A8C\u63A7\u5236 \u00B7 \u56FE\u8868 \u00B7 PDF\u751F\u6210"),
    (Inches(4.7),  Inches(5.4), Inches(3.6), Inches(1.4),
     "\u26A1  \u670D\u52A1\u7AEF\nWebRTC \u89C6\u9891\u63A8\u6D41 + WebSocket \u63A7\u5236\nPython \u00B7 Isaac Sim Runtime"),
    (Inches(9.0),  Inches(5.4), Inches(3.5), Inches(1.4),
     "\U0001F3AE  \u7269\u7406\u5F15\u64CE\nNVIDIA Isaac Sim + PhysX 5\nGPU \u52A0\u901F \u00B7 240Hz \u7269\u7406\u4EFF\u771F"),
]

for (l, t, w, h, txt) in boxes:
    shape = add_rect(s3, l, t, w, h, RGBColor(0xF7, 0xFA, 0xFA))
    shape.line.color.rgb = ACCENT
    shape.line.width = Pt(1.2)
    tb = s3.shapes.add_textbox(l + Inches(0.15), t + Inches(0.12), w - Inches(0.3), h - Inches(0.24))
    tf = tb.text_frame
    tf.word_wrap = True
    for j, line in enumerate(txt.split("\n")):
        if j == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(12) if j > 0 else Pt(14)
        p.font.bold = (j == 0)
        p.font.color.rgb = ACCENT if j == 0 else BODY_COLOR
        p.font.name = "Calibri"

# Arrows between boxes
for ax in [Inches(4.15), Inches(8.65)]:
    arrow_tb = s3.shapes.add_textbox(ax, Inches(5.85), Inches(0.5), Inches(0.5))
    p = arrow_tb.text_frame.paragraphs[0]
    p.text = "\u27A1"
    p.font.size = Pt(22)
    p.font.color.rgb = ACCENT
    p.alignment = PP_ALIGN.CENTER


out = "/125090599/progress_report.pptx"
prs.save(out)
print(f"Saved to {out}")
