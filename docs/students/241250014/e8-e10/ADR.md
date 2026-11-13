# 决策记录：E8—E10 A 轨道的失效键、历史图来源与证据边界

## 背景与约束

A 轨道要在真实 BuildChecker 执行上建立对象依赖历史图，并在后续提交中判断“复用还是刷新”。课程 profile 只覆盖显式 C/Make 规则、两个对象目标（main.o/helper.o）与三种编译配置（`-O0`、`-O1`、`-O0 -DMODE=1`）；实验要在 A 组服务器 `60.204.240.40`（2 vCPU、1775 MiB）上以固定镜像离线运行，证据必须能回溯到原始 trace 与 Make 数据库。课程同时要求个人提交只改本人范围、样例内部提交不能替代外层学生源码 SHA。

## 决策

1. **缓存失效键**取四个维度：所有本地 `.c/.h` 文件中的预处理指令行、Makefile 中所有 TAB 配方行、`CFLAGS` 值、`gcc --version` 首行。任一维度不同即视为历史图失效。
2. **历史图来源**：E8 基线使用真实 BuildChecker 的 `actual-graph.json` 投影到对象目标（`baseline_source` 明确记录），并用 `gcc -MM` 的独立投影做断言；E10 结束时再用 BuildChecker 交叉核对最终项目。
3. **刷新粒度**：失效时**保守刷新全部对象目标**，不做“仅刷新受影响目标”的局部优化。
4. **失败与证据边界**：所有容器阶段 `--network none`、挂载仓库到 `/course`、`--cap-add SYS_PTRACE`；每一步通过 `lab_python` 记录 `steps/*.log` 与 `STEP_EXIT_CODE`；`work/` 不进 Git，单独 tar.gz 归档；报告分别记录外层学生源码 SHA 与样例 project 内部提交。

## 替代方案及拒绝理由

- **以文件 mtime 或整文件哈希作为失效键**：实现简单，但普通函数体变化也会触发全量刷新，无法解释 E9 的 C1 复用，也会把“只改声明”误判为图失效；拒绝。
- **只用 `make -MD` 生成依赖**：更接近构建系统真实路径，但课程 profile 的 Makefile 未开启自动依赖生成，且会把“声明图”和“实际读取图”混在一起，无法计算 MD/RD 两个方向；拒绝，保留 GCC/BuildChecker 双路径。
- **只刷新受影响目标**：需要 include 关系图，并会改变课程原有用例 `test_include_added_invalidates_cache` 断言的“两个目标都刷新”语义；本轮不修改参考实现，改为在 ADR 中记录为扩展计划。
- **直接在宿主机运行**：宿主机缺 gcc/strace 一致性保证，且证据与镜像身份无法绑定；拒绝，统一在 `course-e8e10:241250014` 内执行。

## 代价与覆盖范围

- 保守刷新会在 include/配置变化时多读一次 `gcc -MM`（E10 中 include/flags/header 的 full/inc 比值≈1.0），收益是判定简单、不会漏刷新；代价是失去局部优化的性能空间。
- profile 不支持递归 Make、生成文件、模式规则和多目标 recipe；结论不外推到任意 GNU Make 工程。
- 本机计时包含扫描内的 Git 检查、解析与 `gcc -MM`，不含 clean build 耗时，因此只用于同一环境内增量/全量对照，不作为论文加速倍数。

## 验证命令与证据

```text
# 分步手册路线（E8/E9/E10），每步由 lab_python 记录 steps 日志
lab_new_run e8 A   # OUT=work/e8-A-manual.Wvp5K1
lab_new_run e9 A   # OUT=work/e9-A-manual.aTfZCz
lab_new_run e10 A  # OUT=work/e10-A-manual.Jt18jj

# 容器内定向测试（原包 7 项 + 本人 3 项）
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/course" -w /course course-e8e10:241250014 \
  python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v
```

- E8：`BASELINE_PASS`、`BUILDCHECKER_BASELINE_PASS`、`REUSE_PASS`；MISSING 证据 `trace/t.14:579`、`trace/t.15:23`，RD 证据 `make-db.txt:1044`。
- E9：`C1_REUSE_PASS`、`C2_REFRESH_PASS`、`C3_RESOLVED_PASS`，内部提交 `8bf9596→a8ed93f→63e8ce7→7738a1c`。
- E10：`results.csv` 30 行 `equal=True`、`gate.json passed=true`、`MATRIX_PASS`；最终 BuildChecker `status=SUCCEEDED`，仅剩 RD unused.h。
- 测试：`Ran 10 tests / OK / exit 0`（`work/unit-tests-20261113-133049.log`）。
