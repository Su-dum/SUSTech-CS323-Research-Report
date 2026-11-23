# SUSTech-CS323-Research-Report 审查报告

审查时间：2026-11-23。对象：`Su-dum/SUSTech-CS323-Research-Report`（main 分支，commit 60bf978）。
方法：通读 README + docs/01–08 + out/out_alt 全部产物 + layers 配置；逐行审查 tools/ 脚本并在本地重跑验证；对全部外部引用（论文元数据、官方文档、RFC、GitHub 记录）用 Crossref / GitHub API / 官方站点逐一核实。

---

## 一、总评

这个仓库的**文献功夫和论证意识是过硬的**：§2 对比表、§5 StableHLO 案例、§6 局限分级、"禁止出现的主张"清单，都是远超课程作业平均水平的设计。我抽查核实的**全部外部事实无一失实**（见第二节）。

问题集中在**数据管线**：三个系统性缺陷（Dialect 目录别名缺失、Conversion 目录名误解析、命令行参数与发布数字脱节）让几个"招牌数字"失真或无法按 README 复现。其中**投入分布统计静默丢掉了 233 个文件（21.6%）**，直接动摇发现 3 的"四高均匀、前端独低"叙事，是发布前必须修的第一优先级问题。

---

## 二、核实无误的事实（可以放心写进正文）

以下全部经一手来源逐字核对：

| 事实 | 核实结果 |
|---|---|
| StableHLO 仓库创建于 2022-08-04 | ✅ GitHub API `created_at` |
| v0.9.0 发布于 2023-03-02；v1.0.0 发布于 2024-05-14 | ✅ Releases API |
| v1.0.0 规格化 **98 个算子**（含 verifier 与类型推断） | ✅ Release notes 原文 |
| 兼容窗口 **5 年向后 / 2 年向前**；每周发版；版本不可回填；WEEK_4 / WEEK_12 | ✅ compatibility.md 原文 |
| 兼容测试套路径 `stablehlo/tests/vhlo/stablehlo_legalize_to_vhlo.mlir`；逐 PR 双向兼容测试 | ✅ compatibility.md |
| "Future work: 把兼容性测试套贡献回 MLIR 上游（#1632）"；**该 issue 仍然 open** | ✅ GitHub API（state: open）——docs/07 里"一处未核"可以落定为"尚未上游化" |
| 5 个兼容性相关 RFC 文件名（20220912 / 20230309 / 20230517 / 20230525 / 20230623） | ✅ rfcs/ 目录列表 |
| mlir-hlo 弃用措辞（"All dependencies on MHLO should go through XLA. Users of MHLO should migrate to StableHLO whenever possible."） | ✅ README 逐字一致 |
| XLA 原话 "Retargeting XLA should be significantly simpler and more scalable than implementing every existing op…" | ✅ 逐字准确，**但出处是 `developing_new_backend.md`，docs/05 标成了 architecture.md**（见 B-13） |
| XLA 三段式流程、hlo_to_thunks 的 "Layout assignment passes"、新后端 = 实现 `xla::Compiler` | ✅ 三个文档均核实 |
| Triton 方言名：`tt`/`ttg`/`ttng`/`nvg`/`amdg` | ✅ triton-lang.org/main/dialects 当前列表一致 |
| Halide 目标列表（x86/ARM/MIPS/Hexagon/PPC/RISC-V + CUDA/OpenCL/OpenGL Compute/Metal/DX12） | ✅ halide-lang.org 逐字一致 |
| TVM 摘要 "exposes graph-level and operator-level optimizations"、"mapping to arbitrary hardware primitives" | ✅ arXiv:1802.04799 逐字一致 |
| MLIR 论文用词 "software fragmentation"、"reduce the cost of building domain specific compilers"；无"层数可任意配置"表述 | ✅ arXiv:2002.11054 摘要 |
| 参考文献元数据（llvm04/halide12/halide13/tvm18/triton19/mlir21 的 DOI、页码、作者） | ✅ Crossref 逐条核对，全部正确 |
| **可补的 DOI**：MLIR CGO'21 = `10.1109/CGO51591.2021.9370308`（pages 2–14） | docs/05 里"未取到"的一处，现已核实可填 |
| 图 2 源文件 `matmul-vs-matvec.mlir` 在语料 commit `ba736172` 存在；"节选 29 行、未改写" | ✅ 文件存在（3,247 字节）；脚本逐行渲染不改文本，行号段与文件内容比对一致 |
| 成本模型算术：N\*=(\|E\|+M)/(p·M−1)、p 敏感性（29.33/22.0/17.6/12.57/9.78）、C_pair 80 vs C_layer 128.0/64.0、230/291=79.0%、114 文件/8 条边、68+46、替代划分 106/291=36.4%、18 个非零层对 | ✅ 全部复算一致 |
| layers_alt.json 与主划分的差异（target → generic_exit + vendor） | ✅ 与文档描述一致 |

---

## 三、错误与问题（按严重度排序）

### A 级｜影响发布数字，发布前必须处理

**A1. 投入分布（发现 3 / 表 2 / fig4）静默漏掉 233 个文件 —— 最严重**

`collect_corpus.py` 的 `camel_to_ns()` 对无别名键的 `test/Dialect/<Name>` 目录名做驼峰切分，产生错误的命名空间，analyze.py 对归属失败的文件**不计数、不告警**：

| 目录 | 文件数 | 得到 | 应为 |
|---|---|---|---|
| `Dialect/LLVMIR` | 86 | `llvmir`（丢弃） | `llvm` → target 层 |
| `Dialect/SparseTensor` | 122 | `sparsetensor`（丢弃） | `sparse_tensor` → tensor 层 |
| `Dialect/X86` | 19 | `x`（正则 `[A-Z]+(?![a-z])` 对 "X86" 只匹配到 "X"） | `x86` → target 层 |
| `Dialect/MLProgram` | 6 | `mlprogram`（丢弃） | `ml_program` → frontend 层 |

已发布数字 259/235/232/222/56/73 失真；修正后约为 **target 364、tensor 354、frontend 62**（另有 80 个 infra 目录与 2 个病态行，共 315 个文件未归属）。后果：
- "frontend 只占 5.2%" 应为 ≈4.7%（结论方向不变，数字要改）；
- "四个中后段层几乎均匀（20.6%–24.0%，差不到 4 个百分点）"**修正后不成立**（16.9%–27.8%）。发现 3 的"四高一起"叙事需要改写为"目标层与张量层最高、并行与存储层次之"。
- 修复：给 aliases 加 `LLVMIR→llvm`、`SparseTensor→sparse_tensor`、`X86→x86`、`MLProgram→ml_program`，并让 analyze.py 对未归属目录告警/报告。

**A2. |E|=78 掺了 7 条垃圾边；真实值 ≈71，N\*≈16.2**

`CONV_SPLIT_RE` 贪婪切分把非标准目录名"解析成功"成垃圾命名空间，且 `conversion_dirs_not_parsed` 只在 src/dst 都为空时记录（几乎永不触发），meta.json 里该项为空 `{}`——**垃圾解析零告警**：

| 目录 | 被解析成 | 应该是 |
|---|---|---|
| `GPUToLLVMSPV`（3 文件） | `gpu→llvmspv` | `gpu→llvm`（SPIR-V 分支） |
| `ArithAndMathToAPFloat`（2） | `arithandmath→apfloat` | 多源，应单独覆盖 |
| `ComplexToLibm` / `MathToLibm` | `…→libm` | `complex/math→func` |
| `ComplexToROCDLLibraryCalls` | `…→rocdllibrarycalls` | `complex→rocdl` |
| `VectorToAMX`（2） | `vector→amx`（amx 是真方言，但 layers.json 没收） | `vector→amx`，补 layers |
| `TosaToMLProgram` | `tosa→mlprogram` | `tosa→ml_program` |

这 11 个文件对应 7 条边仍在 |E| 里（且抬高了"目标方言 29"的计数），却不进层矩阵。剔除后 **|E|≈71**，工程级 N\*(p=0.6, M=10) 从 17.6 变为 **≈16.2**（结论方向不变，但"下界 78"的说法必须改为"71"并如实交代这两处修复）。

**A3. README 复现命令与发布数字自相矛盾（M=8 vs M=10）**

- analyze.py 的 `--n-backends` **不会被数据实测值覆盖**（`M_measured=10` 只打印一行叙述，不回写成本表；默认值还是 6）。
- README 复现命令写 `--n-backends 8`，旁边又解释"M=10 由数据实测"——脚本里没有这条逻辑，M=10 是手工传参的。
- 用 README 命令重跑：p=0.6 时 N\*=**22.63**（不是 17.6），C_pair 64 vs C_layer 119.6（不是 80 vs 128.0），fig3 也变。
- 修复：README 命令改成 `--n-backends 10`，或让脚本在缺省时自动采用实测 M。

**A4. "371 个（82.1%）能解析出确定的层间边"口径有水**

371 个"两端非空"的文件里：11 个是垃圾端点（A2）、66 个以 crosslayer 方言（arith/func/math/index/ub/shape）为源、真正能映射到层对的**只有 48 条边对应的文件**。docs/04 发现 1 还混用两种口径："79.0%（230/291）"排除了 crosslayer 源，而"101 文件/18 方言汇入 llvm"又包含它们。建议：把 371 改写成"两端均可解析为命名空间的 371 个（其中 X 个可映射到层对）"，并给 79.0% 加一句口径注。

**A5. "3,309 个 // RUN: 文件 / 356 个用 -pass-pipeline（10.8%）"全仓库无任何工具产出**

`strip_comment` 把 `//` 之后全部裁掉，RUN 行根本不进统计；tools/ 里没有统计 RUN 行的脚本。这个数字写进正文将不可复现。修复：补一个小统计脚本，或删掉这个证据（§6 代价 3 的论证可以改用机制性表述）。

**A6. out_alt 稳健性产物质量差**

- `write_facts` 把 "target" 字样写死：out_alt/facts.md 出现"落到 **target** 层的边 106/291"（实际是 vendor）、"target 层内部：0"、"实测目标端点数：0"等无意义句子；
- analyze.py 从 outdir 读 meta.json，而 out_alt/ 里没有 meta.json → out_alt/facts.md 第 1 节写着"计入算子：**0** 个"；
- README 稳健性命令同样写 `--n-backends 8`，与产物（M=10）不符。

**A7. docs/04 稳健性表"架构级 N\* = 4.3"与仓库自身产物矛盾**

out_alt/facts.md 的非零层对是 **18** → N\*(p=0.6, M=10) = (18+10)/5 = **5.6**，不是 4.3。"小幅变"的定性说法仍成立，但数字必须改成 5.6。

### B 级｜文档内部一致性与论证问题

**B1. 同一数字两套取值、无口径标注**：facts.md §2 入度表 spirv=**72**、emitc=**21**（含源不定的 ConvertToSPIRV/ConvertToEmitC）；docs/04 发现 1 表 spirv=**57**、emitc=**19**（不含）。两表都叫"文件数"，引用时极易拿错。

**B2. docs/08 L2 家族表缺 72 个文件**：表格列了 299 个文件（CPU 101、AMD 65、通用 GPU 57、Intel 33、NVIDIA 21、C/C++ 19、Arm 3），分母却是 371；剩下 72 个落在中间层目标（scf 13、cf 12、linalg 8、gpu 6 等），一句话都未交代。

**B3. "AMD/Intel/NVIDIA 合计 118 个文件"应为 119**（65+33+21）。docs/04 局限四条里出现。

**B4. "架构级门槛约 8 个前端"与自家表格矛盾**：架构级 N\* 在 p=0.6 时是 **4.8**；"8"是 p=0.4 时的值。"工程级 12–23"对应 p∈[0.5,0.8]，同样没说 p。要么标注 p，要么统一口径。

**B5. docs/01 页数预算加错**：0.4+1.5+2.0+3.5+3.5+1.5+1.5+0.4 = **14.3** 页，正文写"合计约 16.3 页"。

**B6. 发现 2 的因果归因夸大**："14→78 的原因**正是**厂商在目标层内部展开子栈"——厂商内二级栈只贡献 **3 条边**（68 个文件，amdgpu→rocdl / xegpu→xevm / nvgpu→nvvm）；14→78 的膨胀主要来自**各层边界内的多个方言对**（如 parallel→target 里有 gpu→{spirv,rocdl,nvvm}、scf→spirv、omp→llvm 等）。正确说法："厂商内二级栈是 |E| 的一部分来源，但方言对粒度本身才是 14→78 的主因"。

**B7. "|E| 不随层数增长，而随硬件家族数及其内部级数增长"没有被数据证明**：这是单一仓库、单一快照下的假说（缺少时间序列或跨仓库对照）。建议要么软化为"本文数据与该假说一致"，要么加一个对照数据点（见建议 C-5）。

**B8. "这解释了为什么 MLIR 在 2020–2023 年被广泛采纳"无出处，且与自家模型有张力**：在 N=8、M=10、p=0.6 下，模型说分层**更贵**（128 vs 80）。采纳的解释需要额外机制（|E| 的社区摊销，见建议 C-4），不能从门槛数字直接推出。

**B9. docs/08 "MOLIR" 拼写错误**（"不能说'MOLIR 的共享收益…'"）。

**B10. 发现 3 称 frontend 转换源"只有 tosa（外加极少量 ml_program）"**：实际上 TosaToMLProgram 因映射失败被丢弃（A2），正文只能写"只有 tosa 一个"。

**B11. meta.json 的自检承诺落空**：layers.json 注释称"凡未列出的 dialect 会落入 other，脚本会在 meta.json 里报告"，但 analyze.py 根本不读 `infra` 节、也不报告未归属；conversion_dirs_not_parsed 恒为空（A2）。docs/02 的"提交前必查"清单因此失效。

**B12. check_paper.py 名不副实**：只做 LaTeX 静态体检 + 一份硬编码过期黑名单，从不读 facts.md 对账——抓不住 A1/A2/A7 这类不一致。README 还引用了不存在的 `ai-log.md`。

**B13. XLA 引文的出处标错文档**：引文本身逐字准确，但它在 `developing_new_backend.md` 里，docs/05 的标注指向 `architecture.md`。

### C 级｜小问题

- C1. make_fig_mixed_levels.py 的行号硬编码、对文件内容零断言——换 LLVM commit 图会静默截错（"未改写"声明本身属实）。
- C2. `KNOWN_DIALECTS` 有 `"armsme"` 拼写错误和大量重复项（仅影响提示，不影响数字）。
- C3. docs/03 路线 2 建议用 llvmorg-21.1.0 源码包，但语料实际是 main @ ba736172——两处口径建议统一说明。
- C4. out_alt 没有 meta.json、没有语料 commit 记录——稳健性运行的可复现记录比主运行弱。

---

## 四、可补充的素材、证据、观点

### 素材 / 证据类（直接可加）

**C-1. N=8 的计数口径（§1 待办项）**：用 [mlir.llvm.org/users](https://mlir.llvm.org/users/)（约 60 个公开项目）列一个表：PyTorch（torch-mlir）、TensorFlow、JAX、ONNX（onnx-mlir）、NumPy（numba-mlir 概念验证）、IREE 等，明确"框架前端"的入选标准。另外 XLA architecture.md 有现成句子："XLA supports several ML framework frontends (including PyTorch, TensorFlow, and JAX)"——可直接引。

**C-2. M 的敏感性分析（模型目前只对 p 做了敏感性）**：N\* 对 M 比对 p 更敏感——|E|=71、p=0.6 下，M=6→32.3，M=8→22.6，M=10→17.6，M=15→11.6（近 3 倍摆动）。补一张 M 敏感性表，方法学上更完整。注意：M=10 把 llvm/spirv 这种通用出口与 rocdl/nvvm 等指令级方言混在一层计数，与发现 2 的"两级栈"有张力，正文要交代口径。

**C-3. p 的语义要钉死**：若 p 是"每侧独立采纳率"，被共享层覆盖的对数是 **p²·N·M** 而非 p·N·M；文档现在按"走共享层的对的占比"理解。一句话定义清楚即可，另可注明 (1−p)·N·M 与 +N+M 两个固定成本项如何随采纳缩放。

**C-4. |E| 的社区摊销（这是最值钱的观点补充）**：模型中 |E| 是"每条边界实现一次"的成本，但 MLIR 上游/社区实现一次后所有采用者共享。单组织的 C_layer = |E|+N+M 高估了生态视角的成本；而"被广泛采纳"的机制恰恰是 **|E| 由社区一次性支付、各采用者只付 N+M 的边际成本**。加上这一段，B8 的张力就解开了，§4 与 §1 的叙事真正闭环。

**C-5. 时间维度证据（支撑 B7 的假说）**：对 llvm-project 的历史 tag（llvmorg-12.x 起每隔几个版本）跑一遍 collect_corpus，画出 Conversion 目录数 / 方言对数随时间的增长曲线——xegpu/vcix/arm_sme 等硬件方言是何时加入的。成本约半小时，能把"|E| 随硬件家族增长"从假说变成趋势证据。

**C-6. "瓶颈方言"分析（发现 1 的延伸）**：算一下汇入 target 的边中有多少经 gpu/vector/memref 等少数中间方言（数据里 gpu→{spirv,rocdl,nvvm}、vector→{llvm,xegpu,nvgpu} 等），可以得到"星形收敛的上游也是少数瓶颈点"的第二层结构，比单讲 llvm 更深。

**C-7. §5 可加的数字（全部已有出处）**：
- v0.9.0 只承诺 **1 个月**兼容、并说"plan to scale up to 5 years later this year"→ v1.0 兑现 5 年/2 年——治理承诺的"棘轮"曲线；
- v0.9.0 发布说明里的"572 commits、15 contributors、6+ months"；
- XLA architecture.md 现称 StableHLO 为 "a versioned operation set … that provides a portability layer between ML frameworks and the compiler"——直接引这句给 §5 定位；
- compatibility.md 的 #1632 已确认仍 open，"尚未上游化"可以放心写。

**C-8. 一句话说明 MLIR 机制超出 AI 生态**（Flang/FIR、ClangIR、CIRCT）——反向印证"层的位置不是设计参数"，一句话即可，不占篇幅。

**C-9. §2 表 1 的 MLIR 行是"机制描述"而非实测**——加脚注声明，避免评审误读成与 §4 同等强度的证据。

**C-10. 图 2 的选材脚注**：docs/06 已说明"393 个候选中选它不是最高分、是判断而非随手"，正文脚注别漏——这恰恰是可信度的加分点。

---

## 五、建议的修复顺序（发布前）

1. **修 aliases**（LLVMIR/SparseTensor/X86/MLProgram 四个键）+ analyze.py 对未归属目录告警 → 重跑 → 更新 facts/findings/fig4 与发现 3 全部数字（4.7% 等）。
2. **修 Conversion 解析**：给 GPUToLLVMSPV、ArithAndMathToAPFloat、*ToLibm、ComplexToROCDLLibraryCalls、TosaToMLProgram、VectorToAMX 加 conversion_overrides；layers.json 补 amx；让解析失败目录进 meta 报告 → 重跑 → |E| 78→71，N\* 17.6→16.2，更新全部引用。
3. **统一参数**：README 两条命令的 `--n-backends` 改为 10（或改脚本默认取实测 M）。
4. **修 out_alt**：write_facts 去硬编码 "target"；补 meta.json；重跑；docs/04 稳健性表 4.3→5.6。
5. **修文档级错误**：B1–B5、B9、B10、B13 的措辞/数字；决定 3,309/356 去留（A5）。
6. **补证据**：C-4（摊销观点）与 C-1（N 口径）优先，时间允许再做 C-5/C-6。

---

## 附录：证据强度与复现性（补充说明，2026-11-23）

本报告结论按"证据强度"分三级，引用时请注意区分：

### 字节级复现验证（最强）

子代理在本地用仓库自带脚本重跑验证：

- 用 `--n-backends 10 --n-frameworks 8 --adoption 0.6` 重跑，生成的 `facts.md` 与 `out/facts.md` **逐字节一致**，fig1–4 与 findings.json 也一致 → 发布产物确实来自 **M=10**；
- 用 README 的 `--n-backends 8` 重跑：N\*(p=0.6)=**22.63**（p=0.4→39.09、0.5→28.67、0.8→15.93、1.0→12.29），C_pair 64 vs C_layer 119.6 → 与发布数字 17.6 / 80 vs 128.0 全部不同；
- 默认值（不带 `--n-backends`）是 M=6、N\*=32.31 —— 同一份 facts.md 会自相矛盾（"实测 M=10"那一行是死文本，不随参数变）；
- 自测夹具重跑与 `_selftest_out` 完全一致，主产物在正确参数下确定、可复现 → **修复后重跑成本很低，结果可信**。

### 代码阅读 + 数据复算（次强）

- A1 的 233 文件：我用 artifacts 复算（259 = 除 LLVMIR/X86 外的 target 目录之和；58 = SPIRV 54 + LLVM 4）独立得到 364/354/62，与子代理"315 个文件未归属、其中 233 明确属层"一致；
- A2 的 |E| 78→71 与"48 条可映射层对"：我从 371 个文件的构成（21 条 crosslayer 对 + 1 条 infra + 1 条 tosa→arith + 7 条垃圾边 = 30 条非层对）独立推出 48，与子代理一致；
- A7 的 4.3 vs 5.6：我从 out_alt/facts.md 的"18 个非零层对"直接算出 (18+10)/5 = 5.6；
- 子代理补充的细节：`check_paper.py` 的 STALE 黑名单内容（`|E|=79`、`22.9`、`7.7`、`16.1`、`39.6`、`M=8`、`79 条/个`、`MLVM`）——这暴露了一个历史线索：**|E|=79 曾是旧稿数值、且"MLVM"拼写错误此前修过一次**；终稿数字应统一为修复后的 |E|≈71、N\*≈16.2，并把 STALE 表当作"历史遗物"清理，而不是当成对账工具。
- 图 2 的行号段：8–19 行是 `@matmul`、21–37 行是 `@matvec`，12+17=29 行，与"节选 29 行"一致（但行号硬编码、对文件内容零断言，见 C1）。

### 推断（最弱，需自己复核）

- B7（|E| 随硬件家族增长的假说）——单一快照，未做时间序列；
- A4 中"66 个 crosslayer 源文件"的精确构成——按目录名推得，未逐文件跑数；
- "MLIR 在 2020–2023 被广泛采纳"的历史叙述——无一手引用。

> 提醒：子代理的结论与我的独立复核在 A1/A2/A3/A7 上完全一致，但**它自身也值得抽查**（例如"逐字节一致"需要它本地确实跑通了脚本；你如果要对外引用，建议自己按附录命令重跑一次）。
