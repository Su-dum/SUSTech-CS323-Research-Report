#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze.py — 把 collect_corpus.py 产出的 corpus.csv 变成图与统计。

三条产出线
----------
1. 层间转换结构：Conversion 目录解析出的 (源方言 -> 目标方言) 聚合到 (源层 -> 目标层)，
   回答"层与层之间的转换如何分布、是否收敛"。
2. 方言共现结构：同一测试文件里同时出现哪些方言，回答"哪些层总是绑定出现"。
3. 成本模型：把测得的层间边数 |E| 代入"成对适配 vs 分层共享"的成本公式，
   并引入共享层采纳率 p，画出两种组织方式的成本随规模变化的关系。

依赖
----
图默认输出 SVG（纯标准库，无 matplotlib）。
加 --preview-png 会用 Pillow（若已安装）额外输出 PNG，便于在聊天/文档里快速预览；
SVG 才是交付给论文的版本。

用法
----
    python tools/analyze.py --corpus out/corpus.csv --outdir out
    python tools/analyze.py --corpus out/corpus.csv --outdir out \
        --n-frameworks 8 --n-backends 6 --adoption 0.6 --preview-png

注意
----
脚本只输出**描述性统计**。findings.json 里所有 interpretation 字段故意留空，
必须由报告作者填写——这是本实验的学术判断部分。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from html import escape
from pathlib import Path

LAYER_COLORS = ["#4E79A7", "#59A14F", "#F28E2B", "#B07AA1", "#E15759", "#76B7B2"]


# ---------------------------------------------------------------- SVG / PNG 双后端


class SVG:
    """记录绘图原语，可导出为 SVG（交付用）或 PNG（预览用）。"""

    def __init__(self, w: int, h: int, bg: str = "#ffffff",
                 font_family: str = "Helvetica,Arial,sans-serif"):
        self.w, self.h, self.bg = w, h, bg
        self.font_family = font_family
        self.ops: list[tuple[str, dict]] = []

    def rect(self, x, y, w, h, fill, stroke="none", sw=1, rx=0, opacity=1.0):
        self.ops.append(("rect", dict(x=x, y=y, w=w, h=h, fill=fill, stroke=stroke,
                                      sw=sw, rx=rx, op=opacity)))

    def line(self, x1, y1, x2, y2, stroke="#333", sw=1, dash=None, opacity=1.0):
        self.ops.append(("line", dict(x1=x1, y1=y1, x2=x2, y2=y2, stroke=stroke, sw=sw,
                                      dash=dash, op=opacity)))

    def bezier(self, x1, y1, c1x, c1y, c2x, c2y, x2, y2, stroke="#333", sw=1, opacity=1.0):
        self.ops.append(("bez", dict(x1=x1, y1=y1, c1x=c1x, c1y=c1y, c2x=c2x, c2y=c2y,
                                     x2=x2, y2=y2, stroke=stroke, sw=sw, op=opacity)))

    def polyline(self, pts, stroke="#333", sw=1, dash=None):
        self.ops.append(("poly", dict(pts=list(pts), stroke=stroke, sw=sw, dash=dash)))

    def text(self, x, y, s, size=11, anchor="start", color="#222", weight="normal",
             rotate=None, opacity=1.0, family=None):
        self.ops.append(("text", dict(x=x, y=y, s=str(s), size=size, anchor=anchor,
                                      color=color, weight=weight, rotate=rotate, op=opacity,
                                      family=family)))

    # -- 导出 SVG

    def save(self, path: Path):
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" font-family="{self.font_family}">',
               f'<rect width="{self.w}" height="{self.h}" fill="{self.bg}"/>']
        for kind, a in self.ops:
            if kind == "rect":
                out.append(
                    f'<rect x="{a["x"]:.1f}" y="{a["y"]:.1f}" width="{a["w"]:.1f}" '
                    f'height="{a["h"]:.1f}" rx="{a["rx"]}" fill="{a["fill"]}" '
                    f'stroke="{a["stroke"]}" stroke-width="{a["sw"]}" opacity="{a["op"]}"/>')
            elif kind == "line":
                d = f' stroke-dasharray="{a["dash"]}"' if a["dash"] else ""
                out.append(f'<line x1="{a["x1"]:.1f}" y1="{a["y1"]:.1f}" x2="{a["x2"]:.1f}" '
                           f'y2="{a["y2"]:.1f}" stroke="{a["stroke"]}" stroke-width="{a["sw"]}" '
                           f'opacity="{a["op"]}"{d}/>')
            elif kind == "bez":
                out.append(
                    f'<path d="M {a["x1"]:.1f} {a["y1"]:.1f} C {a["c1x"]:.1f} {a["c1y"]:.1f} '
                    f'{a["c2x"]:.1f} {a["c2y"]:.1f} {a["x2"]:.1f} {a["y2"]:.1f}" fill="none" '
                    f'stroke="{a["stroke"]}" stroke-width="{a["sw"]}" opacity="{a["op"]}" '
                    f'stroke-linecap="round"/>')
            elif kind == "poly":
                d = " ".join(f"{'M' if i == 0 else 'L'} {x:.1f} {y:.1f}"
                             for i, (x, y) in enumerate(a["pts"]))
                da = f' stroke-dasharray="{a["dash"]}"' if a["dash"] else ""
                out.append(f'<path d="{d}" fill="none" stroke="{a["stroke"]}" '
                           f'stroke-width="{a["sw"]}"{da}/>')
            elif kind == "text":
                tr = (f' transform="rotate({a["rotate"]} {a["x"]:.1f} {a["y"]:.1f})"'
                      if a["rotate"] is not None else "")
                out.append(
                    f'<text x="{a["x"]:.1f}" y="{a["y"]:.1f}" font-size="{a["size"]}" '
                    f'text-anchor="{a["anchor"]}" fill="{a["color"]}" '
                    f'font-weight="{a["weight"]}" opacity="{a["op"]}"'
                    + (f' font-family="{a["family"]}"' if a.get("family") else "")
                    + f'{tr}>{escape(a["s"])}</text>')
        out.append("</svg>")
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        print(f"     图：{path}")

    # -- 导出 PNG（仅预览）

    def save_png(self, path: Path):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            print("     [跳过 PNG 预览] 未安装 Pillow")
            return
        import os

        if "mono" in self.font_family.lower() or "consol" in self.font_family.lower():
            font_paths = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
        else:
            font_paths = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        fpath = next((p for p in font_paths if os.path.exists(p)), None)
        cjk_paths = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf"]
        cjk_path = next((p for p in cjk_paths if os.path.exists(p)), fpath)

        def _load(path, sz):
            if path:
                try:
                    return ImageFont.truetype(path, int(sz))
                except OSError:
                    pass
            return ImageFont.load_default()

        def font(sz, family=None):
            # 逐条：等宽文字用等宽字体，其余走 CJK 字体
            if family and ("mono" in family.lower() or "consol" in family.lower()):
                return _load(fpath, sz)
            return _load(cjk_path, sz)

        img = Image.new("RGBA", (self.w, self.h), self.bg)
        for kind, a in self.ops:
            layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)

            def col(c, op=1.0):
                if c in ("none", None):
                    return None
                h = c.lstrip("#")
                if len(h) == 3:                      # 支持 #333 这类三位简写
                    h = "".join(ch * 2 for ch in h)
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(255 * op))

            if kind == "rect":
                xy = [a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]]
                d.rectangle(xy, fill=col(a["fill"], a["op"]),
                            outline=col(a["stroke"], a["op"]) if a["stroke"] != "none" else None,
                            width=max(1, int(a["sw"])))
            elif kind == "line":
                d.line([a["x1"], a["y1"], a["x2"], a["y2"]],
                       fill=col(a["stroke"], a["op"]), width=max(1, int(a["sw"])))
            elif kind == "bez":
                pts = []
                for i in range(33):
                    t = i / 32
                    mt = 1 - t
                    x = (mt ** 3) * a["x1"] + 3 * mt * mt * t * a["c1x"] + \
                        3 * mt * t * t * a["c2x"] + t ** 3 * a["x2"]
                    y = (mt ** 3) * a["y1"] + 3 * mt * mt * t * a["c1y"] + \
                        3 * mt * t * t * a["c2y"] + t ** 3 * a["y2"]
                    pts.append((x, y))
                d.line(pts, fill=col(a["stroke"], a["op"]), width=max(1, int(a["sw"])),
                       joint="curve")
            elif kind == "poly":
                d.line([tuple(p) for p in a["pts"]], fill=col(a["stroke"]),
                       width=max(1, int(a["sw"])), joint="curve")
            elif kind == "text":
                f = font(a["size"], a.get("family"))
                s = a["s"]
                try:
                    tw = d.textlength(s, font=f)
                except Exception:
                    tw = len(s) * a["size"] * 0.55
                tx = a["x"] - (tw if a["anchor"] == "end" else tw / 2 if a["anchor"] == "middle" else 0)
                ty = a["y"] - a["size"] * 0.8
                if a["rotate"] is not None:
                    tmp = Image.new("RGBA", (int(tw) + 8, int(a["size"] * 2), ), (0, 0, 0, 0))
                    ImageDraw.Draw(tmp).text((4, 2), s, font=f,
                                             fill=col(a["color"], a["op"]))
                    tmp = tmp.rotate(-a["rotate"], expand=True, resample=Image.BICUBIC)
                    layer.alpha_composite(tmp, (int(a["x"]), int(a["y"]) - tmp.height))
                else:
                    d.text((tx, ty), s, font=f, fill=col(a["color"], a["op"]))
            img = Image.alpha_composite(img, layer)
        img.convert("RGB").save(path)
        print(f"     PNG 预览：{path}")


def heat_color(t: float, lo="#f7fbff", hi="#08306b") -> str:
    t = max(0.0, min(1.0, t))

    def rgb(c):
        return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)

    a, b = rgb(lo), rgb(hi)
    return "#{:02x}{:02x}{:02x}".format(*[round(a[i] + (b[i] - a[i]) * t) for i in range(3)])


def fmt_num(n: float) -> str:
    return f"{n:,.0f}" if abs(n) >= 10 else f"{n:.2f}"


# ---------------------------------------------------------------- 装载


def load(corpus_path: Path, cfg: dict):
    rows = []
    with corpus_path.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            r["n_ops"] = int(r["n_ops"])
            r["n_lines"] = int(r["n_lines"])
            ds = {}
            for item in (r["dialects"] or "").split(";"):
                if ":" in item:
                    k, v = item.rsplit(":", 1)
                    ds[k] = int(v)
            r["_dialects"] = ds
            rows.append(r)

    layers = {L["id"]: L for L in cfg["layers"]}
    order = sorted(layers.values(), key=lambda x: x["order"])
    ns2layer = {}
    for L in layers.values():
        for ns in L["dialects"]:
            ns2layer[ns] = L["id"]
    cross = set(cfg.get("crosslayer", {}).get("dialects", []))
    return rows, order, ns2layer, cross


# ---------------------------------------------------------------- 图 1


def fig_funnel(path, order, layer_edges, layer_out, layer_in, png):
    W, H = 900, 540
    svg = SVG(W, H)
    svg.text(24, 30, "层间转换强度（按抽象层聚合）", size=15, weight="bold")
    svg.text(24, 50, "线宽 ∝ 该层间转换对应的 Conversion 测试文件数；弧线自左（源层）指向右（目标层）",
             size=10.5, color="#666")

    n = len(order)
    box_h, gap = 44, 40
    total_h = n * box_h + (n - 1) * gap
    top = (H - total_h) / 2 + 26
    left_x, left_w = 66, 168
    right_x = W - 66 - left_w
    ids = [L["id"] for L in order]
    cy = {}
    box_top_y = {}
    for i, L in enumerate(order):
        y = top + i * (box_h + gap)
        cy[L["id"]] = y + box_h / 2
        box_top_y[L["id"]] = y
        for x in (left_x, right_x):
            svg.rect(x, y, left_w, box_h, "#f5f7fa", stroke="#d5dbe3", rx=6)
            svg.text(x + left_w / 2, y + box_h / 2 - 2, L["label_zh"], size=11.5,
                     anchor="middle", weight="bold")
            svg.text(x + left_w / 2, y + box_h / 2 + 13, L["id"], size=9.5,
                     anchor="middle", color="#8a94a6")

    max_c = max(layer_edges.values()) if layer_edges else 1
    x1, x2 = left_x + left_w, right_x
    mid = (x1 + x2) / 2
    for (src, dst), c in sorted(layer_edges.items(), key=lambda kv: kv[1]):
        if c <= 0:
            continue
        color = LAYER_COLORS[ids.index(src) % len(LAYER_COLORS)]
        wdt = 1.4 + 12 * math.sqrt(c / max_c)
        y1, y2 = cy[src], cy[dst]
        if src == dst:
            # 层内下降：在框顶画小凸起，避免被误读为跨层流动
            bt = box_top_y[src]
            cxm = left_x + left_w / 2
            svg.bezier(cxm - 34, bt, cxm - 20, bt - 20, cxm + 20, bt - 20, cxm + 34, bt,
                       stroke=color, sw=wdt, opacity=0.65)
            svg.text(left_x + 10, bt + box_h - 7, f"层内 {c}", size=9, color="#8a94a6")
        else:
            svg.bezier(x1, y1, mid, y1, mid, y2, x2, y2, stroke=color, sw=wdt, opacity=0.42)

    svg.text(left_x + left_w / 2, top - 14, "源层（括号内为出度）", size=10.5, anchor="middle",
             color="#555", weight="bold")
    svg.text(right_x + left_w / 2, top - 14, "目标层（括号内为入度）", size=10.5,
             anchor="middle", color="#555", weight="bold")
    for L in order:
        y = cy[L["id"]]
        svg.text(left_x - 10, y + 4, f"({layer_out.get(L['id'], 0)})", size=10,
                 anchor="end", color="#5a6472")
        svg.text(right_x + left_w + 10, y + 4, f"({layer_in.get(L['id'], 0)})", size=10,
                 color="#5a6472")
    svg.save(path)
    if png:
        svg.save_png(path.with_suffix(".png"))


# ---------------------------------------------------------------- 图 2


def fig_cooccurrence(path, cooc, df, topk, png):
    tops = [d for d, _ in df.most_common(topk)]
    cell = 40
    m_left, m_top = 156, 138
    W = m_left + cell * len(tops) + 40
    H = m_top + cell * len(tops) + 34
    svg = SVG(W, H)
    svg.text(24, 30, "方言共现矩阵（同一测试文件内同时出现）", size=15, weight="bold")
    svg.text(24, 50, f"取文档频次最高的 {len(tops)} 个方言；非对角格为双方的共现文件数，颜色取对数刻度",
             size=10.5, color="#666")
    svg.text(24, 66, "对角线灰格为该方言自身的文档频次，量纲不同，不参与色阶",
             size=10.5, color="#666")
    mx = max([cooc.get((a, b), 0) for a in tops for b in tops if a != b] + [1])
    for i, a in enumerate(tops):
        svg.text(m_left - 8, m_top + i * cell + cell * 0.68, a, size=10.5, anchor="end")
        for j, b in enumerate(tops):
            x, y = m_left + j * cell, m_top + i * cell
            if a == b:
                # 对角线是自身文档频次，量纲不同，用中性灰并排除在色阶之外
                svg.rect(x, y, cell - 1, cell - 1, "#eceff3", rx=2)
                svg.text(x + cell / 2 - 0.5, y + cell * 0.68, df.get(a, 0), size=8.5,
                         anchor="middle", color="#8a94a6")
                continue
            c = cooc.get((a, b), 0)
            t = math.log1p(c) / math.log1p(mx) if mx > 0 else 0
            svg.rect(x, y, cell - 1, cell - 1, heat_color(t), rx=2)
            if c:
                svg.text(x + cell / 2 - 0.5, y + cell * 0.68, c, size=8.5, anchor="middle",
                         color="#ffffff" if t > 0.55 else "#222222")
    for j, b in enumerate(tops):
        svg.text(m_left + j * cell + cell * 0.42, m_top - 8, b, size=10.5,
                 anchor="end", rotate=-55)
    svg.save(path)
    if png:
        svg.save_png(path.with_suffix(".png"))


# ---------------------------------------------------------------- 图 3


def fig_cost(path, E, N, M, p, png):
    n_max = 40
    xs = list(range(1, n_max + 1))
    pair = [n * M for n in xs]
    lay_full = [E + n + M for n in xs]
    lay_p = [E + n + M + (1 - p) * n * M for n in xs]
    ymax = max(pair + lay_p) * 1.06
    W, H = 900, 470
    left, right, top, bot = 92, 470, 78, 58
    plot_w, plot_h = right - left, H - top - bot
    svg = SVG(W, H)
    svg.text(24, 30, "成本随规模的变化：成对适配 vs 分层共享", size=15, weight="bold")
    svg.text(24, 50, f"|E|={E}（实测层间边数），M={M}（后端数），p={p:.2f}（共享层采纳率）；本图固定 M，横轴扫 N",
             size=10.5, color="#666")

    def sx(x):
        return left + (x - 1) / (n_max - 1) * plot_w

    def sy(y):
        return top + plot_h - y / ymax * plot_h

    for i in range(5):
        yy = top + plot_h * i / 4
        svg.line(left, yy, right, yy, stroke="#eaeef3", sw=1)
        svg.text(left - 8, yy + 4, fmt_num(ymax * (1 - i / 4)), size=9.5, anchor="end",
                 color="#888")
    for n in range(5, n_max + 1, 5):
        svg.line(sx(n), top, sx(n), top + plot_h, stroke="#f3f6f9", sw=1)
        svg.text(sx(n), top + plot_h + 16, n, size=9.5, anchor="middle", color="#888")
    svg.line(left, top + plot_h, right, top + plot_h, stroke="#333", sw=1.2)
    svg.line(left, top, left, top + plot_h, stroke="#333", sw=1.2)
    svg.text(left + plot_w / 2, H - 16, "框架数量 N", size=11, anchor="middle", weight="bold")
    svg.text(24, top + plot_h / 2, "归一化成本", size=11, anchor="middle", weight="bold",
             rotate=-90)

    for ys, color, dash in ((pair, "#E15759", None), (lay_p, "#F28E2B", "6 4"),
                            (lay_full, "#4E79A7", None)):
        svg.polyline(list(zip([sx(x) for x in xs], [sy(y) for y in ys])),
                     stroke=color, sw=2.2, dash=dash)

    for i, (color, label, dash) in enumerate([
        ("#E15759", "成对适配：N×M", None),
        ("#4E79A7", "分层共享，p=1.0：|E|+N+M", None),
        ("#F28E2B", f"分层共享，p={p:.2f}：|E|+N+M+(1−p)·N·M", "6 4"),
    ]):
        y = top + 20 + i * 22
        svg.line(left + 14, y, left + 46, y, stroke=color, sw=3, dash=dash)
        svg.text(left + 54, y + 4, label, size=10.5)

    # 交叉点：解 (1-p)·N·M = |E|+N+M，得 N* = (|E|+M)/(p·M−1)
    denom = p * M - 1
    if denom > 1e-9:
        n_star = (E + M) / denom
        if 1 <= n_star <= n_max:
            svg.line(sx(n_star), top + 86, sx(n_star), top + plot_h - 4, stroke="#9aa4b2",
                     sw=1.3, dash="4 3")
            svg.text(sx(n_star) + 5, top + plot_h - 10, f"N*≈{n_star:.1f} 处分层开始占优",
                     size=9.5, color="#6b7280")

    # 右图：(N, M) 平面上的成本比
    hx0, hy0 = right + 70, top + 12
    n_cols, n_rows, cw, ch = 10, 6, 26, 22
    svg.text(hx0, hy0 - 10, "分层/成对 成本比（越深越占优）", size=10.5, weight="bold")
    ratios = []
    for mi in range(n_rows):
        m = 2 + mi * 2
        for ni in range(n_cols):
            n = 2 + ni * 4
            ratios.append((E + n + m + (1 - p) * n * m) / (n * m))
    rmin, rmax = min(ratios), max(ratios)
    for mi in range(n_rows):
        m = 2 + mi * 2
        svg.text(hx0 - 6, hy0 + mi * ch + ch * 0.72, m, size=9, anchor="end", color="#888")
        for ni in range(n_cols):
            n = 2 + ni * 4
            r = (E + n + m + (1 - p) * n * m) / (n * m)
            t = (r - rmin) / (rmax - rmin) if rmax > rmin else 0
            svg.rect(hx0 + ni * cw, hy0 + mi * ch, cw - 1, ch - 1, heat_color(1 - t), rx=1)
    for ni in range(0, n_cols, 2):
        svg.text(hx0 + ni * cw + cw / 2, hy0 + n_rows * ch + 15, 2 + ni * 4, size=9,
                 anchor="middle", color="#888")
    svg.text(hx0 + n_cols * cw / 2, hy0 + n_rows * ch + 32, "N", size=9.5, anchor="middle")
    svg.text(hx0 - 6, hy0 + n_rows * ch + 15, "M", size=9, anchor="end", color="#888")
    svg.save(path)
    if png:
        svg.save_png(path.with_suffix(".png"))


# ---------------------------------------------------------------- 图 4


def fig_investment(path, order, layer_files, cross_files, total_files, png, attributed=None):
    W, H = 800, 340
    svg = SVG(W, H)
    svg.text(24, 30, "各抽象层的测试投入分布", size=15, weight="bold")
    svg.text(24, 50, "按 test/Dialect/<X> 归属到层；跨层通用方言单独统计", size=10.5, color="#666")
    items = [(L["label_zh"], layer_files.get(L["id"], 0)) for L in order]
    items.append(("跨层通用方言（单列）", cross_files))
    items.sort(key=lambda kv: -kv[1])
    maxv = max([v for _, v in items] + [1])
    left, top, rowh = 200, 88, 40
    for i, (label, v) in enumerate(items):
        y = top + i * rowh
        w = (W - left - 110) * v / maxv
        svg.text(left - 12, y + 18, label, size=11, anchor="end")
        svg.rect(left, y + 5, max(w, 1.5), 20, LAYER_COLORS[i % len(LAYER_COLORS)], rx=3)
        denom = attributed or total_files or 1
        svg.text(left + max(w, 1.5) + 8, y + 20, f"{v}（{v / denom * 100:.1f}%）",
                 size=10, color="#555")
    svg.text(left, H - 16, f"口径：test/Dialect 下已归属文件共 {attributed or total_files} 个；全语料 {total_files} 个 .mlir", size=9.5, color="#666")
    svg.save(path)
    if png:
        svg.save_png(path.with_suffix(".png"))


# ---------------------------------------------------------------- facts.md


def write_facts(path: Path, ctx: dict):
    """把可复述的数字汇总成 markdown，供正文直接取用。不含解释。"""
    order = ctx["order"]
    layer_ids = [L["id"] for L in order]
    label = {L["id"]: L["label_zh"] for L in order}
    le = ctx["layer_edges"]
    ef = ctx["edge_files"]
    ns2layer = ctx["ns2layer"]

    dst = Counter()
    src = Counter()
    for (s, d), c in ef.items():
        dst[d] += c
        src[s] += c
    for d, c in ctx["unattributed"].items():
        dst[d] += c
    dst.pop("*", None)
    deepest = {L["id"] for L in order if L["order"] == max(x["order"] for x in order)}
    into_target = sum(c for (s, d), c in le.items() if d in deepest)
    total_le = sum(le.values())
    tt = sorted(((s, d, c) for (s, d), c in ef.items()
                 if ns2layer.get(s) == "target" and ns2layer.get(d) == "target"),
                key=lambda x: -x[2])
    into_llvm = sorted(((s, c) for (s, d), c in ef.items() if d == "llvm"), key=lambda x: -x[1])

    L = []
    A = L.append
    A("# 统计事实汇总（由 tools/analyze.py 自动生成）\n")
    A("> 本文件只有数字，没有解释。解释写在 `docs/04-results-v1.md`。\n")
    A("## 1. 数据规模\n")
    A(f"- 测试文件：**{ctx['total_files']}** 个 `.mlir`（`mlir/test/**`）")
    A(f"- 计入算子：**{ctx['n_ops']:,}** 个；剔除的非方言算子：{ctx['n_ops_excluded']:,} 个")
    A(f"- 语料版本：`{ctx['commit']}`")
    A(f"- 解析出的 (源方言 → 目标方言) 转换边：**{len(ef)}** 条，覆盖 {len(ctx['conv_files'])} 个 Conversion 文件")
    A(f"- 源方言 {len(src)} 个，目标方言 {len(dst)} 个\n")

    A("## 2. 目标端点收敛（入度，按 Conversion 文件数）\n")
    A("| 目标方言 | 所在层 | 文件数 |")
    A("|---|---|---|")
    for k, v in dst.most_common(12):
        A(f"| `{k}` | {ns2layer.get(k, '—')} | {v} |")
    A("")
    A(f"汇入 `llvm` 的转换共 **{sum(c for _, c in into_llvm)}** 个文件，来自 **{len(into_llvm)}** 个不同方言：")
    A("")
    A(", ".join(f"`{s}`({c})" for s, c in into_llvm) + "\n")

    A("## 3. 层间转换矩阵（行=源层，列=目标层，按文件数）\n")
    A("| 源 \\ 目标 | " + " | ".join(label[i] for i in layer_ids) + " |")
    A("|---|" + "---|" * len(layer_ids))
    for a in layer_ids:
        A(f"| **{label[a]}** | " + " | ".join(str(le.get((a, b), 0)) for b in layer_ids) + " |")
    A("")
    A(f"- 落到 `target` 层的边：**{into_target} / {total_le} = {into_target/total_le:.1%}**")
    A(f"- 非零层对：**{sum(1 for v in le.values() if v)}** 个")
    A(f"- `target` 层内部（target→target）：**{sum(c for _, _, c in tt)}** 个文件 / {len(tt)} 条边\n")
    if tt:
        A("| target 内部转换 | 文件数 |")
        A("|---|---|")
        for s, d, c in tt:
            A(f"| `{s}` → `{d}` | {c} |")
        A("")

    A("## 4. 各层测试投入\n")
    A("| 层 | `test/Dialect/<X>` 文件数 |")
    A("|---|---|")
    for k, v in ctx["layer_files"].most_common():
        A(f"| {label.get(k, k)} | {v} |")
    A(f"| 跨层通用方言（单列） | {ctx['cross_files']} |")
    A("")

    A("## 5. 两种成本口径（本报告的关键对比）\n")
    M_measured = len({d for (s, d) in ef if ns2layer.get(d) == "target"})
    N_measured = len({s for (s, d) in ef if ns2layer.get(s) == "frontend"})
    A(f"- 实测目标端点（`target` 层内作为转换目标的方言）数：**{M_measured}** —— 这是 M 的数据依据")
    A(f"- 实测前端端点（`frontend` 层内作为转换源的方言）数：**{N_measured}** —— "
      f"上游语料只覆盖极少数前端，故 N 必须取自生态而非本语料\n")
    A("| 口径 | 计数对象 | 数量 |")
    A("|---|---|---|")
    A(f"| 架构级：层与层之间的边界 | 非零层对 | **{sum(1 for v in le.values() if v)}** |")
    A(f"| 工程级：真正要写的转换 | (源方言, 目标方言) 对 | **{len(ef)}** |")
    A("")
    A("成本模型：`C_pair = N·M`，`C_layer = |E| + N + M + (1-p)·N·M`，"
      "交叉点 `N* = (|E| + M) / (p·M − 1)`。\n")
    A(f"取 `N = {ctx['N']}`，`M = {ctx['M']}`，对 p 做敏感性分析：\n")
    A("| p | N\\*（分层开始占优的框架数） |")
    A("|---|---|")
    for k, v in ctx["crossover"].items():
        A(f"| {k.split('=')[1]} | {v if v is not None else '无解（p·M ≤ 1）'} |")
    A("")
    A("分别用两种 |E| 代入（M 不变）：\n")
    A("| \\|E\\| 口径 | \\|E\\| | p=0.6 时的 N\\* | N=8, M=6 时 C_pair vs C_layer |")
    A("|---|---|---|---|")
    for name, E in (("工程级（方言对）", len(ef)),
                    ("架构级（层对）", sum(1 for v in le.values() if v))):
        denom = 0.6 * ctx["M"] - 1
        nst = (E + ctx["M"]) / denom if denom > 0 else None
        cp = ctx["N"] * ctx["M"]
        cl = E + ctx["N"] + ctx["M"] + (1 - 0.6) * ctx["N"] * ctx["M"]
        A(f"| {name} | {E} | {nst:.1f} | {cp} vs {cl:.1f} |" if nst else
          f"| {name} | {E} | 无解 | {cp} vs {cl:.1f} |")
    A("")

    if ctx["unattributed"]:
        A("## 6. 未计入层间矩阵的转换目录（源方言不定）\n")
        A("| 目标端点 | 文件数 |")
        A("|---|---|")
        for k, v in ctx["unattributed"].most_common():
            A(f"| `{k}` | {v} |")
        A("")
        A("这些目录（如 `ConvertToSPIRV`）不指明源方言，因此只计入目标端点证据，不计入层间边。\n")

    A("## 7. 待解释（写在 docs/04 或正文）\n")
    A("- 第 2 节的收敛点为什么是 `llvm`，而不是「某一层」？")
    A("- 第 3 节 target 层内部的 8 条边说明什么？")
    A("- 第 5 节两种 |E| 口径给出的 N\\* 相差数倍，这对「N×M 塌缩」的论断意味着什么？")
    A("- 第 4 节里 frontend 的投入为何显著低于其余各层？")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"     事实汇总：{path}")


# ---------------------------------------------------------------- 主流程


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="分析 MLIR 语料统计（零依赖，输出 SVG）")
    ap.add_argument("--corpus", default="out/corpus.csv")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--config", default=None, help="layers.json 路径")
    ap.add_argument("--n-frameworks", type=int, default=8, help="N：框架数量（请自行核算并说明来源）")
    ap.add_argument("--n-backends", type=int, default=6, help="M：后端数量（请自行核算并说明来源）")
    ap.add_argument("--adoption", type=float, default=0.6, help="p：共享层采纳率 0~1（请自行估计并说明方法）")
    ap.add_argument("--topk", type=int, default=12, help="共现矩阵取前 k 个方言")
    ap.add_argument("--preview-png", action="store_true", help="额外输出 PNG 预览（需 Pillow）")
    args = ap.parse_args(argv)

    outdir = Path(args.outdir)
    cfg_path = Path(args.config) if args.config else (Path(__file__).resolve().parent / "layers.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))

    rows, order, ns2layer, cross = load(Path(args.corpus), cfg)
    layer_ids = [L["id"] for L in order]
    total_files = len(rows)

    df, cooc = Counter(), Counter()
    for r in rows:
        ds = [d for d in r["_dialects"] if d]
        for d in ds:
            df[d] += 1
        for i, a in enumerate(ds):
            for b in ds[i:]:
                cooc[(a, b)] += 1
                if a != b:
                    cooc[(b, a)] += 1

    edge_files, layer_edges = Counter(), Counter()
    unattributed = Counter()          # src='*'：源方言不定的泛化转换目录，只按目标端点记
    for r in rows:
        if r["area_kind"] != "Conversion":
            continue
        s, d = r["src_ns"], r["dst_ns"]
        if not d:
            continue
        if s == "*":
            unattributed[d] += 1
            continue
        if not s:
            continue
        edge_files[(s, d)] += 1
        ls, ld = ns2layer.get(s), ns2layer.get(d)
        if ls and ld:
            layer_edges[(ls, ld)] += 1

    layer_out, layer_in = Counter(), Counter()
    for (ls, ld), c in layer_edges.items():
        layer_out[ls] += c
        layer_in[ld] += c

    # 最深的一批层（order 最大）：层划分可替换时，"汇聚点"按最深层判定
    max_order = max(L["order"] for L in order)
    deepest = {L["id"] for L in order if L["order"] == max_order}

    layer_files, cross_files = Counter(), 0
    for r in rows:
        if r["area_kind"] == "Dialect":
            ns = r.get("own_ns") or ""
            L = ns2layer.get(ns)
            if L:
                layer_files[L] += 1
            elif ns in cross:
                cross_files += 1

    outdir.mkdir(parents=True, exist_ok=True)
    png = args.preview_png
    fig_funnel(outdir / "fig1_layer_transitions.svg", order, layer_edges, layer_out, layer_in, png)
    fig_cooccurrence(outdir / "fig2_dialect_cooccurrence.svg", cooc, df, args.topk, png)
    fig_cost(outdir / "fig3_cost_model.svg", len(edge_files), args.n_frameworks,
             args.n_backends, args.adoption, png)
    attributed = sum(layer_files.values()) + cross_files
    fig_investment(outdir / "fig4_layer_investment.svg", order, layer_files, cross_files,
                   total_files, png, attributed)

    E, p, M = len(edge_files), args.adoption, args.n_backends
    crossover = {}
    for pp in (0.4, 0.5, 0.6, 0.8, 1.0):
        denom = pp * M - 1
        crossover[f"p={pp:.1f}"] = (round((E + M) / denom, 2) if denom > 0 else None)

    findings = {
        "sample": {"n_files": total_files},
        "structure": {
            "n_distinct_dialect_pairs": E,
            "layer_matrix": {f"{a}->{b}": layer_edges.get((a, b), 0)
                             for a in layer_ids for b in layer_ids},
            "layer_out_degree": dict(layer_out.most_common()),
            "layer_in_degree": dict(layer_in.most_common()),
            "top_dialect_edges": [{"src": s, "dst": d, "files": c}
                                  for (s, d), c in edge_files.most_common(15)],
            "deepest_layers": sorted(deepest),
            "share_edges_landing_in_deepest_layers": (
                sum(c for (s, d), c in layer_edges.items() if d in deepest) /
                sum(layer_edges.values()) if layer_edges else None),
        },
        "cooccurrence": {
            "dialect_document_frequency": dict(df.most_common(30)),
            "share_of_files_containing_a_crosslayer_dialect": (
                sum(1 for r in rows if set(r["_dialects"]) & cross) / total_files
                if total_files else None),
        },
        "investment": {
            "files_per_layer": dict(layer_files.most_common()),
            "crosslayer_files": cross_files,
            "total": total_files,
        },
        "cost_model": {
            "formula_pairwise": "N*M",
            "formula_layered": "|E| + N + M + (1-p)*N*M",
            "E_measured": E, "N": args.n_frameworks, "M": M, "p": p,
            "crossover_N_by_p": crossover,
            "note": "E 为本语料测得的 (dialect, dialect) 转换边数，作为'每条层间边界实现一次'的成本单位。"
                    "N、M、p 必须由作者核实来源后填入并在报告中说明取值依据。",
        },
        "interpretation": {
            "_instructions": "以下字段必须由报告作者本人填写；null 表示分析尚未完成。",
            "H1_convergence": None,
            "H2_asymmetry": None,
            "H3_conditional_benefit": None,
            "threats_to_validity": None,
        },
    }
    (outdir / "findings.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2), encoding="utf-8")

    meta_path = outdir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.is_file() else {}
    write_facts(outdir / "facts.md", dict(
        order=order, layer_edges=layer_edges, edge_files=edge_files, ns2layer=ns2layer,
        total_files=total_files, n_ops=meta.get("n_ops_total", 0),
        n_ops_excluded=meta.get("n_ops_excluded", 0),
        commit=meta.get("git_commit", "未记录"),
        conv_files=[r for r in rows if r["area_kind"] == "Conversion"],
        layer_files=layer_files, cross_files=cross_files, unattributed=unattributed,
        N=args.n_frameworks, M=M, crossover=crossover,
    ))

    print("\n=== 结构 ===")
    print(f"文件数 {total_files}；不同方言转换边 |E| = {E}")
    print("层间矩阵（行=源层，列=目标层）：")
    print(" " * 12 + "".join(f"{b[:12]:>14}" for b in layer_ids))
    for a in layer_ids:
        print(f"{a[:11]:<12}" + "".join(f"{layer_edges.get((a, b), 0):>14}" for b in layer_ids))
    sh = findings["structure"]["share_edges_landing_in_deepest_layers"]
    dl = "/".join(sorted(findings["structure"]["deepest_layers"]))
    print(f"\n落到最深层（{dl}）的边占比：{sh:.3f}" if sh is not None else "\n(无层间边)")

    print("\n=== 投入（test/Dialect 文件数）===")
    for k, v in layer_files.most_common():
        print(f"  {k:<16}{v:>6}")
    print(f"  {'crosslayer':<16}{cross_files:>6}")

    print(f"\n=== 成本模型 E={E}, N={args.n_frameworks}, M={M}, p={p} ===")
    for k, v in crossover.items():
        print(f"  分层开始占优的 N*（{k}）：{v}")
    print(f"\n[OK] {outdir / 'findings.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
