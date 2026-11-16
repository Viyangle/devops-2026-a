# 决策记录：241250033 A 轨道（EChecker）缓存失效边界、双路径核对与提交规范

## 背景与约束

A 轨道需要在服务器 `60.204.240.40`（Ubuntu 24.04，2 vCPU / 1.7 GiB 内存）上以 `course-e8e10:241250033` 离线容器完成 E8—E10 实验。课程受限 profile 覆盖显式 C/Make 规则、两个对象目标（`main.o`、`helper.o`）及三种编译配置（`-O0`、`-O1`、`-O0 -DMODE=1`）；小组交接文档 `docs/E8-E10小组交接与验收.md` 规定组员不修改课程参考实现 `labs/e8e10/lab.py` 的判定逻辑，仅在 `labs/e8e10/test_profile.py` 追加个人独立测试，并严格在 `docs/students/241250033/e8-e10/` 维护个人报告。

## 选择与替代方案

1. **缓存何时失效与配置身份绑定**：
   - 采用参考实现 `scan()` 的四维 `key` 签名：所有本地 `.c/.h` 预处理指令行（`directives`）、Makefile TAB 配方行（`recipes`）、`CFLAGS` 编译选项（`flags`）与 `gcc --version` 首行（`compiler`）。
   - **替代方案及拒绝理由**：
     - 仅按源码文本整文件哈希判别：会导致普通函数体改动（如 E9 C1）误触发依赖图刷新，无法体现增量复用；拒绝。
     - 按受影响目标精细刷新并直接改动 `lab.py` 默认返回：会改变原有 `ProfileTests::test_include_added_invalidates_cache` 与组长测试对两目标保守刷新的断言语义，也违反组员不改参考实现逻辑的边界；因此保留参考实现保守刷新语义，把按目标精细刷新记录为后续扩展计划，并通过个人单测验证“声明变化复用”和“指令增删迁移失效”等边界。
2. **双路径基线与终态重检**：
   - E8 基线与 E10 终态通过 `buildchecker()` 调用真实 `strace` + Make 数据库解析生成 `actual-graph.json`，投影到 `main.o`/`helper.o` 并与 `gcc -MM` 发现三元组断言一致；其余中间提交由 `gcc -MM` 快速采集，确保声明变化（E8 扩展/E9 C3）只更新 `declared` 图而不误刷新 `actual` 图。
3. **证据与 Git 边界**：
   - 所有分步过程通过 `classroom_helpers.sh` 的 `lab_new_run` 与 `lab_python` 记录至 `work/e*-A-manual.*/steps/*.log`；扩展实验分别在独立的 `ext-decl-and-indirect`、`ext-c4`、`ext-transitive-leaf` 副本上运行，避免污染手册原始样例目录的内部 Git 历史；`work/` 不提交进 Git，按规范打包为 `.tar.gz` 归档。

## 代价与覆盖范围

- **代价**：四维 `key` 任一变化时保守刷新全部对象目标，在 `include`/`flags`/`header` 场景下增量与全量扫描耗时接近（实测比值 0.97–0.99），而 `unchanged`/`body`/`declaration` 场景可达 5.85–6.45 倍扫描加速。
- **覆盖范围**：仅适用于当前受限显式 Makefile 与项目内头文件包含关系；不支持递归 Make、隐式模式规则或动态生成的头文件。此外扫描计时包含 Git 提交读取与 `gcc -MM` 预处理，不包含完整 `make` 编译耗时。

## 验证命令与实际证据

```bash
# 1. 容器内构建与环境检查
python3 run_lab.py build   # work/environment-build-20261116-132151.log, exit=0

# 2. 离线容器单元测试（13 项：原包 7 项 + 组长 3 项 + 241250033 新增 3 项）
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/course" -w /course course-e8e10:241250033 \
  python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v
```

- E8：`work/e8-A-manual.wZd7J7`（`BASELINE_PASS`、`BUILDCHECKER_BASELINE_PASS`、`REUSE_PASS`、`E8_EXT_DECL_AND_INDIRECT_PASS`，`trace/t.14:579`、`t.15:23`、`make-db.txt:1044`）。
- E9：`work/e9-A-manual.FphCcr`（C0–C3 提交 `7320b90`→`87319a7`→`4db6a82`→`6e14f21` 与扩展 C4 `ce91e74` 全部通过）。
- E10：`work/e10-A-manual.CMSUtz`（`matrix/results.csv` 30 行 `equal=True`，`gate.json passed=true`，`final-buildchecker/findings.json` 仅剩 `REDUNDANT unused.h`，`E10_EXT_TRANSITIVE_PASS`）。
- 单元测试：`work/unit-tests-20261116-132527.log`（`Ran 13 tests in 0.741s`，`OK`，退出码 `0`）。
