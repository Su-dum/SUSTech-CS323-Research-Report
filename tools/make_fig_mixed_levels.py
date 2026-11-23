#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_fig2_mixed_levels.py — 生成报告图 2：同一 module 内的多级抽象共存。

图的论点
--------
MLIR 允许不同抽象高度的算子**共存于同一个 module**，并且都是合法 IR。
因此"下降"可以是**部分的**：同一个文件里，一处保留整体结构化算子，
另一处已经显式化成循环与子算子——这正是 progressive lowering 的中间状态。

选材
----
`test/Integration/Dialect/Linalg/CPU/matmul-vs-matvec.mlir`
  - `@matmul`：一次 `linalg.matmul` 完成整个矩阵乘（无显式循环）
  - `@matvec`：`scf.for` + `linalg.matvec` + `memref.subview`（循环已显式化）
两个函数在同一个 module 里，语义相同、抽象高度不同。共 4 个层。

用法
----
  python tools/make_fig2_mixed_levels.py --mlir-root D:\\llvm-project\\mlir \\
      --out out/fig_mixed_levels.svg --preview-png
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze import LAYER_COLORS, SVG  # noqa: E402

# ---------------------------------------------------------------- 选材配置

SOURCE = "test/Integration/Dialect/Linalg/CPU/matmul-vs-matvec.mlir"

SEGMENTS = [
    {"start": 8, "end": 19, "label": "整算子\n一次 linalg.matmul"},
    {"elide": "…（省略 module 内其他函数的声明与调用）…"},
    {"start": 21, "end": 37, "label": "显式循环\nscf.for + 子算子"},
]

LAYER_OF = {
    "linalg": "tensor",
    "tensor": "tensor",
    "scf": "parallel",
    "affine": "parallel",
    "cf": "parallel",
    "memref": "memory_vector",
    "vector": "memory_vector",
    "bufferization": "memory_vector",
}
COLOR = {
    "frontend": LAYER_COLORS[0],
    "tensor": LAYER_COLORS[1],
    "parallel": LAYER_COLORS[2],
    "memory_vector": LAYER_COLORS[3],
    "target": LAYER_COLORS[4],
    "cross": "#C2C8D2",
}
LEGEND = [
    ("tensor", "张量代数层（结构化算子：linalg.matmul / matvec / fill）"),
    ("parallel", "并行与控制层（显式循环：scf.for）"),
    ("memory_vector", "存储与向量层（缓冲区与显式搬运：memref.*）"),
    ("cross", "跨层通用（arith / func / return / 右括号）"),
]
MONO = "Consolas, 'DejaVu Sans Mono', 'Courier New', monospace"

FS = 10.0        # 代码字号
LH = 15.0        # 行高


def classify(line: str) -> str:
    s = line.strip()
    if not s or s.startswith("//"):
        return "cross"
    if s.startswith("%"):
        i = s.find("=")
        if i < 0:
            return "cross"
        s = s[i + 1:].strip()
    head = s.split()[0] if s.split() else ""
    if "." in head:
        ns = head.split(".")[0]
        if ns in LAYER_OF:
            return LAYER_OF[ns]
    return "cross"


CONT_RE = re.compile(r"^(ins|outs|->|\}\s*->|\}\s*$)")


def _is_continuation(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # 只把明显的算子续行算作续行；单独的 } 仍归跨层通用
    return bool(CONT_RE.match(s)) and s != "}"


def collect(src: Path):
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    items = []
    for seg in SEGMENTS:
        if "elide" in seg:
            items.append({"kind": "elide", "text": seg["elide"]})
            continue
        items.append({"kind": "open", "label": seg["label"]})
        for n in range(seg["start"], seg["end"] + 1):
            text = lines[n - 1]
            layer = classify(text)
            if layer == "cross" and _is_continuation(text):
                # 续行：沿用上一条真正的算子行的层，避免多行算子被拆成两种颜色
                for prev in reversed(items):
                    if prev["kind"] == "code" and prev["layer"] != "cross":
                        layer = prev["layer"]
                        break
            items.append({"kind": "code", "n": n, "text": text, "layer": layer})
        items.append({"kind": "close"})
    return items


def render(out_path: Path, items, source_label: str, png: bool):
    W = 950
    head = 78
    gutter = 44
    rail_x = 26
    bracket_x = W - 168

    body_h = sum(11 if it["kind"] == "elide" else LH
                 for it in items if it["kind"] in ("elide", "code"))
    n_code = sum(1 for it in items if it["kind"] == "code")
    legend_y = head + body_h + 22
    H = int(legend_y + 18 + len(LEGEND) * 16 + 34)

    svg = SVG(W, H)
    svg.text(24, 30, "图 2  同一 module 内的多级抽象共存", size=15, weight="bold")
    svg.text(24, 50, f"选自 {source_label}（节选 {n_code} 行，未改写）；左侧色条标出该行算子所属的抽象层",
             size=10.5, color="#666")
    svg.text(24, 66, "同一份模块里，同一个矩阵乘既以整体结构化算子存在，也以显式循环加子算子存在"
                     "——所以下降可以是部分的", size=10.5, color="#666")

    y = head
    spans = []
    open_y = None
    for it in items:
        k = it["kind"]
        if k == "elide":
            svg.text(gutter + 12, y + 8, it["text"], size=9.5, color="#98A2B3")
            y += 11
            continue
        if k == "open":
            open_y = y
            continue
        if k == "close":
            if open_y is not None:
                spans.append((open_y, y))
                open_y = None
            continue
        svg.text(gutter - 8, y + 10.4, it["n"], size=8.5, anchor="end", color="#A6AEBB")
        svg.rect(rail_x, y + 2, 4, LH - 5, COLOR[it["layer"]], rx=1)
        svg.text(gutter + 8, y + 10.6, it["text"], size=FS, color="#1F2430", family=MONO)
        y += LH

    # 右侧括号 + 两行标签
    labels = [it["label"] for it in items if it["kind"] == "open"]
    for (y0, y1), lab in zip(spans, labels):
        svg.line(bracket_x, y0 + 3, bracket_x, y1 - 3, stroke="#C9D0D9", sw=1.5)
        for dy in (y0 + 3, y1 - 3):
            svg.line(bracket_x - 5, dy, bracket_x, dy, stroke="#C9D0D9", sw=1.5)
        for i, line in enumerate(lab.split("\n")):
            svg.text(bracket_x + 9, y0 + 13 + i * 13, line, size=9, color="#5a6472",
                     weight="bold" if i == 0 else "normal")

    ly = legend_y
    svg.text(24, ly, "层级图例", size=10.5, weight="bold", color="#444")
    for i, (key, label) in enumerate(LEGEND):
        yy = ly + 17 + i * 16
        svg.rect(26, yy - 8, 10, 10, COLOR[key], rx=2)
        svg.text(44, yy, label, size=9.5, color="#333")

    svg.text(24, H - 14, "说明：真实语料，未改写；仅按行区间节选，省略处以 … 标出。"
                         "色条由行首算子命名空间决定，} 与 return 归入跨层通用。",
             size=9, color="#8a94a6")
    svg.save(out_path)
    if png:
        svg.save_png(out_path.with_suffix(".png"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mlir-root", required=True)
    ap.add_argument("--out", default="out/fig_mixed_levels.svg")
    ap.add_argument("--preview-png", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.mlir_root) / SOURCE
    if not src.is_file():
        print(f"[错误] 找不到 {src}", file=sys.stderr)
        return 2
    items = collect(src)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    render(out_path, items, SOURCE, args.preview_png)

    counts = {}
    for it in items:
        if it["kind"] == "code":
            counts[it["layer"]] = counts.get(it["layer"], 0) + 1
    print(f"[OK] {out_path}")
    print("     行数按层：" + "，".join(f"{k}={v}" for k, v in sorted(counts.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
