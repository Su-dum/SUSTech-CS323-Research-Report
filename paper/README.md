# paper/ —— 论文源码目录

这里只放**与报告排版直接相关**的东西：LaTeX 源码、参考文献库、图（编译时被引用的那份）。

## 格式决策：单栏 `acmsmall` + `nonacm` + **XeLaTeX**

### 为什么是单栏

课程要求"ACM 期刊模板"。在 `acmart`（v2.21 / 2026-11-01）里，**期刊格式都是单栏**，
双栏选项全部是会议论文集或 TOG。官方格式表原文：

| 选项 | 含义 |
|---|---|
| `manuscript` | "A manuscript. **This is the default.**" |
| **`acmsmall`** | **"Small single-column format."** 用于 JACM、TOPLAS、TOCS、TACO、CSUR、TOMS、TOSEM 等**几乎全部 ACM 期刊汇刊** |
| `acmlarge` | "Large single-column format." 仅 DLT、DTRAP、HEALTH、IMWUT、JOCCH、TAP |
| `acmtog` | "Large **double-column** format." 仅 TOG |
| `sigconf` | "Proceedings format for most ACM **conferences**"（双栏） |
| `sigplan` | "Proceedings format for SIGPLAN **conferences**"（双栏） |

> 说明：`acm.org` 对本机是 Cloudflare 拦截（403），上表读自 CTAN 镜像上的 `acmart.dtx`。

**页数换算（经验值）**：18 页单栏 ≈ 11–12 页双栏。18 页上限在单栏下是宽松的。

### 为什么 `\acmJournal{TOPLAS}`（不是课程号）

**更正：先前判断"acmart 不校验期刊名"是错的。** `\acmJournal` 是 xkeyval 的
`\define@choicekey*+{ACM}{acmJournal}`，**只接受内部注册的代码**，写 `CS323` 会直接报
`Class acmart Error: Incorrect journal CS323`。

本文按主题选用 **`TOPLAS`**（ACM Transactions on Programming Languages and Systems）。
其它常用合法代码：`TACO` / `TOMS` / `CSUR` / `TOPC`。

### 为什么必须 XeLaTeX

正文含中文。**pdfLaTeX 不能排中文**，会报
`Unicode character 的 (U+7684) not set up for use with LaTeX`（错误位置指向 `\maketitle`，
因为标题是第一处中文）。

`main.tex` 已做三件事：

1. `\usepackage{iftex}`：若用 pdfLaTeX 编译会给出**明确的中文报错提示**，而不是一堆 Unicode 错误；
2. XeLaTeX 下加载 `xeCJK` + Fandol 字体（TeX Live 自带：`FandolSong`/`FandolHei`/`FandolKai`/`FandolFang`）；
3. LuaLaTeX 下走 `luatexja-fontspec` 分支。

**Overleaf 上必须改设置**：Menu → Settings → Compiler → **XeLaTeX**。

### 为什么加 `nonacm=true`

课程报告不投 ACM。不加会怎样：首页页脚出现虚构的
`2026. 0164-0925/2026/11-ART1 $15.00` 与 `https://doi.org/10.1145/nnnnnnn.nnnnnnn`。

`nonacm=true` 是 acmart 的官方开关（`\define@boolkey{...}{nonacm}`），专门用于非 ACM 出版场合。

> 注意：acmart 的 toppmatter **只有** `printccs` / `printacmref` / `printfolios` 三个键，
> **没有** `printcopyright`，所以不能靠 `\settopmatter` 关版权块。
>
> 也**不要**用 `\def\footnotetextcopyrightpermission#1{}` 这类重定义：acmart 是用
> `{…\par…}` 调用它的，非 `\long` 的 `\def` 会报
> `Paragraph ended before \footnotetextcopyrightpermission was complete`。

## 当前状态

骨架已**编译通过（6 页）**，正文散文尚未写——`sections/*.tex` 里是结构、表格、图与 TODO 注释。

```
main.tex                    acmsmall + nonacm + XeLaTeX 中文支持
references.bib              24 条（18 条已核对 + 6 条 MLIR 文档）
figures/                    5 张图 × (png + svg)
sections/01-intro.tex       图 1（成本模型）+ TODO 结构
sections/02-background.tex  表 1 维度对比（6 列，已填）
sections/03-mechanisms.tex  图 2（多级共存）+ 四机制 TODO
sections/04-evidence.tex    图 3、图 4 + 表 2（已填）+ TODO
sections/05-contract.tex    表 3（StableHLO 契约设施，已填）+ TODO
sections/06-limitations.tex 表 4（七条局限，已填）+ TODO
sections/07-conclusion.tex  仅 TODO 结构
```

## 本地编译（本机已可用）

本机**没有** TeX Live / MiKTeX，但已装 **Tectonic**（XeTeX 引擎，单个 exe，按需从 CTAN 取宏包）：

```powershell
$tec = "$env:TEMP\tectonic-msvc\tectonic.exe"
$env:TECTONIC_CACHE_DIR = "$env:TEMP\tectonic-cache"
Set-Location paper
& $tec main.tex
```

产物 `main.pdf`。要保留日志加 `--keep-logs`。

读页数 / 渲染页面目检：

```powershell
python -c "import pymupdf; d=pymupdf.open('paper/main.pdf'); print(d.page_count); d[0].get_pixmap(dpi=110).save('paper/_preview/p1.png')"
```

## 两个已知的环境差异

1. **acmart 版本不同**：Tectonic 的 bundle 是 **v1.83（2022-02-19）**，Overleaf 很可能是 **v2.x**。
   本文只用到两版共有的特性（`acmsmall`、`nonacm`、`\acmJournal` 合法代码、`\ccsdesc`、`\Description`），
   但最终仍以 Overleaf 的编译结果为准。
2. **中文字体**：Tectonic 用 bundle 里的 Fandol；Overleaf 的 TeX Live 也自带 Fandol。
   若 Overleaf 报 font not found，改用 `\setCJKmainfont{FandolSong-Regular}`（去掉 `.otf`），
   或换成 `\usepackage[fontset=fandol]{ctex}`。

## 两条约定

1. **图只从 `figures/` 引用**（冻结快照），不从 `../out/` 引用——`out/` 会被脚本重跑覆盖。
2. **中间产物不进版本控制**：`paper/*.aux|log|blg|bbl|out|fls|synctex.gz`、`paper/main.pdf`、
   `paper/_preview/` 均已在根 `.gitignore` 排除。

## 编译顺序

```
xelatex main
bibtex  main
xelatex main
xelatex main
```

Tectonic 会自动跑 bibtex；目前还没有 `\cite`，所以 bibtex 报
"I found no \citation files" 属正常，散文写完后自动消失。
