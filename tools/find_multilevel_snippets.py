#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_multilevel_snippets.py — 找出「同一函数体内多个抽象层共存」的语料片段。

用途
----
报告 §3 需要一张图，展示 MLIR 让不同抽象层级**共存于同一个函数/module**里
（这是 progressive lowering 的前提）。本脚本从 mlir/test 里筛出最合适的候选。

与"整文件统计"的区别
--------------------
整文件扫描只会命中 Integration 目录下的大文件（几十到上千行）。真正适合当图的
是**单个函数体**里 4 个层级并存、长度 16~32 行的那种片段，所以这里按函数级切窗口。

筛选逻辑
--------
1. 用括号深度切出每个 `func.func` / `gpu.func` / `llvm.func` 区域；
2. 统计该区域内的方言 → 归层；
3. 要求覆盖 ≥ min-layers 个层；
4. 打分：层数 + 规模接近理想区间 + 层级纯净度
   + **加分项**：tensor 与 memref 同时出现（这是 bufferization 边界，最适合当图）。

用法
----
  python tools/find_multilevel_snippets.py --mlir-root D:\\llvm-project\\mlir --list 12
  python tools/find_multilevel_snippets.py --mlir-root D:\\llvm-project\\mlir --show 3
  python tools/find_multilevel_snippets.py --mlir-root D:\\llvm-project\\mlir --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_corpus import ALIAS_DEF_RE, BLOCK_LABEL_RE, OP_RE, strip_comment  # noqa: E402

REPRESENTATIVE = {
    "frontend": {"torch", "tosa", "stablehlo", "mhlo", "onnx", "ml_program"},
    "tensor": {"linalg", "tensor", "sparse_tensor"},
    "parallel": {"scf", "affine", "cf", "async", "omp", "gpu", "shard"},
    "memory_vector": {"memref", "vector", "bufferization", "ptr"},
    "target": {"llvm", "spirv", "nvvm", "rocdl", "amdgpu", "xegpu", "xevm", "arm_sme"},
}
CROSS = {"func", "arith", "math", "index", "builtin", "ub"}
REGION_START = re.compile(r"^\s*(?:func\.func|gpu\.func|llvm\.func)\b")


def iter_regions(lines: list[str]):
    """按括号深度切出函数区域，返回 (start, end) 的 0-based 闭区间。"""
    i, n = 0, len(lines)
    while i < n:
        if not REGION_START.match(strip_comment(lines[i])):
            i += 1
            continue
        depth = 0
        started = False
        j = i
        while j < n:
            code = strip_comment(lines[j])
            depth += code.count("{") - code.count("}")
            if "{" in code:
                started = True
            if started and depth <= 0:
                break
            j += 1
        yield i, min(j, n - 1)
        i = max(j + 1, i + 1)


def dialects_in(lines: list[str], start: int, end: int) -> Counter:
    c: Counter = Counter()
    for k in range(start, end + 1):
        line = strip_comment(lines[k])
        if not line.strip() or ALIAS_DEF_RE.match(line) or BLOCK_LABEL_RE.match(line):
            continue
        m = OP_RE.match(line)
        if m:
            ns = (m.group("q") or m.group("p")).split(".", 1)[0]
            c[ns] += 1
    return c


def score(ds: Counter, nlines: int, lo=16, hi=32):
    layers = {L for L, reps in REPRESENTATIVE.items() if any(d in reps for d in ds)}
    if len(layers) < 3:
        return None
    if lo <= nlines <= hi:
        size = 1.0
    elif nlines < lo:
        size = max(0.0, 1.0 - (lo - nlines) / lo)
    else:
        size = max(0.0, 1.0 - (nlines - hi) / hi)

    unrelated = {d for d in ds if d not in CROSS} - {
        d for reps in REPRESENTATIVE.values() for d in reps
    }
    purity = max(0.0, 1.0 - len(unrelated) / 4)

    # tensor 与 memref 并存 = bufferization 边界，教学价值最高
    buf_boundary = 0.8 if ("tensor" in ds and "memref" in ds) else 0.0
    # 结构化算子 + 循环 + 显式搬运，是"多级并存"最典型的形态
    classic = sum(0.25 for d in ("linalg", "scf", "memref", "vector", "arith") if d in ds)

    total = len(layers) * 1.0 + size * 1.2 + purity * 0.8 + buf_boundary + classic
    return {
        "layers": sorted(layers),
        "n_layers": len(layers),
        "nlines": nlines,
        "dialects": dict(ds.most_common()),
        "buf_boundary": bool(buf_boundary),
        "score": round(total, 3),
        "size_score": round(size, 2),
        "purity": round(purity, 2),
        "unrelated": sorted(unrelated),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mlir-root", required=True)
    ap.add_argument("--list", type=int, default=0)
    ap.add_argument("--show", type=int, default=None, help="打印第 N 名候选（从 1 开始）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-layers", type=int, default=4)
    args = ap.parse_args(argv)

    root = Path(args.mlir_root)
    rows = []
    for path in root.joinpath("test").rglob("*.mlir"):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        rel = path.relative_to(root).as_posix()
        for s, e in iter_regions(lines):
            ds = dialects_in(lines, s, e)
            if not ds:
                continue
            r = score(ds, e - s + 1)
            if r and r["n_layers"] >= args.min_layers:
                r.update(path=rel, start=s + 1, end=e + 1)
                rows.append(r)

    rows.sort(key=lambda r: (-r["score"], r["nlines"], r["path"]))
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if args.show:
        r = rows[args.show - 1]
        p = root / r["path"]
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        print(f"# {r['path']}:{r['start']}-{r['end']}  score={r['score']}  "
              f"lines={r['nlines']}  layers={','.join(r['layers'])}\n")
        for i in range(r["start"] - 1, r["end"]):
            print(f"{i+1:4d} | {lines[i]}")
        return 0

    print(f"候选数：{len(rows)}（单函数内覆盖 ≥{args.min_layers} 层）")
    print(f"其中 tensor 与 memref 并存（bufferization 边界）：{sum(1 for r in rows if r['buf_boundary'])}\n")
    print(f"{'#':>3} {'score':>6} {'层':>2} {'行':>4} {'边界':>4}  位置")
    print("-" * 104)
    for i, r in enumerate(rows[: max(args.list, 20)], 1):
        print(f"{i:>3} {r['score']:>6.2f} {r['n_layers']:>2} {r['nlines']:>4} "
              f"{'tensor|memref' if r['buf_boundary'] else '-':>13}  {r['path']}:{r['start']}-{r['end']}")
        print(f"{'':>3} 层={','.join(r['layers'])}  方言={','.join(list(r['dialects'])[:8])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
