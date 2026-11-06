# 谢浩天 241250033 的根目录测试合入记录

本次将个人提交中的三个测试函数加入仓库根目录现有运行入口，保留其他成员的测试。

- `tests/e7/test_e7_a_gate.py`：增加 `test_extra_finding_is_rejected`、`test_missing_evidence_is_rejected`，分别检查多出 `extra.h` finding 和删除 `evidence` 字段，并断言具体错误消息。
- `services/buildchecker/tests/test_fullcheck.py`：增加 `test_matching_dependencies_have_no_findings_and_preserve_graphs_and_job`，检查声明与读取一致时无 finding，且两张依赖图、证据 PID、父子进程与构建任务归属保持正确。

原始来源：本工作目录 `e7-a-241250033-20261106/repository` 中的同名文件；集成基线为 GitHub 个人分支 `68097d9` 的 tarball。个人原始提交归档仍在本目录的 `source/`。

现有 `tests/e7/test_e7_gate_rejections.py` 使用 `original-2`、额外 `stdio.h`、空列表 `evidence=[]`；此次加入的个人测试使用 `original-1`、额外 `extra.h`、缺失 `evidence` 键，输入和错误断言不同，因此保留两组。

静态计数预期：根目录判定测试由 7 项增至 9 项，服务测试由 16 项增至 17 项；合计由 23 项增至 26 项。实验与测试执行交由服务器，本机仅检查 Python AST 和来源函数一致性；此记录不包含服务器通过结果。
