# 任务：MLIR 方言对数量的时间序列（C-5）

> 这是交给同学执行的独立任务。**自包含**，不需要读仓库里其它文档。
> 预计 0.5–1 个工作日（含下载）。产出交回给报告作者。

---

## 1. 一句话目标

在 **4–6 个历史版本的 LLVM 仓库存档**上重跑现有分析管线，得到"方言对数量 `|E|` 随时间的增长曲线"，
把一个目前只是**假说**的论断升级为**趋势证据**。

## 2. 为什么这件事重要（你交付的东西会让报告多一条硬结论）

报告现在的第 4 节有一个论断：

> `|E|`（真正要写的方言对数量）**随硬件家族数增长**，不随层数增长。

这条目前只有**单个时间点**的支撑（一个 commit 的横截面数据），因而只能写成"假说"。
如果你能给出 `|E|` 随时间的变化，这条就变成**趋势**，报告里那句"假说"可以改成实测结论。
反之，**如果曲线是平的**，那也是一个有价值的发现（说明 `|E|` 的规模由层结构决定、与硬件数量无关），
同样要如实报告——**不要为了"结果好看"去挑 tag**。

## 3. 已经就绪的东西（你不需要重写）

仓库里已有完整管线，你只需要**换输入**：

| 文件 | 作用 |
|---|---|
| `tools/collect_corpus.py` | 扫描 `<mlir-root>/test/**/*.mlir`，输出 `corpus.csv` + `meta.json`（含 commit） |
| `tools/analyze.py` | 聚合出 `facts.md`、`findings.json` 与四张图 |
| `tools/layers.json` | 层划分与方言别名配置（**本次任务不要改它**） |

已实测的基线（`llvm-project@ba736172`，即 2026-11 的 main）：
测试文件 3,329 个、算子 181,326 个、`|E|=76`、非零层对 15、M（实测目标端点数）11。

## 4. 环境

Windows + Python 3.12（仓库自带解释器可用）。**不需要**装 LaTeX。
仅需 `git` 与 Python 标准库——管线零第三方依赖。

## 5. 步骤

### 5.1 选 tag 并拉语料

建议 **4 个起步**，确认可行后再补到 6 个：

```
llvmorg-15.0.7   llvmorg-17.0.6   llvmorg-19.1.7   llvmorg-20.1.8
```

（已代为核对：这些 tag 在仓库里**确实存在**，是各主版本最新的 patch tag。
若要补点，可用 `llvmorg-16.0.6`、`llvmorg-18.1.8`、`llvmorg-21.1.8`。
注意 19 以后 patch 号规则变成 `19.1.x`，不是 `19.0.x`。）

每个 tag 用**稀疏克隆**，只取 `mlir/` 一层，放到仓库**之外**的目录（例如 `D:\llvm-series\<tag>`）：

```powershell
cd D:\llvm-series
git clone --depth 1 --branch <tag> --filter=blob:none --sparse `
    https://github.com/llvm/llvm-project.git <tag>
cd <tag>
git sparse-checkout set mlir
```

记录版本与日期（后面要用）：

```powershell
git -C D:\llvm-series\<tag> rev-parse HEAD
git -C D:\llvm-series\<tag> log -1 --format=%cI
```

### 5.2 每个 tag 跑一次管线

```powershell
$tag = "llvmorg-17.0.6"
python tools\collect_corpus.py --mlir-root D:\llvm-series\$tag\mlir --outdir series\out\$tag
python tools\analyze.py --corpus series\out\$tag\corpus.csv --outdir series\out\$tag `
    --n-frameworks 8 --n-backends 11 --no-title
```

三个必须遵守的参数：

| 参数 | 为什么 |
|---|---|
| `--n-backends 11` | **必须固定**。若让它自动取实测 M，各 tag 的 M 不同，`N*` 的变化会被 M 的变化污染，曲线无法解释。固定成基线的 11，M 的实测值另记一列。 |
| `--no-title` | 去掉图内标题（这些图会进论文，标题由 LaTeX caption 提供） |
| `--outdir series\out\<tag>` | **不要**写进 `out/`，否则覆盖基线的产物 |

### 5.3 汇总成一张表

写一个 `tools/series.py`（**自己写**，约 60–80 行即可），读每个 tag 的
`series/out/<tag>/findings.json` 与 `meta.json`，抽成 `series/facts.csv`：

| 列 | 取值来源 |
|---|---|
| `tag` | 你给的标签 |
| `commit` | `meta.json` 的 `git_commit`（前 7 位即可） |
| `date` | `git log -1 --format=%cI` 得到的 commit 日期 |
| `n_files` | `meta.json` 的 `n_files` |
| `n_ops` | `meta.json` 的 `n_ops_total` |
| `n_dialects` | `corpus.csv` 中出现过的**不同方言命名空间数**（去重计数） |
| `E` | `findings.json` → `structure.n_distinct_dialect_pairs` |
| `E_per_1k_files` | `E / n_files * 1000`（**归一化，必算**） |
| `layer_pairs` | `findings.json` → 层矩阵里非零元素个数 |
| `M_measured` | `findings.json` → `cost_model.M_measured` |
| `target_share` | `findings.json` → `structure.share_edges_landing_in_deepest_layers` |
| `frontend_share` | `investment.files_per_layer["frontend"] / investment.attributed_total` |

### 5.4 画图

一张折线图 `series/series.svg`：横轴 = commit 日期，纵轴 = 三条线
（`E`、`n_dialects`、`M_measured`；若量纲差太多就做双轴或画两个子图）。
再附一条 `E_per_1k_files` 以排除"语料变大导致 `|E|` 变大"的混淆。

图要能看出：**增长是否真的跟硬件/目标方言的增加同步**。

### 5.5 写一页结论

`series/README.md`，包含：
- 你实际用的 tag 列表与日期；
- 上面那张表；
- **三句话结论**：曲线形状是什么、与哪条论断一致或不一致、有没有反例；
- 你踩到的任何口径问题。

## 6. 交付物（直接提交到仓库）

```
series/
  TASK.md            # 本文件（可从 docs/ 复制或直接软链，别删）
  facts.csv          # 汇总表
  series.svg         # 折线图
  README.md          # 一页结论
  out/<tag>/         # 每个 tag 的 facts.md / findings.json / meta.json
tools/series.py      # 你写的汇总脚本
```

**不要提交**：`D:\llvm-series\` 下的任何克隆（每个约 80 MB，仓库会被撑大；
`.gitignore` 已挡住 `llvm-project/`、`mlir/`，但请你自己确认）。

## 7. 验收标准

1. `python tools/series.py` 能从零重建 `facts.csv`，不需要手工填数字；
2. 每个 tag 的 `out/<tag>/meta.json` 里 `git_commit` 与该 tag 一致（防止拷错目录）；
3. `facts.csv` 里同时有**绝对值**与**归一化值**（`n_files` 与 `E_per_1k_files`）；
4. 图上每个点都能追溯到某个 tag 与日期；
5. `series/README.md` 的结论与 `facts.csv` 一致，没有夸大。

## 8. 已知的坑（按踩到概率排序）

1. **`|E|` 的增长可能只是语料变大。** 后续版本的 `mlir/test` 文件数本身在增长，
   `|E|` 自然变大。所以**必须**同时报 `E_per_1k_files` 与 `n_dialects`。
   真正有意义的信号是**不同方言/目标端点的数量增加**（`n_dialects`、`M_measured`），
   而不是测试文件数增加。
2. **老 tag 可能没有某些目录。** 那是正常的，正是要观察的东西；不要为了"对齐"去删新 tag 的目录。
3. **`--n-backends` 一定要钉死 11**，否则 `N*` 的漂移来自参数而非事实。
4. **不要把不同 tag 的结果混进同一个 `outdir`**，也别覆盖 `out/`（基线）。
5. **`--depth 1 --branch <tag>` 与 `--sparse` 的顺序**：先 clone 再 `sparse-checkout set mlir`；
   若 `--filter=blob:none` 报错（老 git），去掉它，体积会大一些但能跑。
6. **tag 名规则随版本变**：15–18 是 `llvmorg-17.0.6` 这种，19 以后是 `llvmorg-19.1.7`。
   本文档第 5.1 节的四个 tag 已核对存在；要加别的点请先
   `git ls-remote --tags https://github.com/llvm/llvm-project.git | findstr llvmorg` 确认。
7. **日期不是 tag 的发布日期**，而是该 tag 指向 commit 的日期——用 `git log -1 --format=%cI`，
   不要用 GitHub 的 release 日期（会引入几周偏差）。
8. **磁盘**：6 个 tag 约 2–3 GB。不够就先做 4 个。

## 9. 时间预估

| 步骤 | 时间 |
|---|---|
| 拉 4 个 tag（含网络） | 20–40 min |
| 跑管线（每 tag 约 1 min） | 5 min |
| 写 `series.py` + 出表 | 40 min |
| 画图（SVG，可用现有图的风格参考） | 30 min |
| 写一页结论 + 复核 | 30 min |
| **合计** | **约 2–3 小时**（若网络慢则 +30 min） |

## 10. 做不了 / 中途失败怎么办

- **网络拉不动 tag**：先只做 2 个（例如 15 与 19），给出"两端对比"，也比没有强；
  在 `series/README.md` 里写明只做了两个。
- **老 tag 编译不了管线**（例如目录结构差异导致 `collect_corpus.py` 报错）：
  不要改 `collect_corpus.py` 的核心逻辑；在 issue 里贴出报错与 tag 名，先跳到下一个 tag。
- **`M_measured` 在某些 tag 上为 0**（说明该版本的 `target` 层没有任何转换目标）：
  这本身是数据，记录并在 README 说明，不要人为填值。

## 11. 交给谁复核

完成后把 `series/facts.csv` + `series/series.svg` + `series/README.md` 三件东西发回给报告作者，
由他把结论并进报告的第 4 节（新增"发现七：时间序列"或改写发现四的措辞）。
**不要**自己改动 `paper/` 下的任何 `.tex`。
