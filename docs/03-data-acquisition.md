# 语料获取（三条路，按成功率排序）

目标：在本机拿到 `llvm-project` 的 `mlir/` 目录。只需要 `mlir/test/`，不需要编译任何东西。

---

## 路线 1：稀疏克隆（推荐，最小体积）

```powershell
cd D:\
git clone --depth 1 --filter=blob:none --sparse https://github.com/llvm/llvm-project.git
cd llvm-project
git sparse-checkout set mlir
```

- 只检出 `mlir/`，体积远小于全仓库；`--depth 1` 避免历史。
- 如果 `--filter=blob:none` 报错（老版本 git），退化为：
  ```powershell
  git clone --depth 1 https://github.com/llvm/llvm-project.git
  ```
  体积大很多，但一定能用。
- 预计耗时取决于网速，国内可能十几分钟。**如果卡在 `Receiving objects` 长时间无进展，直接走路线 2。**

## 路线 2：下载官方源码包

从 LLVM 的 GitHub Releases 取某个正式版本的源码包（不是 Windows 安装包）：

```
https://github.com/llvm/llvm-project/releases
→ 选 llvmorg-21.1.0 (或任一近期版本) → Source code (tar.gz)
```

解压后只需 `llvm-project-<ver>/mlir/` 这一层，其余可删。好处是版本固定、引用时可写明 commit/tag（比 `main` 更适合写进报告）。

## 路线 3：镜像

GitHub 直连困难时：
- Gitee 镜像：`https://gitee.com/mirrors/llvm-project`
- 或任一可访问的 GitHub 代理前缀 + 上面的仓库地址

> 注意：镜像可能滞后于上游，报告里要写明"数据取自 \<tag\>，获取日期 \<date\>"。

---

## 校验（拿到后立刻做，30 秒）

```powershell
# 1) test 下应有大量 .mlir 文件（数量级 10^3 以上）
(Get-ChildItem D:\llvm-project\mlir\test -Recurse -Filter *.mlir).Count

# 2) 确认 Conversion 目录结构存在（脚本依赖它解析层间边）
Get-ChildItem D:\llvm-project\mlir\test\Conversion -Directory | Select-Object -First 15 Name

# 3) 确认 Dialect 目录结构存在
Get-ChildItem D:\llvm-project\mlir\test\Dialect -Directory | Select-Object -First 15 Name
```

任一步失败 → 说明路径指错（`--mlir-root` 应指向 `mlir` 这一级，不是 `llvm-project`）。

---

## 记录下来（写进报告 §4 的方法段）

- 仓库 URL 与 **commit / tag**：`git -C D:\llvm-project rev-parse HEAD`
- 获取日期
- `.mlir` 文件总数（脚本的 `meta.json` 里也会打印）

这三项缺一项，数据就不可复现，评阅人有理由质疑。
