# E7 A：谢浩天 241250033

个人实验已通过 [PR #3](https://github.com/Viyangle/devops-2026-a/pull/3) 合入本组 `main`。实际运行源码 `4e81e9c2713e220a25bcab294b58ad7a5673a899`，合并提交 `4f87c2452f3caaa51793f24a7e51a9da23d00ebe`。

公共入口在 A 组服务器 `60.204.240.40` 实测：**9 项独立判定测试、17 项服务测试、8 项门禁全部通过**。同一 PR 的故意失败阶段为 1 failed / 16 passed，普通合并退出 1、OPEN/BLOCKED；修复后恢复成功并合入 main。

- [个人报告](REPORT-241250033.md)
- [验收表](E7验收记录-241250033.csv)
- [个人贡献与提交记录](CONTRIBUTIONS.md)
- [新增测试接入记录](INTEGRATION.md)
- [根目录判定测试](../../../tests/e7/test_e7_a_gate.py)
- [根目录服务测试](../../../services/buildchecker/tests/test_fullcheck.py)
- [小组仓库 CI 与合并证据](evidence/group-integration-20261106/)
- [完整小组集成包](E7_A_241250033_Group_20261106.zip)

此前独立实验的源码、8 / 17 / 8 项结果和原始证据保留在 [source/](source/)、[历史证据](evidence/241250033-20261106/) 和 [原完整实验包](E7_A_241250033_20261106.zip)。两阶段完整包都包含 work、输入、trace、命令、stdout/stderr 和下载 artifact，哈希见 [publication.json](publication.json)。
