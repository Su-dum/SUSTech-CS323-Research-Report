#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_attribution.py — 审计"归属失败"的目录：哪些 Dialect 目录、哪些 Conversion
目录没有被映射到层，各丢了多少文件。

为什么需要它
------------
collect_corpus.py 对 test/Dialect/<Name> 用驼峰切分推断方言名，analyze.py 对
映射不到层的文件**静默丢弃**。LLVMIR / SparseTensor / X86 / MLProgram 这类目录名
切分后得不到正确的命名空间，于是整批文件从"投入分布"里消失而不报警。

本脚本把这类"静默丢失"显式列出来。

用法
----
    python tools/audit_attribution.py --mlir-root D:\\llvm-project\\mlir
    python tools/audit_attribution.py --corpus out/corpus.csv    # 只查已采集数据
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_corpus import camel_to_ns, parse_area  # noqa: E402


def load_cfg(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--mlir-root", default=r"D:\llvm-project\mlir")
    ap.add_argument("--corpus", default=str(here.parent / "out" / "corpus.csv"))
    ap.add_argument("--config", default=str(here / "layers.json"))
    args = ap.parse_args(argv)

    cfg = load_cfg(Path(args.config))
    aliases = {k: v for k, v in cfg.get("aliases", {}).items() if not k.startswith("_")}
    overrides = {k: v for k, v in cfg.get("conversion_overrides", {}).items()
                 if not k.startswith("_")}
    ns2layer = {}
    for L in cfg["layers"]:
        for ns in L["dialects"]:
            ns2layer[ns] = L["id"]
    cross = set(cfg.get("crosslayer", {}).get("dialects", []))
    infra = set(cfg.get("infra", {}).get("dialects", []))
    noise = set(cfg.get("noise_dialects", {}).get("dialects", []))
    known = set(ns2layer) | cross | infra | noise

    root = Path(args.mlir_root)
    rows = list(csv.DictReader(open(args.corpus, encoding="utf-8"))) if Path(args.corpus).is_file() else []

    # ---------- 1. Dialect 目录归属 ----------
    print("=" * 78)
    print("1. test/Dialect/<Name> 的归属审计")
    print("=" * 78)
    dial_dirs = Counter()
    for r in rows:
        if r["area_kind"] == "Dialect":
            dial_dirs[r["area_name"]] += 1
    if not dial_dirs and root.joinpath("test").is_dir():
        for p in root.joinpath("test").rglob("*.mlir"):
            info = parse_area(p.relative_to(root), aliases, overrides)
            if info["area_kind"] == "Dialect":
                dial_dirs[info["area_name"]] += 1

    lost = []
    for name, n in sorted(dial_dirs.items(), key=lambda kv: -kv[1]):
        ns = camel_to_ns(name, aliases)
        if ns in ns2layer:
            continue
        tag = "crosslayer" if ns in cross else ("infra" if ns in infra else "丢失")
        if tag != "丢失":
            continue
        lost.append((name, ns, n))
    if lost:
        print(f"{'目录名':<26}{'切分得到的命名空间':<28}{'文件数':>6}")
        print("-" * 62)
        total = 0
        for name, ns, n in lost:
            print(f"{name:<26}{ns:<28}{n:>6}")
            total += n
        print("-" * 62)
        print(f"合计丢失 {total} 个文件（占 Dialect 文件 "
              f"{total / sum(dial_dirs.values()):.1%}）")
        print("\n修复方式：在 layers.json 的 aliases 里补上这些目录名到正确命名空间的映射。")
    else:
        print("✓ 无丢失")

    # ---------- 2. Conversion 目录端点归属 ----------
    print()
    print("=" * 78)
    print("2. Conversion/<X>To<Y> 的端点审计")
    print("=" * 78)
    bad = Counter()
    for r in rows:
        if r["area_kind"] != "Conversion":
            continue
        s, d = r["src_ns"], r["dst_ns"]
        if not s or not d or "*" in (s, d):
            continue
        if s not in known or d not in known:
            bad[(r["area_name"], s, d)] += 1
    if bad:
        print(f"{'转换目录':<32}{'源':<20}{'目标':<24}{'文件数':>5}")
        print("-" * 82)
        tot = 0
        for (name, s, d), n in sorted(bad.items(), key=lambda kv: -kv[1]):
            mark_s = "" if s in known else "✗"
            mark_d = "" if d in known else "✗"
            print(f"{name:<32}{mark_s + s:<20}{mark_d + d:<24}{n:>5}")
            tot += n
        print("-" * 82)
        print(f"合计 {tot} 个文件、{len(bad)} 条'伪边'：端点里有不在任何层/跨层/基础设施集合中的")
        print("命名空间，因此不会进入层矩阵，却仍被计入 |E|。")
        print("\n修复方式：layers.json 的 conversion_overrides 里显式写 src/dst，")
        print("或补 aliases（例如 LLVMSPV -> llvm、AMX -> x86）。")
    else:
        print("✓ 无伪边")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
