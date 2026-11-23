# §3 素材：图 2 与四个机制

> 图已生成：[out/fig_mixed_levels.svg](../out/fig_mixed_levels.svg)（PNG 仅预览）。
> 生成脚本：[tools/make_fig_mixed_levels.py](../tools/make_fig_mixed_levels.py)，
> 选材脚本：[tools/find_multilevel_snippets.py](../tools/find_multilevel_snippets.py)。

---

## 1. 这张图要证明什么

§3 的第二个机制主张是：**多级 IR 共存于同一个 module，是 progressive lowering 的前提**。
图 2 用真实语料把这句话变成可看的东西——同一个文件里，同一个矩阵乘同时以两种抽象高度存在：

- `@matmul`：**一次** `linalg.matmul` 完成整个矩阵乘，没有显式循环；
- `@matvec`：`scf.for` + `linalg.matvec` + `memref.subview`，循环与内存搬运都显式化。

两段都是合法 IR，在同一个 module 里共存。**由此可以推出三件事**，正好对应报告需要的论证：

1. "下降"不必整段一次性完成——可以只下降一部分（图里 `@matvec` 被显式化了，`@matmul` 没有）；
2. 层的边界是可选的工程决策，而不是 IR 合法性的硬约束；
3. 因此"复用"的最小单位可以是**一条转换**，而不是"一整条编译流水线"——这直接支撑 §4 的 `|E|` 计数口径。

## 2. 图注（可直接用）

> **图 2** 同一 module 内的多级抽象共存。选自 `llvm-project@ba736172` 的
> `mlir/test/Integration/Dialect/Linalg/CPU/matmul-vs-matvec.mlir`，节选 29 行，未改写。
> 左侧色条标出该行算子所属的抽象层。`@matmul` 以单个 `linalg.matmul` 表达整个矩阵乘；
> `@matvec` 中同一计算已被显式化为 `scf.for` 循环与子算子 `linalg.matvec`。
> 两者共存于同一 module，说明下降可以是部分的。

## 3. LaTeX 引入

```latex
\begin{figure*}[t]
\centering
\includesvg[width=\textwidth]{fig_mixed_levels}
\caption{同一 module 内的多级抽象共存。……}
\label{fig:mixed-levels}
\end{figure*}
```

不用 `svg` 宏包时先转 PDF：`inkscape fig_mixed_levels.svg --export-filename=fig_mixed_levels.pdf`。

> 版式提示：图宽 950 px、高 662 px，长宽比约 1.43。跨栏（`figure*`）时按 `\textwidth`
> 缩放，代码字号约 7.5pt，是可读的下限；**不要再缩小**。若要放进单栏，建议只截 `@matvec`
> 那一段（17 行），并把右侧括号标签移到图下方。

## 4. 选材说明（如果被问到"为什么用这个文件"）

- **为什么不用 tensor 与 memref 并存的例子**：那样展示的是 bufferization 边界（语义模型不同），
  与本节要讲的"抽象高度不同"是两件事，容易讲混。当前选材只涉及 buffer 语义，变量单一。
- **为什么是 4 层**：`linalg`（张量代数）+ `scf`（并行控制）+ `memref`（存储）+ `arith/func`
  （跨层通用）。这正好覆盖 §4 层划分里的三层加跨层通用。
- **为什么不是整个文件**：全文 76 行里含 `@main`（初始化与校验），与本图论证无关，已省略并标出。

## 5. §3 的另外三个机制（对照用）

图 2 只承担第 2 条。其余三条不需要图，但各自要有一句能被追问的硬主张：

| 机制 | 必须在正文写出的那句话 | 可引 |
|---|---|---|
| ① dialect 可扩展 | dialect 把"算子集合 + 类型/属性 + 验证与规范化"整套搬到库边界，新增一层不必改编译器内核 | [MLIR CGO'21](https://ieeexplore.ieee.org/abstract/document/9370308)；ODS 文档 |
| ③ **op interface** | pass 通过 interface 对**它不认识的方言**仍然生效——这是 N+M 可加性的技术根源，而不只是命名空间隔离 | [Interfaces](https://mlir.llvm.org/docs/Interfaces/) |
| ④ conversion target / legality | 层与层之间的边界是**可声明**的契约（legality + type converter），因此"边界"本身成为可检验对象 | [Dialect Conversion](https://mlir.llvm.org/docs/DialectConversion/) |

> 第 ③ 条是这一节最容易被写浅的地方。常见的浅写法是"interface 让不同 dialect 共享同一套操作"；
> 有力的写法是："**一条转换不必重写**，因为它可以只依赖 interface 而不依赖具体方言"——
> 这正好解释了 §4 里 `|E|` 为什么能停留在 79 而不是爆炸。

## 6. 图的复现

```powershell
python tools\find_multilevel_snippets.py --mlir-root D:\llvm-project\mlir --min-layers 3 --list 20
python tools\make_fig_mixed_levels.py --mlir-root D:\llvm-project\mlir --preview-png
```

选材脚本会在 3,329 个文件里按"层数 + 规模 + 纯净度 + 是否跨越 bufferization 边界"打分，
输出 393 个候选（≥3 层）。当前选定的是其中 `matmul-vs-matvec.mlir` 的两个函数，
不为分数最高者——**分数最高的是稀疏张量集成测试（55 行，含 GPU 目标层），对 §3 太杂**。
这个取舍本身值得在正文脚注里说一句，表明选材是判断而非随手。
