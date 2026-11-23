#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_corpus.py — 从 llvm-project 的 mlir/ 目录采集 MLIR 测试语料的结构化统计。

设计目标
--------
1. 零第三方依赖（只用标准库），Windows / Linux / macOS 均可直接跑。
2. 只做"客观计数"，不做任何结论推断——解读必须由报告作者完成。
3. 统计口径全部显式记录在输出的 meta 里，便于在报告中交代方法。

用法
----
    python tools/collect_corpus.py --mlir-root D:\\llvm-project\\mlir --outdir out
    python tools/collect_corpus.py --selftest --outdir out_selftest     # 用合成样本自检

输入布局假设（llvm-project 标准布局）
-------------------------------------
    <mlir-root>/test/Dialect/<Name>/*.mlir                —— 单层的往返/单元测试
    <mlir-root>/test/Conversion/<Src>To<Dst>/*.mlir       —— 层间下降测试
    <mlir-root>/test/Transforms|Target|Integration|...    —— 其他
仅扫描 test/ 下的 *.mlir。

输出
----
    <outdir>/corpus.csv       每个文件一行
    <outdir>/meta.json        口径声明、跳过项、未知方言、总量
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ---------------------------------------------------------------- 正则与常量

# 一条 MLIR 语句通常形如：
#     %0 = arith.addf %a, %b : f32
#     "tosa.conv2d"(%0, %1) {...} : (...) -> tensor<...>
#     linalg.generic {...}
# 这里只抓"语句起始处的带命名空间算子名"。
_OP_START = (
    r'^\s*'
    r'(?:%[\w$.#]+\s*=\s*)?'          # 可选的结果绑定 %0 = / %0#1 =
    r'(?:"(?P<q>[A-Za-z_][\w$]*\.[A-Za-z_][\w$]*)"'   # 带引号形式
    r'|(?P<p>[A-Za-z_][\w$]*\.[A-Za-z_][\w$]*))'      # 裸形式
)
OP_RE = re.compile(_OP_START)

# 属性别名 / 类型别名的定义行，例如：#map = affine_map<(d0) -> (d0)>
ALIAS_DEF_RE = re.compile(r'^\s*[#!][\w$.\-]*\s*=')

# 顶层块标签，例如 ^bb1(...)
BLOCK_LABEL_RE = re.compile(r'^\s*\^')

# Conversion 目录名拆解：ArithToLLVM / TosaToLinalg / GPUToNVVM
CONV_SPLIT_RE = re.compile(r'^(?P<src>[A-Za-z][A-Za-z0-9]*)To(?P<dst>[A-Za-z][A-Za-z0-9]*)$')

# 无分隔的驼峰/全大写词切分：ControlFlow -> Control, Flow ; NVVM -> NVVM
_CAMEL = re.compile(r'[A-Z]+(?![a-z])|[A-Z][a-z0-9]*')

# 已知 dialect 命名空间（来自 mlir.llvm.org/docs/Dialects 的清单，另加若干常见外部方言）。
# 不在此集合中的命名空间仍会被计数，但会在 meta.json 里单独列出，避免静默错误。
KNOWN_DIALECTS = {
    "acc", "affine", "amdgpu", "arith", "arm_neon", "arm_sve", "armsme", "async",
    "bufferization", "builtin", "cf", "complex", "dlti", "emitc", "func", "gpu",
    "index", "irdl", "linalg", "llvm", "math", "memref", "ml_program", "mpi",
    "nvgpu", "nvvm", "omp", "pdl", "pdl_interp", "ptr", "quant", "rocdl", "scf",
    "shape", "shard", "smt", "sparse_tensor", "tensor", "ub", "vcix", "vector",
    "wasmssa", "x86", "xegpu", "xevm", "tosa", "spirv", "transform",
    "arm_sme", "arm_neon", "arm_sve", "ptr", "wasmssa", "dlti", "omp", "acc",
    # 生态中常见、但不在上游 Dialects 文档里的命名空间
    "torch", "stablehlo", "mhlo", "onnx", "iree", "tt", "ttir", "ttnn", "arithx",
    "hivm", "hacc", "anvil", "linalgx", "gpu", "xevm", "vortex",
}


# ---------------------------------------------------------------- 工具函数


def git_commit(mlir_root: Path) -> str:
    """尽力记录语料的 commit，便于报告写明可复现来源。"""
    try:
        import subprocess
        for cand in (mlir_root, mlir_root.parent):
            r = subprocess.run(["git", "-C", str(cand), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
    except Exception:
        pass
    return "未记录"


def camel_to_ns(name: str, aliases: dict) -> str:
    if name in aliases:
        return aliases[name]
    parts = _CAMEL.findall(name)
    if not parts:
        return name.lower()
    return "".join(parts).lower()


def strip_comment(line: str) -> str:
    """去掉 // 行注释。MLIR 测试里字符串中极少出现 //，此处按朴素口径处理。"""
    idx = line.find("//")
    return line if idx < 0 else line[:idx]


def scan_file(path: Path, noise: set):
    """返回 (op_counter, n_lines_nonempty, n_ops_total, excluded_counter)。"""
    counter: Counter = Counter()
    excluded: Counter = Counter()
    n_lines = 0
    n_ops = 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return counter, 0, 0, excluded
    for raw in text.splitlines():
        line = strip_comment(raw)
        if not line.strip():
            continue
        n_lines += 1
        if ALIAS_DEF_RE.match(line) or BLOCK_LABEL_RE.match(line):
            continue
        m = OP_RE.match(line)
        if not m:
            continue
        full = m.group("q") or m.group("p")
        ns = full.split(".", 1)[0]
        if not re.fullmatch(r"[A-Za-z_][\w$]*", ns):
            continue
        if ns in noise:
            excluded[ns] += 1
            continue
        counter[ns] += 1
        n_ops += 1
    return counter, n_lines, n_ops, excluded


def parse_area(rel: Path, aliases: dict, overrides: dict | None = None):
    """从相对路径解析所属区域、以及（若为 Conversion）层间边。"""
    parts = rel.parts
    # parts[0] == 'test'
    info = {
        "area_kind": "Other",
        "area_name": "",
        "src_ns": "",
        "dst_ns": "",
        "conv_note": "",
    }
    if len(parts) < 2:
        return info
    top = parts[1]
    if top == "Dialect" and len(parts) >= 3:
        info["area_kind"] = "Dialect"
        info["area_name"] = parts[2]
        info["own_ns"] = camel_to_ns(parts[2], aliases)
    elif top == "Conversion" and len(parts) >= 3:
        info["area_kind"] = "Conversion"
        info["area_name"] = parts[2]
        ov = (overrides or {}).get(parts[2])
        if ov:
            info["src_ns"] = ov.get("src", "")
            info["dst_ns"] = ov.get("dst", "")
            info["conv_note"] = ov.get("note", "")
        else:
            m = CONV_SPLIT_RE.match(parts[2])
            if m:
                info["src_ns"] = camel_to_ns(m.group("src"), aliases)
                info["dst_ns"] = camel_to_ns(m.group("dst"), aliases)
            else:
                info["src_ns"] = ""
                info["dst_ns"] = ""
    elif top in ("Transforms", "Target", "Integration", "Analysis", "IR",
                 "Interfaces", "Rewrite", "lib", "python", "mlir-opt",
                 "mlir-rewrite", "mlir-reduce", "CAPI", "Bytecode", "Debug",
                 "ExecutionEngine", "TableGen", "Tools"):
        info["area_kind"] = top
        info["area_name"] = parts[2] if len(parts) >= 3 else ""
    else:
        info["area_kind"] = "Other"
        info["area_name"] = top
    info.setdefault("own_ns", "")
    return info


# ---------------------------------------------------------------- 主流程


def collect(mlir_root: Path, outdir: Path, cfg: dict) -> int:
    aliases = {k: v for k, v in cfg.get("aliases", {}).items() if not k.startswith("_")}
    noise = set(cfg.get("noise_dialects", {}).get("dialects", []))
    overrides = {k: v for k, v in cfg.get("conversion_overrides", {}).items()
                 if not k.startswith("_")}
    test_root = mlir_root / "test"
    if not test_root.is_dir():
        print(f"[错误] 找不到目录：{test_root}", file=sys.stderr)
        print("       请传入 llvm-project 的 mlir 目录（其中应含 test/）。", file=sys.stderr)
        return 2

    files = sorted(test_root.rglob("*.mlir"))
    if not files:
        print(f"[错误] {test_root} 下没有 *.mlir 文件。", file=sys.stderr)
        return 2

    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    unknown_ns: Counter = Counter()
    skipped_conv: Counter = Counter()
    area_counter: Counter = Counter()
    excluded_ns: Counter = Counter()

    for path in files:
        rel = path.relative_to(mlir_root)
        info = parse_area(rel, aliases, overrides)
        counter, n_lines, n_ops, excluded = scan_file(path, noise)
        excluded_ns.update(excluded)

        if info["area_kind"] == "Conversion" and not info["src_ns"] and not info["dst_ns"]:
            skipped_conv[info["area_name"]] += 1

        for ns in counter:
            if ns not in KNOWN_DIALECTS:
                unknown_ns[ns] += counter[ns]

        area_counter[f'{info["area_kind"]}/{info["area_name"]}'] += 1
        rows.append({
            "relpath": rel.as_posix(),
            "area_kind": info["area_kind"],
            "area_name": info["area_name"],
            "own_ns": info["own_ns"],
            "src_ns": info["src_ns"],
            "dst_ns": info["dst_ns"],
            "conv_note": info["conv_note"],
            "n_lines": n_lines,
            "n_ops": n_ops,
            "n_dialects": len(counter),
            "dialects": ";".join(f"{k}:{v}" for k, v in sorted(counter.items())),
        })

    csv_path = outdir / "corpus.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    meta = {
        "mlir_root": str(mlir_root),
        "git_commit": git_commit(mlir_root),
        "n_files": len(rows),
        "n_ops_total": sum(r["n_ops"] for r in rows),
        "n_lines_total": sum(r["n_lines"] for r in rows),
        "area_counts": dict(area_counter.most_common()),
        "conversion_dirs_not_parsed": dict(skipped_conv.most_common()),
        "unknown_namespaces": dict(unknown_ns.most_common(50)),
        "excluded_namespaces_ops": dict(excluded_ns.most_common()),
        "n_ops_excluded": sum(excluded_ns.values()),
        "noise_dialects": sorted(noise),
        "method_notes": [
            "只扫描 test/ 下的 *.mlir 文件。",
            "算子识别：行内注释(//)剥离后，匹配语句起始处带命名空间的算子名（含 \"quoted.op\" 形式）。",
            "属性别名/类型别名定义行（#x = ... / !t = ...）与 ^bb 块标签不计为算子。",
            "已剔除 noise_dialects 中的非方言命名空间（测试夹具、WAT 片段、伪方言等），剔除量见 excluded_namespaces_ops。",
            "builtin.module 在文本 IR 中通常写作 module（无命名空间），因此 builtin 会被显著低估；这是已知口径偏差。",
            "Conversion/<X>To<Y> 目录被解析为一条层间边 X -> Y；无法解析的目录见 conversion_dirs_not_parsed。",
            "一次统计的是测试文件数量，代表'工程投入的分布'，不代表运行时性能。",
        ],
    }
    (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] 扫描 {meta['n_files']} 个文件，{meta['n_ops_total']} 个算子，{meta['n_lines_total']} 行")
    print(f"     输出：{csv_path}")
    print(f"           {outdir / 'meta.json'}")
    if skipped_conv:
        print(f"[注意] {len(skipped_conv)} 个 Conversion 目录名无法拆成 XToY，已记录在 meta.json")
    if unknown_ns:
        top = ", ".join(f"{k}({v})" for k, v in unknown_ns.most_common(8))
        print(f"[注意] 出现已知清单外的命名空间：{top}")
    if excluded_ns:
        print(f"[剔除] 非方言命名空间 {len(excluded_ns)} 个 / {sum(excluded_ns.values())} 个算子"
              f"（见 meta.json 的 excluded_namespaces_ops）")
    return 0


def make_selftest_corpus(dst: Path) -> None:
    """生成合成样本，仅用于验证脚本逻辑，绝不可作为实验数据使用。"""
    samples = {
        "test/Dialect/Linalg/matmul.mlir": """
// RUN: mlir-opt %s | FileCheck %s
#map = affine_map<(d0, d1, d2) -> (d0, d2)>
#map1 = affine_map<(d0, d1, d2) -> (d2, d1)>
func.func @matmul(%A: tensor<16x32xf32>, %B: tensor<32x8xf32>) -> tensor<16x8xf32> {
  %cst = arith.constant 0.0 : f32
  %0 = tensor.empty() : tensor<16x8xf32>
  %1 = linalg.fill ins(%cst : f32) outs(%0 : tensor<16x8xf32>) -> tensor<16x8xf32>
  %2 = linalg.generic {indexing_maps = [#map, #map1, #map], iterator_types = ["parallel", "parallel", "reduction"]}
      ins(%A, %B : tensor<16x32xf32>, tensor<32x8xf32>) outs(%1 : tensor<16x8xf32>) {
    ^bb0(%a: f32, %b: f32, %c: f32):
      %d = arith.mulf %a, %b : f32
      %e = arith.addf %c, %d : f32
      linalg.yield %e : f32
  } -> tensor<16x8xf32>
  return %2 : tensor<16x8xf32>
}
""",
        "test/Dialect/Vector/vector-transpose.mlir": """
func.func @transpose(%v: vector<4x8xf32>) -> vector<8x4xf32> {
  %0 = vector.transpose %v, [1, 0] : vector<4x8xf32> to vector<8x4xf32>
  %1 = vector.bitcast %0 : vector<8x4xf32> to vector<32xf32>
  %2 = arith.addf %1, %1 : vector<32xf32>
  return %2 : vector<32xf32>
}
""",
        "test/Dialect/SCF/for-loop.mlir": """
func.func @loop(%lb: index, %ub: index, %step: index) {
  scf.for %iv = %lb to %ub step %step {
    %c = arith.constant 1 : i32
    memref.store %c, %m[%iv] : memref<?xi32>
  }
  return
}
""",
        "test/Conversion/TosaToLinalg/tosa-to-linalg.mlir": """
func.func @conv(%arg0: tensor<1x32x32x8xf32>, %arg1: tensor<3x3x8x16xf32>) -> tensor<1x30x30x16xf32> {
  %0 = tosa.conv2d %arg0, %arg1, %bias, %pad, %stride, %dil : (tensor<1x32x32x8xf32>, tensor<3x3x8x16xf32>, tensor<16xf32>, tensor<4xi32>, tensor<2xi32>, tensor<2xi32>) -> tensor<1x30x30x16xf32>
  %1 = linalg.conv_2d_nhwc_hwcf ins(%arg0, %arg1 : tensor<1x32x32x8xf32>, tensor<3x3x8x16xf32>) outs(%out : tensor<1x30x30x16xf32>) -> tensor<1x30x30x16xf32>
  return %1 : tensor<1x30x30x16xf32>
}
""",
        "test/Conversion/ArithToLLVM/arith-to-llvm.mlir": """
func.func @ops(%a: i32, %b: i32) -> i32 {
  %0 = arith.addi %a, %b : i32
  %1 = llvm.add %0, %0 : i32
  %2 = llvm.mlir.constant(1 : i32) : i32
  return %1 : i32
}
""",
        "test/Conversion/SCFToControlFlow/for-to-cf.mlir": """
func.func @loop(%lb: index, %ub: index, %step: index) {
  scf.for %iv = %lb to %ub step %step {
    cf.br ^bb1
  ^bb1:
    cf.br ^bb2
  ^bb2:
    return
  }
}
""",
        "test/Conversion/GPUToNVVM/lower-gpu-to-nvvm.mlir": """
gpu.module @kernels {
  gpu.func @add(%a: memref<128xf32>) kernel {
    %tid = gpu.thread_id x
    %0 = memref.load %a[%tid] : memref<128xf32>
    nvvm.barrier0
    gpu.return
  }
}
""",
        "test/Conversion/TosaToArith/tosa-to-arith.mlir": """
func.func @add(%a: tensor<4xi32>) -> tensor<4xi32> {
  %0 = tosa.add %a, %a : (tensor<4xi32>, tensor<4xi32>) -> tensor<4xi32>
  return %0 : tensor<4xi32>
}
""",
        "test/Conversion/MemRefToLLVM/memref-to-llvm.mlir": """
func.func @load(%m: memref<4xf32>) -> f32 {
  %0 = memref.load %m[%c0] : memref<4xf32>
  %1 = llvm.load %ptr : !llvm.ptr -> f32
  return %1 : f32
}
""",
        "test/Conversion/GPUCommon/common.mlir": """
gpu.module @m {
  gpu.func @f() kernel {
    gpu.return
  }
}
""",
        "test/Transforms/canonicalize.mlir": """
func.func @f(%a: i32) -> i32 {
  %0 = arith.addi %a, %c0 : i32
  return %0 : i32
}
""",
        "test/Target/LLVMIR/export.mlir": """
llvm.func @foo(%a: i32) -> i32 {
  %0 = llvm.add %a, %a : i32
  llvm.return %0 : i32
}
""",
    }
    for rel, content in samples.items():
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.lstrip("\n"), encoding="utf-8")
    print(f"[selftest] 已生成 {len(samples)} 个合成样本到 {dst}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="采集 MLIR 测试语料结构统计（零依赖）")
    ap.add_argument("--mlir-root", help="llvm-project 的 mlir 目录（应含 test/）")
    ap.add_argument("--outdir", default="out", help="输出目录")
    ap.add_argument("--config", default=None, help="layers.json 路径（仅用于取 aliases）")
    ap.add_argument("--selftest", action="store_true", help="生成合成样本并对其统计")
    args = ap.parse_args(argv)

    cfg = {}
    cfg_path = Path(args.config) if args.config else (Path(__file__).resolve().parent / "layers.json")
    if cfg_path.is_file():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    else:
        print(f"[提示] 未找到配置文件 {cfg_path}，Conversion 目录名将按朴素规则映射。", file=sys.stderr)

    if args.selftest:
        dst = Path(__file__).resolve().parent / "_selftest"
        make_selftest_corpus(dst)
        return collect(dst, Path(args.outdir), cfg)

    if not args.mlir_root:
        ap.error("需要 --mlir-root，或使用 --selftest")
    return collect(Path(args.mlir_root), Path(args.outdir), cfg)


if __name__ == "__main__":
    raise SystemExit(main())
