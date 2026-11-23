# -*- coding: utf-8 -*-
"""从 layers.json 重新生成 layers_alt.json（稳健性检验用）。

alt 划分 = 主划分，但把 target 层拆成「通用出口层」+「厂商指令方言层」，其余一律同步。
这样 aliases / noise / conversion_overrides / crosslayer / infra 都不会漂移。
"""
import copy
import json
from pathlib import Path

here = Path(__file__).resolve().parent
base = json.loads((here / "layers.json").read_text(encoding="utf-8"))
alt = copy.deepcopy(base)

GEN = ["llvm", "spirv"]
for L in alt["layers"]:
    if L["id"] == "target":
        L["id"] = "generic_exit"
        L["label_zh"] = "通用出口层"
        L["label_en"] = "generic exit (LLVM / SPIR-V)"
        L["rationale"] = "稳健性检验用：只保留被全行业接受的通用出口（LLVM 与 SPIR-V）"
        L["dialects"] = GEN

_tgt = next(L for L in base["layers"] if L["id"] == "target")
VENDOR = sorted(set(_tgt["dialects"]) - set(GEN))
alt["layers"].append({
    "id": "vendor",
    "label_zh": "厂商指令方言层",
    "label_en": "vendor ISA",
    "order": 6,
    "rationale": "稳健性检验用：厂商自有的指令级方言，各自独立",
    "dialects": VENDOR,
})

(here / "layers_alt.json").write_text(
    json.dumps(alt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("layers_alt.json 已重新生成；层:", [L["id"] for L in alt["layers"]])
print("vendor 方言:", VENDOR)
