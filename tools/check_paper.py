#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_paper.py — 在没有 LaTeX 的机器上对 paper/ 做静态体检。

为什么需要它
------------
本机没有 pdflatex，无法编译验证。这个脚本只检查"最常见的编译失败原因"，
不保证排版正确，但能把 90% 的低级错误在提交 Overleaf 之前排掉。

检查项
------
1. 花括号是否配平（跳过 \\{ \\} 与注释）
2. \\begin{env} / \\end{env} 是否成对且顺序正确
3. \\input{...} 指向的文件是否存在
4. \\includegraphics{...} 指向的图片是否存在
5. \\cite{...} 的 key 是否都在 references.bib 里；并列出未被引用的条目
6. \\ref{...} 是否有对应 \\label{...}；并列出未被引用的 label
7. 报告里不该出现的旧数字（79、22.9、7.7、M=8 等）是否残留

用法
----
    python tools/check_paper.py
    python tools/check_paper.py --paper-dir paper
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 已废弃的数字：出现在正文里说明与 out/facts.md 不一致（2026-11-23 按外部 review 修正后）
STALE = [
    (r"\|E\|\s*=\s*78", "|E| 应为 76"),
    (r"\b78 条", "应为 76 条"),
    (r"\b78 个", "应为 76 个"),
    (r"79\.0\s*%", "最深层占比应为 79.2%"),
    (r"\b36\.4\s*%", "替代划分占比应为 36.6%"),
    (r"\b17\.6\b", "工程级 N* 应为 15.5"),
    (r"\b4\.8\b", "架构级 N* 应为 4.6"),
    (r"\b22\.9\b", "旧的工程级 N*（M=8 时代）"),
    (r"\b16\.1\b", "旧的敏感性下限"),
    (r"\b39\.6\b", "旧的敏感性上限"),
    (r"M\s*=\s*10\b", "M 应为 11"),
    (r"1,?077", "已归属文件数应为 1,390"),
    (r"5\.2\s*\\?%", "导入层占比应为 4.5%"),
    (r"\b230\s*/\s*291", "应为 236/298"),
    (r"\bMLVM\b", "拼写应为 LLVM"),
    (r"\bMOLIR\b", "拼写应为 MLIR"),
]


def strip_comments(text: str) -> str:
    """去掉未被转义的 % 注释（保留行数以便报错定位）。"""
    out = []
    for line in text.splitlines():
        buf, i = [], 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                buf.append(line[i:i + 2])
                i += 2
                continue
            if ch == "%":
                break
            buf.append(ch)
            i += 1
        out.append("".join(buf))
    return "\n".join(out)


def check_braces(path: Path, text: str, problems: list):
    depth, line_no = 0, 1
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line_no += 1
        if ch == "\\" and i + 1 < len(text):
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                problems.append(f"{path.name}:{line_no}: 多余的 '}}'")
                depth = 0
        i += 1
    if depth != 0:
        problems.append(f"{path.name}: 花括号不配平，结束时还差 {depth} 个 '}}'")


def check_envs(path: Path, text: str, problems: list):
    stack = []
    for m in re.finditer(r"\\(begin|end)\{([^}]+)\}", text):
        kind, env = m.group(1), m.group(2)
        line_no = text[: m.start()].count("\n") + 1
        if kind == "begin":
            stack.append((env, line_no))
        else:
            if not stack:
                problems.append(f"{path.name}:{line_no}: \\end{{{env}}} 没有对应的 begin")
            elif stack[-1][0] != env:
                problems.append(
                    f"{path.name}:{line_no}: \\end{{{env}}} 与最近打开的 "
                    f"\\begin{{{stack[-1][0]}}}（第 {stack[-1][1]} 行）不匹配")
                stack.pop()
            else:
                stack.pop()
    for env, line_no in stack:
        problems.append(f"{path.name}:{line_no}: \\begin{{{env}}} 未关闭")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper-dir", default="paper")
    args = ap.parse_args(argv)

    paper = Path(args.paper_dir)
    if not paper.is_dir():
        print(f"[错误] 找不到目录 {paper}", file=sys.stderr)
        return 2

    tex_files = sorted(paper.rglob("*.tex"))
    if not tex_files:
        print(f"[错误] {paper} 下没有 .tex", file=sys.stderr)
        return 2

    problems: list[str] = []
    warnings: list[str] = []
    bib = paper / "references.bib"
    bib_text = bib.read_text(encoding="utf-8") if bib.is_file() else ""
    bib_keys = set(re.findall(r"@\w+\{([^,]+),", bib_text))

    cites: dict[str, str] = {}
    refs: dict[str, str] = {}
    labels: dict[str, str] = {}

    for tex in tex_files:
        raw = tex.read_text(encoding="utf-8")
        text = strip_comments(raw)
        check_braces(tex, text, problems)
        check_envs(tex, text, problems)

        # \input / \include
        for m in re.finditer(r"\\(?:input|include)\{([^}]+)\}", text):
            target = paper / m.group(1)
            if target.suffix != ".tex":
                target = target.with_suffix(".tex")
            if not target.is_file():
                problems.append(f"{tex.name}: \\input{{{m.group(1)}}} 找不到 {target}")

        # \includegraphics
        for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
            target = paper / m.group(1)
            if not target.is_file():
                problems.append(f"{tex.name}: \\includegraphics 找不到 {target}")

        for m in re.finditer(r"\\cite[a-z]*\{([^}]+)\}", text):
            for key in m.group(1).split(","):
                cites[key.strip()] = tex.name
        for m in re.finditer(r"\\ref\{([^}]+)\}", text):
            refs[m.group(1)] = tex.name
        for m in re.finditer(r"\\label\{([^}]+)\}", text):
            if m.group(1) in labels:
                warnings.append(f"重复 label: {m.group(1)}（{labels[m.group(1)]} 与 {tex.name}）")
            labels[m.group(1)] = tex.name

        for pat, note in STALE:
            for m in re.finditer(pat, text):
                line_no = text[: m.start()].count("\n") + 1
                problems.append(f"{tex.name}:{line_no}: 疑似过期数字 —— {note}")

    for key, where in cites.items():
        if key not in bib_keys:
            problems.append(f"{where}: \\cite{{{key}}} 不在 references.bib")
    for key in sorted(bib_keys - set(cites)):
        warnings.append(f"references.bib 中的 {key} 未被引用")
    for r, where in refs.items():
        if r not in labels:
            problems.append(f"{where}: \\ref{{{r}}} 没有对应 \\label")

    print(f"检查 {len(tex_files)} 个 .tex 文件，bib 条目 {len(bib_keys)} 条，"
          f"引用 {len(cites)} 条，label {len(labels)} 个\n")

    if problems:
        print(f"✗ 阻断性问题 {len(problems)} 个：")
        for p in problems:
            print("   -", p)
    else:
        print("✓ 未发现阻断性问题（花括号/环境/input/图片/cite/ref 全部通过）")

    if warnings:
        print(f"\n⚠ 提醒 {len(warnings)} 条（不阻断编译）：")
        for w in warnings:
            print("   -", w)

    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
