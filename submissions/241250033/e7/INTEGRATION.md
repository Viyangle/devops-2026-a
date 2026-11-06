# 谢浩天 241250033 的根目录测试合入记录

本次将个人提交中的三个测试函数加入仓库根目录现有运行入口，保留其他成员的测试。

- `tests/e7/test_e7_a_gate.py`：增加 `test_extra_finding_is_rejected`、`test_missing_evidence_is_rejected`，分别检查多出 `extra.h` finding 和删除 `evidence` 字段，并断言具体错误消息。
- `services/buildchecker/tests/test_fullcheck.py`：增加 `test_matching_dependencies_have_no_findings_and_preserve_graphs_and_job`，检查声明与读取一致时无 finding，且两张依赖图、证据 PID、父子进程与构建任务归属保持正确。

原始来源：独立实验运行提交 `d2cbe210b2a90c34ebd10c360846314321d17d04` 中的同名文件；集成基线为 GitHub 个人分支 `68097d9` 的 tarball。个人原始提交归档仍在本目录的 `source/`。

现有 `tests/e7/test_e7_gate_rejections.py` 使用 `original-2`、额外 `stdio.h`、空列表 `evidence=[]`；此次加入的个人测试使用 `original-1`、额外 `extra.h`、缺失 `evidence` 键，输入和错误断言不同，因此保留两组。

服务器实际通过：根目录判定测试由 7 项增至 **9 项**，服务测试由 16 项增至 **17 项**，八项真实门禁全部通过。

运行源码 `4e81e9c2713e220a25bcab294b58ad7a5673a899`；恢复 CI [42164137207](https://github.com/Viyangle/devops-2026-a/actions/runs/42164137207)。同一 PR #3 已实际拒绝错误版本断言并在修复后合入 main，合并提交 `4f87c2452f3caaa51793f24a7e51a9da23d00ebe`。

所有实验检查在 A 组服务器 `60.204.240.40` 执行。GitHub runner 负责传输和归档；新增 `scripts/run_e7_server_ci.sh` 与 `ci/server/e7-ci-dispatch.py` 保存精确 SHA、主机、退出码和完整原始证据。服务器入口、构建源和内存适配见根目录 `STATE.md`。

完整三阶段链接、原始证据复核与个人贡献见 [报告](REPORT-241250033.md) 和 [贡献记录](CONTRIBUTIONS.md)。
