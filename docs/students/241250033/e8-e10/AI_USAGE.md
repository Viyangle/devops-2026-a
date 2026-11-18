# AI 使用记录

工具/模型/日期：Antigravity AI 编程助手 / 2026-11-16

## 输入上下文与问题

向模型提供课程材料包 `DevOps_E8_E10_20261031.zip`、小组交接文档 `docs/E8-E10小组交接与验收.md`、A 组仓库 `Viyangle/devops-2026-a` 当前 `main` 分支状态及 A 组服务器 `60.204.240.40` 环境信息，要求以谢浩天（学号 `241250033`，A 轨道）身份按手册分步完成 E8—E10 全部实验、自主扩展、个人单元测试、三份报告文档、PR/CI 验证以及服务器证据归档。

## 模型建议、采纳/拒绝及理由

- **采纳**：先核对远端 `main` 与 `docs/E8-E10小组交接与验收.md`，确认课程包已由组长 PR #5 导入，无需重复导入。
- **采纳**：按 `02_操作手册` 分步路线使用 `classroom_helpers.sh`（`lab_ready`、`lab_new_run`、`lab_python`）在服务器容器内逐步执行，确保保留每一步 `steps/*.log` 与 `STEP_EXIT_CODE=0`。
- **采纳**：在独立的 `ext-decl-and-indirect`、`ext-c4`、`ext-transitive-leaf` 副本上开展 E8/E9/E10 自主扩展实验，避免破坏原始手册样例目录中的内部 Git 历史。
- **采纳**：在 `labs/e8e10/test_profile.py` 末尾追加 `StudentE8A241250033`、`StudentE9A241250033`、`StudentE10A241250033` 三个独立测试类，先写出独立预期再在容器内运行验证。
- **拒绝**：拒绝直接修改 `labs/e8e10/lab.py` 的保守刷新语义，因小组交接边界明确要求组员不修改课程参考实现判定逻辑，且现有用例 `test_include_added_invalidates_cache` 依赖该语义；拒绝直接合并 PR 或改动组长维护的验收表。

## 人工修改与贡献边界

- 课程参考代码 `labs/e8e10/lab.py`、`run_lab.py`、`.github/workflows/e8e10.yml` 与组长原有 3 个测试类保持原样不变。
- 本人（`241250033`）负责在服务器规范目录 `/root/devops-students/241250033/buildchecker` 隔离运行并核对所有输出；AI 协助整理分步执行脚本、编写 `labs/e8e10/test_profile.py` 第 133—235 行的新增测试类及三份文档草稿。报告中的所有 commit SHA、镜像 ID、trace 行号、计时中位数与日志路径均直接采自服务器实际运行结果。

## 实际验证命令/输入/结果

- 镜像构建：`python3 run_lab.py build` → `work/environment-build-20261116-132151.log`，退出码 `0`，镜像 `course-e8e10:241250033`（`sha256:217dea8231525eb525b1ab2113ed7b7eac91acca538bd35bf1ac4f3b0d6587d1`）。
- 单元测试：`docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/course" -w /course course-e8e10:241250033 python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v` → `Ran 13 tests in 0.741s`、`OK`（`work/unit-tests-20261116-132527.log`）。
- 阶段实验：`work/e8-A-manual.wZd7J7`、`work/e9-A-manual.FphCcr`、`work/e10-A-manual.CMSUtz` 全部步骤 `STEP_EXIT_CODE=0`；E10 `matrix/results.csv` 30 行 `equal=True`，`matrix/gate.json` `passed=true`。
- 远程 CI：[PR #9](https://github.com/Viyangle/devops-2026-a/pull/9) 在源码 SHA `9cc3c8cd892c317e95230366c40ee482a5f66a33` 上触发的 `e8e10-quality-gate`（[43811016857](https://github.com/Viyangle/devops-2026-a/actions/runs/43811016857)）与 `e7-a-quality-gate`（[43811016884](https://github.com/Viyangle/devops-2026-a/actions/runs/43811016884)）均已 `success`。
