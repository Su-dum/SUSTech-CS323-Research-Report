#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diagnose_namespaces.py — 列出语料中出现的所有方言命名空间及若干样例行。

用途：在把某个命名空间判为"噪声"并从统计中剔除之前，先看它到底是什么。
报告的方法节需要能说明：剔除了哪些、为什么、影响多少算子。

用法：
    python tools/diagnose_namespaces.py --mlir-root D:\\llvm-project\\mlir
    python tools/diagnose_namespaces.py --mlir-root D:\\llvm-project\\mlir --ns i32 bytecode
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

OP_RE = re.compile(
    r'^\s*(?:%[\w$.#]+\s*=\s*)?'
    r'(?:"(?P<q>[A-Za-z_][\w$]*\.[A-Za-z_][\w$]*)"|(?P<p>[A-Za-z_][\w$]*\.[A-Za-z_][\w$]*))'
)
ALIAS_DEF_RE = re.compile(r'^\s*[#!][\w$.\-]*\s*=')
BLOCK_LABEL_RE = re.compile(r'^\s*\^')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mlir-root", required=True)
    ap.add_argument("--ns", nargs="*", default=None, help="只详细看这些命名空间")
    ap.add_argument("--samples", type=int, default=3)
    args = ap.parse_args(argv)

    test_root = Path(args.mlir_root) / "test"
    counts: Counter = Counter()
    files_of: dict[str, Counter] = defaultdict(Counter)
    samples: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for path in sorted(test_root.rglob("*.mlir")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(args.mlir_root).as_posix()
        for raw in text.splitlines():
            line = raw.split("//", 1)[0]
            if not line.strip() or ALIAS_DEF_RE.match(line) or BLOCK_LABEL_RE.match(line):
                continue
            m = OP_RE.match(line)
            if not m:
                continue
            ns = (m.group("q") or m.group("p")).split(".", 1)[0]
            counts[ns] += 1
            files_of[ns][rel] += 1
            if len(samples[ns]) < args.samples:
                samples[ns].append((rel, raw.strip()[:120]))

    print(f"共 {len(counts)} 个命名空间，总算子 {sum(counts.values())}\n")
    print(f"{'namespace':<20}{'ops':>9}  {'files':>7}")
    print("-" * 40)
    for ns, c in counts.most_common():
        print(f"{ns:<20}{c:>9}  {len(files_of[ns]):>7}")

    target = set(args.ns) if args.ns else set(counts)
    for ns in sorted(target, key=lambda n: -counts[n]):
        print(f"\n### {ns}  ({counts[ns]} ops in {len(files_of[ns])} files)")
        for rel, line in samples.get(ns, []):
            print(f"  {rel}\n    {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
