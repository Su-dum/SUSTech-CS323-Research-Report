# §2 素材：只选一层的代价（维度对比）

> 这一节的目标**不是**评判哪个系统更好，而是回答一个可客观回答的问题：
> **每个系统把"抽象层"固定在了哪里？固定在那里之后，硬件知识和新前端分别从哪个口子进入？**
>
> 三者都是事实问题，可以用官方文档和论文回答；"哪个更好"不在本节出现。

---

## 1. 表 1（正文用）

| 系统 | 固定的抽象层 | 该层的计算单位 | 硬件知识进入点 | 新增一个前端要做什么 | 新增一个后端要做什么 | 复用的最小单位 |
|---|---|---|---|---|---|---|
| **LLVM IR** | 一层：目标无关 SSA IR | 三地址码、标量/向量指令 | 指令选择（ISel）、调度、MC 层 | 生成 LLVM IR（保留类型与内存语义） | 实现 TargetLowering / InstrInfo / ISel 模式 | pass、指令选择模式 |
| **Halide** | 一层：函数式 Halide IR（算法）+ 调度 | 图像/张量函数、循环与存储指令 | 调度原语（tile/vectorize/parallel）与后端 | 用 C++ 内嵌 DSL 写算法 | 接入一个后端（LLVM 或 CUDA/OpenCL/Metal/DX12 等） | 调度原语、后端 |
| **TVM** | 两层：图级（Relax）+ 算子级（TensorIR） | 图：张量算子 DAG；算子：显式循环程序 | 算子级调度（tensor intrinsic、内存布局）与 target 专属下放 | 把模型导入成图级 IR | 提供 target 描述 + 算子级 codegen（或 BYOC 走外部编译器） | 调度原语、tensor intrinsic、BYOC 后端 |
| **XLA** | 一层：HLO（现以 StableHLO 为接口） | 高阶张量算子（含 shape 与 layout） | **HLO 内部**：layout assignment 等 pass，以及后端的 HLO 级重写 | 生成 StableHLO 图 | 实现 `xla::Compiler` 接口 + HLO→后端 IR 的 lowering | HLO pass、后端 lowering |
| **Triton** | 一层：tile 级程序（`tt` 方言） | 块/tile 上的张量运算 + 显式 grid 模型 | tile 级布局（`ttg` 的 blocked encoding、共享内存分配）与厂商方言（`nvg`/`amdg`） | 从 Python DSL 生成 tile 级程序 | 增加一个厂商方言 + 相应 lowering | dialect、tile 级原语 |
| **MLIR**（参照） | **不固定**：层的位置与数量都不是设计参数 | 取决于当前 dialect | 可在任意 dialect 边界进入 | 定义/复用一个前端 dialect | 定义/复用一个目标 dialect + 转换 | dialect、转换、interface |

### LaTeX 版本（acmart 单栏，`\small`）

```latex
\begin{table*}[t]
\caption{各系统把抽象层固定在何处，以及硬件知识与新前端的进入点。所有条目均为可核对的机制描述，不含性能优劣判断。}
\label{tab:layer-fixing}
\small
\begin{tabularx}{\textwidth}{@{}l p{2.0cm} p{2.1cm} p{2.4cm} p{2.3cm} p{2.5cm} p{1.9cm}@{}}
\toprule
系统 & 固定的抽象层 & 该层的计算单位 & 硬件知识进入点 & 新增前端 & 新增后端 & 复用单位 \\
\midrule
LLVM IR & 一层：目标无关 SSA IR & 三地址码、标量/向量 & 指令选择、调度、MC 层 & 生成 LLVM IR & 实现 TargetLowering / ISel & pass、ISel 模式 \\
Halide & 一层：算法 + 调度 & 图像/张量函数 & 调度原语与后端 & 用内嵌 DSL 写算法 & 接入一个后端 & 调度原语 \\
TVM & 两层：图级 + 算子级 & 算子 DAG；循环程序 & 算子级调度与 target 下放 & 导入为图级 IR & target 描述 + codegen / BYOC & 调度原语、intrinsic \\
XLA & 一层：HLO & 高阶张量算子 & HLO 内部 pass 与后端重写 & 生成 StableHLO & 实现 Compiler 接口 + lowering & HLO pass \\
Triton & 一层：tile 级 & tile 上的张量运算 & tile 布局与厂商方言 & 生成 tile 级程序 & 厂商方言 + lowering & dialect、tile 原语 \\
MLIR & 不固定 & 取决于 dialect & 任意 dialect 边界 & 定义前端 dialect & 定义目标 dialect + 转换 & dialect、转换、interface \\
\bottomrule
\end{tabularx}
\end{table*}
```

> 排版提示：7 列在单栏里会挤。两个选择——① 用 `table*` 跨栏（上面的写法）；② 拆成两张表：左半（系统 / 固定层 / 计算单位 / 硬件进入点）与右半（系统 / 新增前端 / 新增后端 / 复用单位）。我建议跨栏一张表，读者能一次横向比较。

---

## 2. 每个单元格的证据

**LLVM IR**：设计目标即"目标无关 + 生命周期内持续优化"（[Lattner & Adve, CGO 2004](https://dl.acm.org/doi/10.1145/996841.996859)）。硬件知识必然落在 IR 之下：指令选择、调度、MC 层。这条不需要额外论证，但**值得在正文里明确写一句**：LLVM IR 并非"不含硬件知识"，而是把硬件知识全部推迟到了 IR 之后。

**Halide**：核心贡献是把算法与调度解耦（[SIGGRAPH 2012](https://dl.acm.org/doi/10.1145/2185520.2185528)、[PLDI 2013](http://people.csail.mit.edu/jrk/halide-pldi13.pdf)）。官方站点列出的目标是 x86/ARM/MIPS/Hexagon/PPC/RISC-V，以及 CUDA/OpenCL/OpenGL Compute/Metal/DX12（[halide-lang.org](https://halide-lang.org/)）——也就是说，**同一份算法配不同调度与后端**，这正是"把硬件知识外置成调度"的做法。可引为"解耦思想早于 MLIR 十余年"的谱系证据。

**TVM**：官方摘要明确写"exposes graph-level and operator-level optimizations"，并把"mapping to arbitrary hardware primitives"列为要解决的问题（[TVM, OSDI 2018 / arXiv:1802.04799](https://arxiv.org/abs/1802.04799)）。图级 IR 现为 Relax（早期为 Relay），算子级为 TensorIR，两者在 TVM 文档中并列（[tvm.apache.org/docs/arch](https://tvm.apache.org/docs/arch/index.html)）。硬件知识主要进入在**算子级调度**：tensor intrinsic、内存布局、以及 target 相关的下放规则。

**XLA**：三段式流程是官方写明的——① 在 StableHLO 上做**目标无关**的 pass，并转成内部 HLO；② 交给后端做**目标相关**的 HLO 级优化；③ 后端生成 LLVM IR 再交给 LLVM（[XLA architecture](https://github.com/openxla/xla/blob/main/docs/architecture.md)；而下面引的 "Retargeting XLA…" 那句出自 [developing_new_backend.md](https://github.com/openxla/xla/blob/main/docs/developing_new_backend.md)，不是 architecture.md）。layout 在 HLO 内部就以显式 pass 的形式被指派（[From HLO to Thunks § Layout assignment passes](https://github.com/openxla/xla/blob/main/docs/hlo_to_thunks.md)）。新后端的路径是"实现 `xla::Compiler` 接口"（[Developing a new backend](https://github.com/openxla/xla/blob/main/docs/developing_new_backend.md)）。

> ⚠️ **这一条是全节最有力的引用**。XLA 官方文档原话：
> "Retargeting XLA should be significantly simpler and more scalable than implementing every existing op from a frontend framework such as PyTorch or TensorFlow for new hardware."
> 也就是说，**"避免 N×M"这个论证不是我事后附会，而是 XLA 自己写下来的设计动机**。用它可以让 §1 的问题陈述立刻落地，而且完全不必评判优劣——两个项目在同一个问题上给了两种不同的答案。

**Triton**：定位即"tiled neural network computations"（[MAPL 2019](https://dl.acm.org/doi/10.1145/3315508.3329973)）。**关键事实：Triton 本身就是 MLIR 上的一组 dialect**——`tt`（Triton IR）、`ttg`（TritonGPU，含布局）、`ttng`/`nvg`（NVIDIA）、`amdg`（AMD），见 [Triton MLIR Dialects 文档](https://triton-lang.org/main/dialects/dialects.html)。

> ⚠️ **千万不要把 Triton 写成"绕开通用层的反例"**。它是 MLIR 的**纵向用法**：只保留必要的一两级，把 tile 级钉死，然后一路下到厂商方言。这个观察比"反例"有价值得多，因为它说明 MLIR 被生态用成了两种形态：
> - **横向**（IREE、OpenXLA + StableHLO）：栈宽、方言多、目标是覆盖多框架多硬件；
> - **纵向**（Triton、Mojo）：栈窄、方言少、目标是单一域做到极致。
>
> 这两种用法都能成立，恰恰是"层的位置不是设计参数"这一点的证据。建议把这一段放进 §3 而不是 §2，因为它需要读者先理解 dialect。

**MLIR**：设计原则见 [CGO 2021](https://ieeexplore.ieee.org/abstract/document/9370308) 与 [arXiv:2002.11054](https://arxiv.org/abs/2002.11054)。注意用词：论文用的是 "software fragmentation"、"reduce the cost of building domain specific compilers"，**没有**"多级抽象层数可任意配置"这种表述——所以正文这句话要写成分解式的：MLIR 没有把"层"当作可配置参数来宣传，但它的机制（dialect + interface + progressive lowering）使层的位置与数量不再是框架的固定前提。这个区别很重要，别写成"MLIR 声称层数可任意"。

---

## 3. 表 1 之后的三个分析（这是拿分的地方）

**分析 A：层的"位置"是一个守恒量，不是可以省掉的量**

五行里没有一行是"无层"的——每一行都选了**一个**（TVM 选了两个）。能变的只是"选在哪"。所以严格的说法不是"有了 MLIR 就不需要选层"，而是：

> 抽象层的**位置**可以随域调整，抽象层的**总量**不会消失。MLIR 改变的是"谁来做这个选择、以及能否在同一程序里保留多个选择"，而不是"可以不做选择"。

这句话如果写进 §2 末尾，会直接把 §1 的命题从"MLIR 提供更多层"提升到"MLIR 把选层从架构决策变成可局部化的决策"。

**分析 B：固定点越低，前端越厚、后端越薄；反之亦然**

- LLVM IR 固定在最低处 → 前端必须承担全部语义下降（Clang 的活），后端只需 ISel；
- XLA 固定在高处 → 前端只需产 StableHLO（很薄），后端必须扛 HLO 级的所有目标相关重写（很厚）；
- Halide / TVM / Triton 落在中间的不同高度。

这是一个**权衡曲线**，不是优劣排序。可以在正文配一句：每个系统都在曲线上选了不同的点，而选择依据是"它预期自己要被多少个前端复用、被多少个后端支持"——这正好接回 §1 的成本模型（N 与 M 的相对大小决定最优固定点）。**这一句能让 §1 和 §2 真正咬合**，是全文结构上最值钱的一处衔接。

**分析 C：XLA 与 MLIR 是同一个问题的两种答案，不是"新旧"**

两者都明确以"避免为每个硬件重写所有算子"为动机（引 XLA 那句原文 + MLIR 的 software fragmentation）。差别在**谁来承担不确定性**：

- XLA 把不确定性收进后端，保证 HLO 这一层稳定；
- MLIR 把不确定性放到 dialect 边界上，允许边界本身被重新协商。

这个对比完全不需要说谁更好，但它解释了 §4 的实证结果：如果 MLIR 的成功取决于边界能否被协商成功，那么**边界的协商成本**就成了关键变量——正好是 §5（mhlo→StableHLO）要讲的事。

---

## 4. 写这一节时不要做的事

- ❌ 不要写"XLA 只有一个 IR，所以不如 MLIR 灵活"。XLA 的 HLO 内部有完整的 pass 流水线（含 layout assignment、fusion），说它"只有一个 IR"在技术上不准确。
- ❌ 不要写"Halide 只支持图像处理"。官方目标包含张量处理，且调度模型被 TVM/MLIR 继承。
- ❌ 不要写"Triton 绕开了 MLIR"（见上）。
- ❌ 不要把"复用单位"列写成"谁的复用单位更小所以更好"。小单位意味着更细的复用，也意味着更多的组合与更高的治理成本——这是 §6 的内容。
- ✅ 每一行的"新增后端要做什么"都必须能指向一个具体的接口或文档页面。凡是写不出具体动作的格子，说明你还没读懂，先删掉。

---

## 5. BibTeX（可直接进 `references.bib`）

```bibtex
@inproceedings{llvm04,
  author    = {Lattner, Chris and Adve, Vikram},
  title     = {{LLVM}: A Compilation Framework for Lifelong Program Analysis \& Transformation},
  booktitle = {Proceedings of the International Symposium on Code Generation and Optimization (CGO)},
  pages     = {75--86},
  year      = {2004},
  doi       = {10.1109/CGO.2004.1281665}
}

@inproceedings{halide13,
  author    = {Ragan-Kelley, Jonathan and Barnes, Connelly and Adams, Andrew and Paris, Sylvain and Durand, Fr{\'e}do and Amarasinghe, Saman},
  title     = {Halide: A Language and Compiler for Optimizing Parallelism, Locality, and Recomputation in Image Processing Pipelines},
  booktitle = {Proceedings of the 34th ACM SIGPLAN Conference on Programming Language Design and Implementation (PLDI)},
  pages     = {519--530},
  year      = {2013},
  doi       = {10.1145/2491956.2462176}
}

@article{halide12,
  author  = {Ragan-Kelley, Jonathan and Adams, Andrew and Paris, Sylvain and Levoy, Marc and Amarasinghe, Saman and Durand, Fr{\'e}do},
  title   = {Decoupling Algorithms from Schedules for Easy Optimization of Image Processing Pipelines},
  journal = {ACM Transactions on Graphics},
  volume  = {31},
  number  = {4},
  pages   = {1--12},
  year    = {2012},
  doi     = {10.1145/2185520.2185528}
}

@inproceedings{tvm18,
  author    = {Chen, Tianqi and Moreau, Thierry and Jiang, Ziheng and Zheng, Lianmin and Yan, Eddie and Cowan, Meghan and Shen, Haichen and Wang, Leyuan and Hu, Yuwei and Ceze, Luis and Guestrin, Carlos and Krishnamurthy, Arvind},
  title     = {{TVM}: An Automated End-to-End Optimizing Compiler for Deep Learning},
  booktitle = {Proceedings of the 13th USENIX Symposium on Operating Systems Design and Implementation (OSDI)},
  pages     = {578--594},
  year      = {2018}
}

@inproceedings{triton19,
  author    = {Tillet, Philippe and Kung, H. T. and Cox, David},
  title     = {Triton: An Intermediate Language and Compiler for Tiled Neural Network Computations},
  booktitle = {Proceedings of the 3rd ACM SIGPLAN International Workshop on Machine Learning and Programming Languages (MAPL)},
  pages     = {10--19},
  year      = {2019},
  doi       = {10.1145/3315508.3329973}
}

@inproceedings{mlir21,
  author    = {Lattner, Chris and Amini, Mehdi and Bondhugula, Uday and Cohen, Albert and Davis, Andy and Pienaar, Jacques and Riddle, River and Shpeisman, Tatiana and Vasilache, Nicolas and Zinenko, Oleksandr},
  title     = {{MLIR}: Scaling Compiler Infrastructure for Domain Specific Computation},
  booktitle = {Proceedings of the IEEE/ACM International Symposium on Code Generation and Optimization (CGO)},
  pages     = {2--14},
  year      = {2021},
  doi       = {10.1109/CGO51591.2021.9370308}
}

@misc{xla_arch,
  author       = {{OpenXLA Project}},
  title        = {{XLA} Architecture},
  howpublished = {\url{https://github.com/openxla/xla/blob/main/docs/architecture.md}},
  note         = {Accessed 2026-11-23}
}

@misc{xla_thunks,
  author       = {{OpenXLA Project}},
  title        = {From {HLO} to Thunks},
  howpublished = {\url{https://github.com/openxla/xla/blob/main/docs/hlo_to_thunks.md}},
  note         = {Accessed 2026-11-23}
}

@misc{xla_backend,
  author       = {{OpenXLA Project}},
  title        = {Developing a New Backend for {XLA}},
  howpublished = {\url{https://github.com/openxla/xla/blob/main/docs/developing_new_backend.md}},
  note         = {Accessed 2026-11-23}
}

@misc{triton_dialects,
  author       = {{Triton Project}},
  title        = {Triton {MLIR} Dialects and Ops},
  howpublished = {\url{https://triton-lang.org/main/dialects/dialects.html}},
  note         = {Accessed 2026-11-23}
}
```

### 核对状态（2026-11-23）

已用 Crossref API 与 USENIX 官方 BibTeX 逐条核对，**修正了两处**：

| 条目 | 原稿 | 核对后 |
|---|---|---|
| `llvm04` | DOI `10.1145/996841.996859`，pages 75–88 | **DOI `10.1109/CGO.2004.1281665`，pages 75–86** |
| `halide12` | 无页码 | **pages 1–12** |

其余已确认：`halide13` DOI/页码 519–530；`tvm18` pages 578–594（USENIX BibTeX）；`triton19` DOI/页码 10–19；`mlir21` pages 2–14（[mlir.llvm.org/pubs](https://mlir.llvm.org/pubs/)）。

> `mlir21` 的 DOI 已补：IEEE CGO 2021 的 `10.1109/CGO51591.2021.9370308`（pages 2–14）。
> 另：XLA 的 "Retargeting XLA…" 引文出自 `developing_new_backend.md`；早前标成 architecture.md 是错的，已更正。
