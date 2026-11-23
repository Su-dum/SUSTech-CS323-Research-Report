# CS323 研究报告工作区

**题目**：MLIR 的多级抽象设计及其在 AI 编译器生态中的角色——从成对适配到分层共享的复用成本分析
**截止**：11/29 23:55（正文/图表 ≤ 18 页，参考文献另 4 页，ACM 期刊模板）

## 当前状态（2026-11-23）

| 环节 | 状态 |
|---|---|
| 选题与命题 | ✅ 定稿为「成本重分配 + 条件性收益」 |
| 语料获取 | ✅ `llvm-project` @ `ba736172`，稀疏克隆只取 `mlir/` |
| 数据采集与分析 | ✅ 3,329 个测试文件 / 181,326 个算子 / 79 条方言转换边 |
| 四张图 | ✅ `out/fig1..fig4.svg`（PNG 为预览） |
| 结果解读 | ✅ [docs/04-results-v1.md](docs/04-results-v1.md)，含稳健性检验 |
| §2 对比表 | ✅ [docs/05-section2-comparison.md](docs/05-section2-comparison.md)，已核到一手文献 |
| 正文写作 | 🟡 §2 可落笔；§4 可落笔；§1/§3/§5/§6 待写 |
| ACM 模板 | ⬜ 待建 |

## 文件导航

| 文件 | 用途 |
|---|---|
| [docs/05-section2-comparison.md](docs/05-section2-comparison.md) | **§2 素材**：LLVM / Halide / TVM / XLA / Triton / MLIR 的维度对比表（含 LaTeX 版）、逐格证据、三条分析、核对过的 BibTeX |
| [docs/04-results-v1.md](docs/04-results-v1.md) | **实证结果与解读**：五条发现、对命题的修正、稳健性检验、局限。写 §4 从这里拿料 |
| [out/facts.md](out/facts.md) | 同一批数字的机器生成版（无解释），可核对 |
| [docs/01-outline-v1.md](docs/01-outline-v1.md) | 七节大纲：每节必须回答的问题、页数预算、图表位置 |
| [docs/02-experiment-design-v1.md](docs/02-experiment-design-v1.md) | 实验设计：假设、证伪判据、指标口径、成本模型推导 |
| [docs/03-data-acquisition.md](docs/03-data-acquisition.md) | 语料获取与校验（已完成，留作复现记录） |
| [ai-log.md](ai-log.md) | AI 使用日志（课程现已无强制要求，保留作为学术惯例记录） |
| `tools/collect_corpus.py` | 采集：扫 `mlir/test/**/*.mlir`，解析 `Conversion/XToY` 为层间边 |
| `tools/analyze.py` | 聚合 + 出图（SVG，零依赖）+ 生成 `facts.md` |
| `tools/diagnose_namespaces.py` | 排除某个方言前，先用它看样例行（口径透明度） |
| `tools/layers.json` | 主层划分 + 噪声方言排除表 + Conversion 目录覆盖表 |
| `tools/layers_alt.json` | 替代层划分（稳健性检验用） |
| `tools/_selftest*` | 合成样本，仅用于回归测试（⚠️ 不可作为实验数据） |

## 图表清单（当前实际文件）

| 报告中的编号 | 文件 | 承载的论点 |
|---|---|---|
| 图 1 | `out/fig3_cost_model.svg` | §1 立问题：成本交叉点 N\*，两种组织方式的规模阈值 |
| 图 2 | 手工绘制（建议） | §3 混层 IR 片段：linalg + scf + arith + memref 在同一函数体内 |
| 图 3 | `out/fig1_layer_transitions.svg` | §4 层间转换结构：汇入最深层的那束粗线 |
| 图 4 | `out/fig2_dialect_cooccurrence.svg` | §4 共现结构：`func`/`arith` 作为跨层通用语 |
| 表 1 | 手工整理 | §2 维度对比（LLVM / Halide / TVM / XLA / Triton） |
| 表 2 | `out/fig4_layer_investment.svg` 或表格 | §4 投入分布：frontend 只有 5.2% |

## 复现命令

```powershell
# 1) 语料（已完成，D:\llvm-project 已有）
git clone --depth 1 --filter=blob:none --sparse https://github.com/llvm/llvm-project.git D:\llvm-project
git -C D:\llvm-project sparse-checkout set mlir

# 2) 采集
python tools\collect_corpus.py --mlir-root D:\llvm-project\mlir --outdir out

# 3) 分析（主划分）
python tools\analyze.py --corpus out\corpus.csv --outdir out --n-frameworks 8 --n-backends 8 --adoption 0.6 --preview-png

# 4) 稳健性检验（替代划分）
python tools\analyze.py --corpus out\corpus.csv --outdir out_alt --config tools\layers_alt.json --n-frameworks 8 --n-backends 8 --adoption 0.6
```

参数说明：`M=8` 由数据实测（`target` 层内作为转换目标的方言数）；`N=8` 是生态假设，需在正文说明来源；`p=0.6` 是敏感性分析的基线，不是估计值。

## 三条写作纪律

1. **保留口径**：`out/meta.json` 里的排除项、未解析目录、未知方言，必须在方法节或 §6 交代。
2. **可追溯**：正文每个数字都要能对上 `out/facts.md` 或引用文献。
3. **别把稳健性检验藏起来**：`docs/04` 的稳健性一节已经指出哪些数字换划分就会变，如实写出来是加分项。

## 图与 LaTeX

图是纯 SVG（无 matplotlib 依赖）。Overleaf 里：

```latex
\usepackage{svg}
\includesvg[width=\linewidth]{fig1_layer_transitions}
```

不用 `svg` 宏包时用 Inkscape 转 PDF：`inkscape fig1.svg --export-filename=fig1.pdf`。
