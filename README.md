# CS323 研究报告工作区

**题目**：MLIR 的多级抽象设计及其在 AI 编译器生态中的角色——从成对适配到分层共享的复用成本分析
**作者**：蒋言、黄俊智、黄文治（南方科技大学 计算机科学与工程系）
**截止**：11/29 23:55（正文/图表 ≤ 18 页，参考文献另 4 页，ACM 期刊模板）

## 当前状态（2026-11-23）

| 环节 | 状态 |
|---|---|
| 选题与命题 | ✅ 定稿为「成本重分配 + 条件性收益」 |
| 语料获取 | ✅ `llvm-project` @ `ba736172`，稀疏克隆只取 `mlir/` |
| 数据采集与分析 | ✅ 3,329 个测试文件 / 181,326 个算子 / **76 条方言间转换** |
| 四张图 + 四张表 | ✅ 已入 `paper/figures/`，编号与正文一致 |
| 正文写作 | ✅ **§1–§7 全部成文，14 页**（正文约 12 + 参考文献约 2） |
| ACM 模板 | ✅ `acmsmall` 单栏 + `nonacm`，XeLaTeX 编译通过 |
| 参考文献 | ✅ 24 条全部编号正确并被引用；`[? ]` 与 `[n. d.]` 均为 0 |
| 编译体检 | ✅ Errors 0 / Overfull 0 / 未定义引用 0 |
| 时间序列分析 | ⬜ |

**距离 18 页上限还有 4 页余量**，见「后续工作」中可加固的方向。

## 核心数字（正文与 `out/facts.md` 一致）

| 指标 | 值 | 说明 |
|---|---|---|
| 测试文件 / 算子 | 3,329 / 181,326 | `mlir/test/**/*.mlir`，快照 `ba736172` |
| 方言间转换 `\|E\|` | **76** | 由 371 个两端可解析的 `Conversion` 文件得出；**下界**（81 个一端不定的被排除） |
| 非零层对 | 15 | 替代划分下变为 20（划分依赖，正文只用方言级数字） |
| 汇入最深层占比 | 79.2%（236/298） | 划分依赖，正文不单独引用 |
| `llvm` 入度 | 104 个文件 / 来自 19 个方言 | 硬结论：收敛在端点，不在层级 |
| 最深层内部 | 114 文件 / 8 条边 | 68 厂商二级栈 + 46 出口转向 |
| 投入分布 | 364 / 354 / 235 / 222 / 62（+73 跨层 +80 基础设施） | 导入层仅 **4.5%**，两级结构 |
| `M` / `p` | 11（实测）/ 0.6（基线） | `N*` ≈ 15.5（工程级）、4.6（架构级） |

## 仓库结构

```
paper/              论文（可直接编译）
  main.tex          acmart 主文件（acmsmall + nonacm + xeCJK）
  sections/01..07   七节正文
  references.bib    24 条文献
  figures/          五张图（正文用 4 张；`fig4_layer_investment` 因改用表格而未入正文）
docs/               写作素材与任务书（01 大纲、02 实验设计、04 结果、05–08 各节素材、09 任务书）
out/                主划分的产物（corpus.csv / facts.md / findings.json / 四张图）
out_alt/            替代划分的产物（稳健性检验）
tools/              采集、分析、出图、体检脚本（零第三方依赖）
```

## 文件导航

| 文件 | 用途 |
|---|---|
| [paper/main.tex](paper/main.tex) | 论文主文件；作者、摘要、页眉、参考书目都在这里 |
| [paper/README.md](paper/README.md) | 模板选择理由、编译方式、常见报错 |
| [docs/08-section6-limitations.md](docs/08-section6-limitations.md) | §6 素材：机制代价、七条局限、结论强度分级 |
| [docs/07-section5-stablehlo.md](docs/07-section5-stablehlo.md) | §5 素材：mhlo→StableHLO 的治理与兼容机制 |
| [docs/06-section3-figure.md](docs/06-section3-figure.md) | §3 素材：图 2 的论点与四个机制的硬主张 |
| [docs/05-section2-comparison.md](docs/05-section2-comparison.md) | §2 素材：六系统维度对比表 + 逐格证据 |
| [docs/04-results-v1.md](docs/04-results-v1.md) | 实证结果与解读：六个发现、稳健性检验、局限 |
| [out/facts.md](out/facts.md) | 同一批数字的机器生成版（无解释），可核对 |
| [docs/01-outline-v1.md](docs/01-outline-v1.md) | 七节大纲：每节必须回答的问题、页数预算 |
| [docs/02-experiment-design-v1.md](docs/02-experiment-design-v1.md) | 实验设计：假设、证伪判据、指标口径 |
| [docs/03-data-acquisition.md](docs/03-data-acquisition.md) | 语料获取与校验（复现记录） |
| `tools/collect_corpus.py` | 采集：扫 `mlir/test/**/*.mlir`，解析 `Conversion/XToY` |
| `tools/analyze.py` | 聚合 + 出图（纯 SVG，零依赖）+ 生成 `facts.md` |
| `tools/audit_attribution.py` | 查"归属失败"：被静默丢弃的方言目录与伪边 |
| `tools/layers.json` | 主层划分 + 别名 + 噪声排除表 |
| `tools/layers_alt.json` | 替代层划分（稳健性检验用，由 `make_layers_alt.py` 生成） |
| `tools/check_paper.py` | 论文静态体检：花括号/环境/引用/标签 + 过期数字黑名单 |

## 图表清单（与正文编号一致）

| 编号 | 文件 | 承载的论点 |
|---|---|---|
| 图 1 | `fig3_cost_model` | §4 成本模型：两条曲线、交叉点、敏感性 |
| 图 2 | `fig_mixed_levels` | §3 多级共存：同一 module 内整算子与显式循环并存 |
| 图 3 | `fig1_layer_transitions` | §4 层间转换结构：汇入最深层的那束粗线 |
| 图 4 | `fig2_dialect_cooccurrence` | §4 共现结构：`func`/`arith` 作为跨层通用语 |
| 表 1 | `sections/02-background.tex` | §2 六系统维度对比 |
| 表 2 | `sections/04-evidence.tex` | §4 各层投入分布（两级结构） |
| 表 3 | `sections/05-contract.tex` | §5 StableHLO 的八项契约设施 |
| 表 4 | `sections/06-limitations.tex` | §6 七条局限及对结论的影响 |

## 复现命令

```powershell
# 1) 语料（已完成，D:\llvm-project 已有）
git clone --depth 1 --filter=blob:none --sparse https://github.com/llvm/llvm-project.git D:\llvm-project
git -C D:\llvm-project sparse-checkout set mlir

# 2) 采集
python tools\collect_corpus.py --mlir-root D:\llvm-project\mlir --outdir out

# 3) 分析（主划分）——--no-title 去掉图内标题，供论文使用
python tools\analyze.py --corpus out\corpus.csv --outdir out --n-frameworks 8 --adoption 0.6 --no-title --preview-png

# 4) 稳健性检验（替代划分）
python tools\make_layers_alt.py
python tools\analyze.py --corpus out\corpus.csv --outdir out_alt --config tools\layers_alt.json --n-frameworks 8 --n-backends 11 --adoption 0.6 --no-title

# 5) 重跑后必须同步到论文目录，否则图里还是旧数字
Copy-Item out\fig*.svg,out\fig*.png paper\figures\ -Force
Copy-Item out\fig_mixed_levels.svg,out\fig_mixed_levels.png paper\figures\ -Force

# 6) 论文体检 + 编译
python tools\check_paper.py
```

参数说明：`M` 省略时**自动取实测值**（当前 11 = `target` 层内作为转换目标的方言数）；`N=8` 是生态假设，正文已说明来源；`p=0.6` 是敏感性基线，不是估计值。稳健性运行需显式传 `--n-backends 11` 以与主划分可比。

## 编译论文

本机（无需装完整 TeX Live）：

```powershell
$env:TECTONIC_CACHE_DIR = "$env:TEMP\tectonic-cache"
& "$env:TEMP\tectonic-msvc\tectonic.exe" main.tex   # 在 paper/ 目录下
```

Overleaf：**必须选 XeLaTeX**（含中文，pdfLaTeX 会报 `Unicode character 的 not set up`）。
若参考文献显示 `[? ]`，用 **Menu → Recompile from scratch** 清掉旧的 `.bbl` 缓存。

## 写作纪律

1. **保留口径**：`out/meta.json` 里的排除项、未解析目录、未知方言，必须在方法节或 §6 交代。
2. **可追溯**：正文每个数字都要能对上 `out/facts.md` 或引用文献。
3. **别把稳健性检验藏起来**：哪些数字换划分就会变，如实写出来是加分项。
4. **图内不写标题**：标题与编号由 LaTeX caption 提供，图里再画一遍是重复。

---

# 后续工作

分三档，按"交稿前要不要做"排序。

## 一、交稿前值得做的（1–2 小时量级）

1. **补上时间序列**(docs/09-timeseries-task.md)
   现状：`|E|` 只有单点数据，"随硬件家族增长"只能写成假说。
   产出后可在 §4 新增「发现七」，把假说升级为趋势证据；**若曲线是平的，同样要如实写**——
   那说明 `|E|` 的规模由层结构决定，与硬件数量无关，是一个有价值的反向结论。


## 二、把论文做扎实（半天到两天）

5. **把语料从 1 个仓库扩到 4 个**
   现在只统计 `llvm-project/mlir/test`，所以"栈顶碎片化"只能由投入分布**间接推断**。
   把 `torch-mlir`、`stablehlo`、`onnx-mlir` 的测试语料并入，可以直接看到
   `torch → stablehlo → linalg` 这条链在仓库间的分裂程度，§6 的那条局限就能删掉。

6. **把 `|E|` 从等权计数换成加权计数**
   现在一条 `Conversion` 目录算 1。实际各目录的 pass 数量与代码行数差很多
   （`TosaToLinalg` 与 `GPUToNVVM` 显然不是一个量级）。用 `git grep -c "Pattern"` 或
   目录内文件数做权重，可以得到更接近真实工程成本的 `|E|`，同时回答"哪些边界最贵"。

7. **直接检验机制三（op interface 的复用率）**
   现在机制三是**从设计文献推出来的**，没有实测。可行做法：统计 `mlir/lib` 里
   `matchAndRewrite` 中依赖 `OpInterface` 的比例，与"按具体方言特化"的 pass 对比。
   如果 interface 复用率确实高，$N+M$ 的技术根据就有了语料支撑；如果不高，
   这是对本文最有力的一处反驳，应当写进去。

8. **访谈 2–3 个真正做过 MLIR 接入的人**（实习同事、学长）
   本文的"契约成本"完全来自文档推断。哪怕只有两段半结构访谈，
   也能把 §5 从"文档分析"变成"经验证据"，这是当前证据链最弱的一环。

## 三、可以延伸成投稿的（数周量级）

9. **与 XLA 做同口径量化对照**
   §2 目前只是机制对比。若按同一套口径统计 XLA 仓库的 HLO pass 数与 backend 数，
   就能画出"两种答案的成本曲线"，把"谁承担不确定性"从定性讨论变成定量比较。

10. **细化成本模型**
    现在 `p` 是单一采纳率。真实的采纳是**分层**的（`linalg` 被广泛采纳、`tosa` 未必），
    可以写成 $p_i$ 与 $|E_i|$ 的矩阵形式，做参数区间分析，
    回答"哪一层最值得标准化"——这比"要不要用 MLIR"更有决策价值。
