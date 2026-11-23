# §5 素材：共享契约是怎么被建立的（mhlo → StableHLO）

> 这一节回答的是 §4 结论里那个"条件性"到底是**什么条件**。
> §3 讲的是 MLIR 提供的**能力**（层可协商）；§5 要讲的是这种能力**被兑现时付出了什么**。
> 全部材料来自一手来源，核对状态见末尾。

---

## 1. 为什么这一节是必需的

§4 的结论是："分层共享的收益取决于共享层是否被多方采纳（p）。"
但这句话本身还没解释：**为什么采纳这件事不是免费的？** 如果只是"大家都用同一个方言"，那它应该很快发生。

`mhlo → StableHLO` 的迁移正好提供了答案：**把一个方言变成契约，需要一整套制度性设施**——版本号、序列化格式、兼容窗口、逐 PR 的兼容测试、以及明确写出"不保证什么"。这些东西都不在 MLIR 框架里。

---

## 2. 时间线（每个节点都可查证）

| 时间 | 事件 | 来源 |
|---|---|---|
| — | MHLO 作为独立孵化仓库存在于 `tensorflow/mlir-hlo`，定位是"独立于 TensorFlow 与 XLA 的端到端流程"、"作为把技术上游化的孵化器" | [mlir-hlo README](https://github.com/tensorflow/mlir-hlo) |
| 2022-08-04 | `openxla/stablehlo` 仓库创建 | GitHub API `created_at` |
| 2022-09-12 | 兼容性 RFC：建立"什么算兼容、怎么测"的流程 | [`rfcs/20220912-compatibility.md`](https://github.com/openxla/stablehlo/blob/main/rfcs/20220912-compatibility.md) |
| 2023-03-02 | v0.9.0 发布 | Releases |
| 2023-05-17 | 前向兼容测试 RFC | [`rfcs/20230517-forward-compatibility-testing.md`](https://github.com/openxla/stablehlo/blob/main/rfcs/20230517-forward-compatibility-testing.md) |
| 2023-06-23 | **v1.0 兼容性 RFC**：确定 5 年 / 2 年窗口 | [`rfcs/20230623-compatibility.md`](https://github.com/openxla/stablehlo/blob/main/rfcs/20230623-compatibility.md) |
| 2024-05-14 | **v1.0.0 发布**：98 个算子全部规格化（含 verifier 与类型推断） | [Release notes](https://github.com/openxla/stablehlo/releases/tag/v1.0.0) |
| 现状 | `tensorflow/mlir-hlo` 标记 **deprecated**，代码规范位置迁到 `openxla/xla/xla/mlir_hlo`，官方建议"All dependencies on MHLO should go through XLA. Users of MHLO should migrate to StableHLO whenever possible." | mlir-hlo README 首段 |

> 注意措辞：官方用的是 **deprecated + 迁移建议**，理由不是"MHLO 语义有缺陷"，而是它没有版本化与序列化契约。写正文时不要写成"MHLO 不好所以被替换"。

---

## 3. StableHLO 相对 MHLO 加了什么（这是全节的核心表）

StableHLO 官方对自己的定位是："基于 MHLO dialect，并**增加了序列化与版本化**"，以此提供前后向兼容保证。
把这句话展开就是下表——**新增的全是契约设施，不是算子语义**：

| 机制 | 具体做法 | 为什么它构成"契约" |
|---|---|---|
| **定位** | "portability layer between ML frameworks and ML compilers" | 它明确承担"接口"角色，而非"某个编译器的内部 IR" |
| **序列化** | portable artifact 用 MLIR bytecode；`stablehlo-translate`、C++、Python 三种入口 | 让"同一个程序"能跨版本、跨进程传递 |
| **版本号** | `#.#.#`：minor 随 opset 或序列化格式变更递增；patch 随发布递增，**发布是每周一次** | 任何变更都有名字、可被引用 |
| **不可回填** | 版本一旦被 supersede 就不能再添加内容；变更必须开新 minor | 旧版本的语义被**冻结**，不是"大致不变" |
| **VHLO 方言** | 把"版本化"本身做成一个 dialect（`stablehlo/dialect/VhloOps.td`）；序列化时 StableHLO → 目标版本的 VHLO | 旧 artifact 的读写有**明确目标**，而不是靠尽力而为 |
| **兼容窗口** | **5 年**向后兼容 + **2 年**向前兼容（v1.0 Compatibility RFC） | 承诺有年限、可被测试 |
| **CI 门槛** | 每个 PR 都测双向兼容；目标版本取"main 上至少 4 周 / 12 周前被 supersede 的最新版本"（`WEEK_4` / `WEEK_12`） | 承诺变成**流水线里的断言**，不是文档里的口号 |
| **规格化** | 98 个算子全部写进 spec，含 verifier 与类型推断；另有参考解释器 | 语义可判定，才谈得上"语义相同" |
| **显式排除** | Out of scope：**prettyprinted IR 与裸 bytecode 不保证兼容**；未规格化的特性不保证；实现与 spec 冲突时允许破坏兼容（"bug compatibility" 不保证） | 契约的**边界是写出来的**，因此可被检验 |

来源：[stablehlo README](https://github.com/openxla/stablehlo)、[docs/compatibility.md](https://github.com/openxla/stablehlo/blob/main/docs/compatibility.md)、[v1.0.0 release notes](https://github.com/openxla/stablehlo/releases/tag/v1.0.0)。

---

## 4. 三条推论（正文的落点）

**推论 A｜契约的成本是治理成本，不是实现成本。**
上表里没有一行是"再实现一个算子"。成本集中在：5 个 RFC 的讨论、每周发版、一个 VHLO 方言、逐 PR 的双向兼容测试套、以及一份写清 out-of-scope 的文档。这些开销与"这层有多少算子"无关，与"有多少方依赖它"有关。

**推论 B｜这套治理能力不在 MLIR 里。**
`compatibility.md` 的 "Future work" 明确写道：他们计划**把兼容性测试套贡献回 MLIR 上游**（issue #1632），以便在 MLIR bytecode 基础设施里更早发现意外破坏。也就是说，**在贡献之前，这套契约是 StableHLO 自己立法、自己执行、自己承担**的。

这一条直接支撑 §4 的结论：MLIR 提供的是**机制**（dialect、bytecode、interface、progressive lowering），而"某个层被多方采纳"这件事需要**采用者自己建立制度**。所以 p 不是给定的，是被治理出来的——这就是"收益条件性"的机制解释。

**推论 C｜契约必须显式排除一些东西，才成立。**
Out of scope 三条（prettyprinted IR、未规格特性、bug compatibility）说明：一个可辩护的契约不是"什么都能保证"，而是"明确保证这些、明确不保证那些"。

这一条接得上 §3 的机制④（conversion target / legality 让边界可声明）：**边界可声明，不等于边界免费**。声明边界本身要成本，而且必须写清反面。

---

## 5. 正文写法建议（约 1.5 页）

1. **开篇一句**：§3 说明了 MLIR 有能力让层被协商，但没说明协商成功需要什么。本节用一个真实迁移案例回答。
2. **第 2 段：MHLO 的位置问题**。它在 `tensorflow/mlir-hlo` 独立仓库里、定位是孵化器；用它当"框架与编译器之间的接口"，等于把跨组织的接口放在一个项目的内部 IR 上。
3. **第 3 段 + 表**：StableHLO 的增量全部是契约设施（序列化、版本、VHLO、兼容窗口、CI）。这里用一个数字定锚：**5 年向后 / 2 年向前 / 每周发版**。
4. **第 4 段：三条推论**，重点落在推论 B。
5. **收束一句**（建议原话）：

> 由此可见，MLIR 让"层"可被协商，但把某一层变成各方都敢依赖的契约，需要采用者自建版本、序列化与兼容测试制度；这部分成本不体现在转换数量 `|E|` 里，却决定了共享层采纳率 `p` 能否真正上去。

---

## 6. 不要写成什么

- ❌ "MHLO 被淘汰是因为设计不好"——官方措辞是 deprecated + 迁移建议，原因是缺少版本化与序列化契约。
- ❌ "StableHLO 解决了碎片化"——它解决的是**框架↔编译器这一段的接口稳定**，不解决栈顶各家私有方言（这正是 §4 发现 3 的另一面）。
- ❌ 把 5 年 / 2 年当作技术指标或性能数字——它是**治理承诺**，且只在"以指定方式创建的 portable artifact"上有效。
- ❌ 说"MLIR 提供了兼容性保证"——MLIR 提供 bytecode 基础设施；兼容性保证是 StableHLO 建立的（见推论 B，有 issue #1632 为证）。
- ✅ 安全的强表述："StableHLO 把版本化本身实现成了一个方言（VHLO），并把兼容性写成每个 PR 都要通过的测试。"

---

## 7. 核对状态（2026-11-23）

| 事实 | 核对方式 | 状态 |
|---|---|---|
| 仓库创建时间 2022-08-04 | GitHub API `created_at` | ✅ |
| v1.0.0 发布于 2024-05-14；98 个算子规格化 | Releases API + release notes 原文 | ✅ |
| 5 年向后 / 2 年向前兼容 | `docs/compatibility.md` 原文 | ✅ |
| 每周发布、minor/patch 递增规则、版本不可回填 | `docs/compatibility.md` `## Versions` | ✅ |
| VHLO 存在于 `stablehlo/dialect/VhloOps.td` | HTTP 200 | ✅ |
| 兼容测试套路径 `stablehlo/tests/vhlo/stablehlo_legalize_to_vhlo.mlir` | HTTP 200 | ✅ |
| 5 个兼容性 RFC 的文件名 | GitHub API 列 `rfcs/` | ✅ |
| mlir-hlo deprecated、建议迁移 StableHLO | mlir-hlo README 首段原文 | ✅ |
| "Future work: 把兼容性测试套贡献回 MLIR 上游（#1632）" | `docs/compatibility.md` `## Future work` | ✅ |
| `WEEK_4` / `WEEK_12` | `docs/compatibility.md` `## Versions` 与 `## Guarantees` | ✅ |

> 一处未核：issue #1632 的具体内容与状态我没打开（只引用了 `compatibility.md` 对它的描述）。若正文要写"该测试套尚未上游化"，请先确认该 issue 仍然 open。

---

## 8. BibTeX

```bibtex
@misc{stablehlo_repo,
  author       = {{OpenXLA Project}},
  title        = {{StableHLO}: Backward Compatible {ML} Compute Opset Inspired by {HLO}/{MHLO}},
  howpublished = {\url{https://github.com/openxla/stablehlo}},
  note         = {Accessed 2026-11-23}
}

@misc{stablehlo_compat,
  author       = {{OpenXLA Project}},
  title        = {{StableHLO} Compatibility},
  howpublished = {\url{https://github.com/openxla/stablehlo/blob/main/docs/compatibility.md}},
  note         = {Accessed 2026-11-23}
}

@misc{stablehlo_spec,
  author       = {{OpenXLA Project}},
  title        = {{StableHLO} Specification},
  howpublished = {\url{https://github.com/openxla/stablehlo/blob/main/docs/spec.md}},
  note         = {Accessed 2026-11-23}
}

@misc{stablehlo_v1,
  author       = {{OpenXLA Project}},
  title        = {{StableHLO} v1.0 Release},
  howpublished = {\url{https://github.com/openxla/stablehlo/releases/tag/v1.0.0}},
  year         = {2024},
  note         = {Released 2024-05-14; accessed 2026-11-23}
}

@misc{mlirhlo_repo,
  author       = {{OpenXLA Project}},
  title        = {{MLIR-HLO}: A Standalone {HLO} {MLIR}-based Compiler (deprecated)},
  howpublished = {\url{https://github.com/tensorflow/mlir-hlo}},
  note         = {Deprecation notice in README; accessed 2026-11-23}
}

@misc{stablehlo_rfc_v1_compat,
  author       = {{OpenXLA Project}},
  title        = {{StableHLO} v1.0 Compatibility {RFC}},
  howpublished = {\url{https://github.com/openxla/stablehlo/blob/main/rfcs/20230623-compatibility.md}},
  year         = {2023}
}

@misc{stablehlo_rfc_compat,
  author       = {{OpenXLA Project}},
  title        = {{StableHLO} Compatibility {RFC}},
  howpublished = {\url{https://github.com/openxla/stablehlo/blob/main/rfcs/20220912-compatibility.md}},
  year         = {2022}
}

@misc{stablehlo_rfc_fwd,
  author       = {{OpenXLA Project}},
  title        = {Forward Compatibility Testing {RFC}},
  howpublished = {\url{https://github.com/openxla/stablehlo/blob/main/rfcs/20230517-forward-compatibility-testing.md}},
  year         = {2023}
}
```
