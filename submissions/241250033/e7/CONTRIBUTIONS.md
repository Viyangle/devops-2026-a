# 个人贡献

学生：谢浩天，学号 241250033，A09 组，E7 A。

## 参考实现来源

本项目基于用户提供的课程参考包 `DevOps_E7_Student_Cloud.zip`（整理日期 2026-11-05）。参考包中的 buildchecker 核心算法、容器运行方式、E7 gate 脚本及原有测试继续沿用。检测核心算法未改。

## E6 个人工作沿用

从本人 E6 提交 `8ba60482da7f2140026c40660b55c7b39b974c0c` 迁入 `services/buildchecker/tests/test_fullcheck.py` 中的 `test_matching_dependencies_have_no_findings_and_preserve_graphs_and_job`。该用例检查声明依赖与实际读取一致时 findings 为空，同时保留声明图、实际图、证据 PID 和进程 job 归属。参考包的其他测试保留。

E6 完整最终提交为 `Lee-bx-06/devops-2026` 的 `2f776cd13b62ea22d960046e5ccc4e83b7934e52`。

## E7 本次新增

- `scripts/doctor.py`：将本组最低内存改为 1.5 GiB，适配教师分配的 2 GiB 主机（系统实际报告约 1.7 GiB），保留真实资源报告和建议阈值。
- `tests/e7/test_e7_a_gate.py`：新增“多一条 finding 拒绝”和“缺失 evidence 拒绝”两个行为测试。E7 oracle 用例由 6 条增至 8 条，gate 实现未改。
- `STATE.md`：记录资源阈值适配原因和恢复条件。

## 协作与执行记录

Codex 协助编写代码、执行命令及整理材料。个人新增与参考实现按上文区分。

2026-11-06 的手动实验在 `60.204.240.40` 的 `/root/241250033/e7-a` 执行，CI 在同机 `/opt/actions-runner-e7-241250033` runner 工作区执行。oracle 8 项、最终服务 17 项、完整 gate 8 项通过；详见 [个人报告](REPORT-241250033.md)。

构建网络适配：移除未使用扩展语法的外部 Dockerfile frontend 指令；基础镜像使用服务器已有的 DaoCloud 地址，固定 SHA-256 不变。首次 Docker Hub 解析超时日志保留在 work/build-20261106-01。

E7 同时沿用 E6 已实际构建通过的云机 Dockerfile：DaoCloud 同 digest 基础镜像、清华 Debian/PyPI 源及原有锁文件哈希校验。原始 Debian 源构建停滞的第二次尝试保留在 work/build-20261106-02；最终重建使用独立的 -03 目录。

## E7 提交与验收记录

| 提交 | 个人工作 |
| --- | --- |
| 28be69a | 导入参考包并保留来源；迁入 E6 测试，新增 E7 两项判定测试，资源适配和 self-hosted CI |
| c73d5e5 | 固定同 digest 基础镜像地址，清除打包元数据 |
| 6014b17 | 外部 PR 在 checkout 前明确失败，保留必需检查的拒绝效果 |
| 60b5927 | 沿用 E6 已验证的云机 Debian/PyPI 镜像源；正常本地与 CI 通过 |
| 9b0896e | 故意错误测试，记录 CI failure 与实际拒绝合并 |
| d2cbe21 | 修正成功退出码预期，服务器与 CI 均为 17 项服务测试通过 |
| 939c205 | 同一 PR #1 的最终合并记录 |

独立实验仓库：[mcjiansheng/devops-e7-a-241250033](https://github.com/mcjiansheng/devops-e7-a-241250033)。三阶段运行和 PR 见报告第 4 节。完整原始 work 与下载 artifact 随个人提交包交付。

## 新 A 组仓库集成与个人归属

仓库：`Viyangle/devops-2026-a`；本人分支 `student/241250033/e7`；Git 作者为“谢浩天 241250033”，邮箱为本人 GitHub noreply 地址。

| 提交 | 本人工作 |
| --- | --- |
| 68097d9 | 个人源码、报告、证据和原完整实验包提交到指定组仓库 |
| 7608fca | 将三个个人测试接入根目录；CI 实验迁到 A 组服务器，保留组员测试 |
| 627cd8f | 补齐中断/失败的本次容器清理与证据终态记录，正常 CI 通过 |
| 0a99f93 | 故意改错版本预期并实测 main 拒绝普通合并 |
| 4e81e9c | 恢复版本预期，同一 PR 的最新 CI 通过 |
| 4f87c24 | PR #3 正常合入 main |

新增服务器调度脚本、工作流传输/归档、镜像源和最低内存配置均有源文件记录。BuildChecker 核心算法与门禁判定实现继续沿用课程代码，原组员 `test_e7_gate_rejections.py` 保持不变。Codex 协助实现、服务器执行、审查及材料整理。

公共入口实测为 oracle 9、服务 17、门禁 8 项全部通过。该计数包含组员已有的 1 项 oracle 测试；本人独立实验的原计数 8 / 17 / 8 保留在历史记录。完整运行和合并证据见报告新增的“小组仓库最终提交”一节。
