# AI 使用记录

工具/模型/日期：DeepSeek Harness 编码代理（deepseek-v4.1-flash）/ 2026-11-13。

## 输入上下文与问题

向模型提供课程 `DevOps_E8_E10_20261031` 材料、A 组仓库 `Viyangle/devops-2026-a`、AB 公用仓库 `Lee-bx-06/devops-2026` 的当前分支与 PR 状态，以及“本人是 A 组组长、只完成自己的一份、给组员留出任务”的边界，要求：先判断组长在 E8—E10 中要做的事，再按 A 轨道手册在本组服务器完成实验、证据、报告与提交。

## 模型建议与采用情况

- 采用：组长任务拆成“群组导入（公共准备第 6—7 步）+ 个人 E8/E9/E10 + 组员验收/交接”，并先导入、再开个人分支。
- 采用：课程实验包以独立提交 `ede3824` 原样导入（32 文件、1772 行），个人测试与报告另起提交 `4fdb612`，便于评审区分来源。
- 采用：按手册逐节执行（`lab_new_run` + `lab_python`），每一步保留 `steps/*.log` 与 `STEP_EXIT_CODE`，而不是只用一键演示入口。
- 采用：三个个人扩展场景（E8 间接 include、E9 间接新头文件、E10 配置身份变化）与 3 个独立预期测试，先写预期再运行。
- 采用：E10 性能只报本机扫描中位数与 full/inc 比值，≈1 的场景如实保留，不换算成论文加速倍数。
- 拒绝：不修改参考实现 `lab.py` 的刷新语义（否则会与课程原有用例冲突）；不把 `work/` 证据提交进 Git；不改动 `student/241250033`、`student/241250048` 的个人范围；不把模型生成的示例路径或运行 ID 当作真实证据。

## 人工修改与贡献边界

课程包中的 `labs/e8e10/`、`run_lab.py`、`.github/workflows/e8e10.yml` 为公共材料，原样导入。本人（组长 241250014）决定实验环境为 A 组服务器、镜像标签 `course-e8e10:241250014`、个人分支命名与提交边界，并在合并前核对证据文件。模型按手册组织命令与文档草稿；报告中的 SHA、镜像 ID、计时、findings 与日志路径均取自服务器实际输出，未使用占位值。

## 实际验证

- 服务器：`60.204.240.40`，Docker 29.1.3，镜像 `sha256:723c315584069c443d3e61709e06a37767185660601fa98d043a62d489d4f7de`；`run_lab.py build` 退出码 0。
- 单元测试：容器内 10 项（原包 7 + 本人 3）`OK`，退出码 0。
- E8/E9/E10 分步路线三步 `STEP_EXIT_CODE=0`（OUT：`work/e8-A-manual.Wvp5K1`、`work/e9-A-manual.aTfZCz`、`work/e10-A-manual.Jt18jj`）；E10 30 行 `equal=True`、`gate.json passed=true`。
- CI：[run 43372197175](https://github.com/Viyangle/devops-2026-a/actions/runs/43372197175) 在源码 SHA `4fdb612` 上 `success`，artifact `e8e10-evidence-43372197175`；合并前另有 PR 检查 `e7-a-quality-gate` 与 `e8e10-quality-gate`。
