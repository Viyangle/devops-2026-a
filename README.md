# A 组仓库（BuildChecker 线）

本仓库是 A 组的公共仓库，从 E7 开始使用；后续实验按目录继续追加，不再按单个实验命名。

当前内容为 **E7 A 轨道验证**、**E8—E10 增量检测与修复教学实验**、**E11—E12 轨道内集成/接口联调** 与 **E13—E14 交叉测试/候选发布**：本地门禁 + GitHub CI + main 分支保护与合并门禁。

## 目录

| 路径 | 内容 |
|---|---|
| `services/buildchecker/` | BuildChecker 实现（`fullcheck.py`、`cli.py`）与 17 项服务测试 |
| `tests/e7/` | 9 项独立判定测试（含新增的拒绝规则测试） |
| `labs/e8e10/` | E8—E10 教学实验（`lab.py`、`test_profile.py`、固定环境与 BuildChecker 参考实现） |
| `run_lab.py` | E8—E10 构建/运行入口，按学号生成 `course-e8e10:<学号>` 镜像 |
| `labs/e11e12/` | E11—E12 编排、DRAFT/EChecker/MDFixer 适配、异步任务 API 与契约测试 |
| `run_e11e12.py` | E11—E12 构建/运行/服务入口，按学号生成 `course-e11e12:<学号>` 镜像 |
| `labs/e13e14/` | E13—E14 报告交接、运行日志扫描、四服务 Compose/HTTP 编排与 C1–C8 采集脚本 |
| `scripts/` | `lab_cloud.py` 入口、`run_e7_a_gate.py` 门禁、`secret_scan.py`、`doctor.py` |
| `fixtures/md-rd/` | 教学用最小 MD/RD 输入工程 |
| `ci/` | main 分支保护配置与"拒绝合并"演示测试 |
| `docs/` | `E7实验报告.md`、`E7验收记录.csv`、`E8-E10小组交接与验收.md`、`E11-E12小组交接与验收.md`、`E13-E14小组交接与验收.md` |
| `docs/students/<学号>/e8-e10/` | 各人 E8—E10 个人报告、ADR、AI 使用记录 |
| `docs/students/<学号>/e11-e12/` | 各人 E11—E12 个人报告、ADR、接口契约、数据与联调记录 |
| `docs/students/<学号>/e13-e14/` | 各人 E13 交叉测试记录、E14 候选发布说明、AI 使用记录 |
| `work/` | 运行证据（不进 Git，随实验包归档） |

## 常用命令

```bash
python3 scripts/lab_cloud.py doctor
python3 scripts/lab_cloud.py build --out work/build-01 --build-timeout 1200
python3 -m unittest discover -s tests/e7 -v
python3 scripts/lab_cloud.py gate --out work/e7-01

# E8—E10
python3 run_lab.py build
python3 run_lab.py e8 --track A --out work/e8-A-01

# E11—E12（服务器上先按交接文档设置镜像源变量）
python3 run_e11e12.py build
python3 run_e11e12.py test
python3 run_e11e12.py prepare
python3 run_e11e12.py run --request data/integration-sample/e11-a.json --out work/e11-a-01
python3 run_e11e12.py serve --port 8081

# E13—E14（服务器上复用 E11—E12 镜像；教师候选需派生含 git/strace 的 runtime 候选）
python3 -m unittest discover -s labs/e13e14/tests -p 'test_*.py' -v
python3 labs/e13e14/verify_exchange.py --request data/a09/request-241250014.json \
  --out work/e13-241250014-a09-01 --image course-e11e12:241250014 \
  --api-url http://127.0.0.1:18433 --scope paired-exchange
E14_ROOT="$PWD" E14_IMAGE=course-e11e12:241250014 \
  E14_BUILDCHECKER_PORT=18281 E14_ECHECKER_PORT=18282 \
  E14_DRAFT_PORT=18283 E14_MDFIXER_PORT=18284 \
  docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250014 up -d --wait
python3 labs/e13e14/orchestrate.py --request data/integration-sample/e12.json --out work/e14-01
python3 labs/e13e14/scan_runtime_logs.py work/e13-241250014-a09-01 work/e14-01
```

## CI

`.github/workflows/e7-quality-gate.yml`：main push、面向 main 的 PR 与手动触发均运行。GitHub 托管 runner 负责检出精确 SHA、传输完整 Git bundle 和上传 artifact；语法检查、判定测试、源码及历史扫描、镜像构建和八项门禁在 A 组服务器 `60.204.240.40` 执行。`work/ci/` 保存主机、环境、源码 SHA 与完整场景证据。`e7-a-quality-gate` 是五项必需检查之一，通过 PR 合并。

`.github/workflows/e8e10.yml`：E8—E10 教学验证（检查名 `e8e10-quality-gate`），在 GitHub 托管 runner 上构建 `course-e8e10:ci`，运行 `test_profile.py`（原包 7 项）并对 A/B 两个轨道各跑 e8、e9、e10 三个阶段，上传 `work/` 证据 artifact。该检查已是 main 必需检查。

`.github/workflows/e11e12.yml`：E11—E12 集成验证（检查名 `e11e12-integration`），构建 `course-e11e12:ci`，运行 26 项契约测试、四种课堂 mode、STALE_REPORT 负例、外部 SDS 与真实 HTTP API，上传 `work/` artifact。该检查也是 main 必需检查。

`.github/workflows/e13e14.yml`：E13—E14 集成验证（检查名 `e13e14-contracts`、`e13e14-four-services`），在 GitHub 托管 runner 上构建 `course-e11e12:ci`，运行 E11—E12 契约与 E13 四组单测、Compose 配置、源码扫描，以及四容器五阶段 + 0.01s 超时 + 恢复重跑，上传 `work/` artifact。两项检查均为 main 必需检查。

main 必需检查共五项且均为 strict：`e7-a-quality-gate`、`e8e10-quality-gate`、`e11e12-integration`、`e13e14-contracts`、`e13e14-four-services`。

## E8—E10 增量检测与修复教学实验

- 课程实验包已由组长按公共准备第 6 步原样导入：`labs/e8e10/`、`run_lab.py`、`.github/workflows/e8e10.yml`（[PR #5](https://github.com/Viyangle/devops-2026-a/pull/5) 合入 main，合并提交 `9332340`）。
- 每人在 `student/<学号>/e8-e10` 分支完成 E8/E9/E10，A 轨道以真实 BuildChecker 历史图、C0—C3 逐提交和六类一致性矩阵为主线，并至少增加一个有独立预期的测试。
- 组内操作步骤、环境约定与验收表见 [E8—E10 小组交接与验收](docs/E8-E10小组交接与验收.md)。

| 姓名 | 学号 | 分支 | 状态 | PR |
|---|---|---|---|---|
| 殷晓瑞（组长） | 241250014 | `student/241250014/e8-e10` | 已合入 main，合并提交 `8813889` | [#6](https://github.com/Viyangle/devops-2026-a/pull/6) |
| 谢浩天 | 241250033 | `student/241250033/e8-e10` | 已合入 main，合并提交 `ae35ed5` | [#9](https://github.com/Viyangle/devops-2026-a/pull/9) |
| 朱鸣涛 | 241250048 | `student/241250048/e8-e10` | 待提交 | — |

## E11—E12 轨道内集成与接口联调

- 课程包经 [PR #12](https://github.com/Viyangle/devops-2026-a/pull/12) 合入 `main`（合并提交 `e7194ab`）：`labs/e11e12/`、`run_e11e12.py`、`.github/workflows/e11e12.yml`；`labs/e8e10/lab.py` 只增加可选参数，E8—E10 回归通过。
- E11-A：BuildChecker 真实 strace 图接入 EChecker 缓存，验证头文件变化刷新、函数体变化复用；E11-B：DRAFT 真实构建 + 固定 MD → 补丁 → 复验；E12：DRAFT→BuildChecker→EChecker→MDFixer→复验五阶段，MDFixer 消费本轮报告；API 提供异步任务、幂等键、`job_id`/`trace_id` 和带 SHA-256 的产物引用。
- 真实项目采用外部 `antirez/sds`（BSD-3-Clause），课程样例与真实项目分开记录；与 E2 pair09 旧契约的差异见 [接口契约](docs/students/241250014/e11-e12/接口契约.md) 第 5 节。
- 组内操作步骤、服务器环境、验收表见 [E11—E12 小组交接与验收](docs/E11-E12小组交接与验收.md)。

| 姓名 | 学号 | 分支 | 状态 | PR |
|---|---|---|---|---|
| 殷晓瑞（组长） | 241250014 | `student/241250014/e11-e12` | 已合入 main，合并提交 `c993f8b` | [#13](https://github.com/Viyangle/devops-2026-a/pull/13) |
| 谢浩天 | 241250033 | `student/241250033/e11-e12` | 已合入 main，合并提交 `e7194ab` | [#12](https://github.com/Viyangle/devops-2026-a/pull/12) |
| 朱鸣涛 | 241250048 | `student/241250048/e11-e12` | 待提交 | — |

## E13—E14 交叉测试与候选发布

- 实验包经 [PR #15](https://github.com/Viyangle/devops-2026-a/pull/15) 合入 `main`（合并提交 `4843fec`）：`labs/e13e14/`、`.github/workflows/e13e14.yml`；对 `labs/e11e12` 的改动均为可选参数或新增 profile。
- E13：C1–C8（正常任务、旧报告、传输哈希、超时、错误补丁回滚、假密钥、失败隔离、幂等）在 A09 自建项目与 B09 公开项目上各跑 8/8；教师发放的 jsmn、inih、tiny-AES-c 五阶段通过，各 182 产物。
- E14：四容器（BuildChecker/EChecker/DRAFT/MDFixer）经 HTTP 跑通五阶段，固定样例 164、A09 183、B09 193、恢复 164 产物；0.01s 构建时限进入 `TIMED_OUT`/`DRAFT_FAILED`。
- **门禁待签收**：配对组 B09 无 E11—E14 产物，正式回执见 [Issue #16](https://github.com/Viyangle/devops-2026-a/issues/16)；适配范围待组员补公开（[Issue #17](https://github.com/Viyangle/devops-2026-a/issues/17)）；教师隐藏测试未执行；`v0.9-rc` 未创建。
- 组内交接、验收表与遗留任务见 [E13—E14 小组交接与验收](docs/E13-E14小组交接与验收.md)；组长记录在 [docs/students/241250014/e13-e14](docs/students/241250014/e13-e14/README.md)。

| 姓名 | 学号 | 分支 | 状态 | PR |
|---|---|---|---|---|
| 殷晓瑞（组长） | 241250014 | `student/241250014/e13-e14` | 已合入 main，合并提交 `da7d3c7` | [#18](https://github.com/Viyangle/devops-2026-a/pull/18) |
| 谢浩天 | 241250033 | `student/241250033/e13-e14` | 已合入 main，合并提交 `4843fec` | [#15](https://github.com/Viyangle/devops-2026-a/pull/15) |
| 朱鸣涛 | 241250048 | — | 未参与 E11—E14 | — |

## 个人实验提交

| 姓名 | 学号 | 内容 | 实验结果 |
|---|---|---|---|
| 谢浩天 | 241250033 | [E7 源码、报告、证据及完整实验包](submissions/241250033/e7/README.md) | 公共入口 9 / 17 / 8 项通过；[PR #3](https://github.com/Viyangle/devops-2026-a/pull/3) 已合入 main，见 [集成记录](submissions/241250033/e7/INTEGRATION.md) |
| 殷晓瑞 | 241250014 | [E8—E10 报告、ADR、AI 记录](docs/students/241250014/e8-e10/个人报告.md) | 10 项测试通过、E10 30 行一致性通过；[PR #6](https://github.com/Viyangle/devops-2026-a/pull/6) 已合入 main |
| 殷晓瑞 | 241250014 | [E11—E12 报告、ADR、契约、联调记录](docs/students/241250014/e11-e12/个人报告.md) | 26 项契约 + 13 项回归；E11-A 刷新/复用、E12 五阶段、API、SDS；[PR #13](https://github.com/Viyangle/devops-2026-a/pull/13) 已合入 `c993f8b` |
| 谢浩天 | 241250033 | [E11—E12 报告、ADR、接口契约](docs/students/241250033/e11-e12/个人报告.md) | 25 项契约；E11-A/B、E12、API、SDS；[PR #12](https://github.com/Viyangle/devops-2026-a/pull/12) 已合入 `e7194ab` |
| 殷晓瑞 | 241250014 | [E13 交叉测试、E14 候选发布说明](docs/students/241250014/e13-e14/README.md) | A09/B09 各 C1–C8 8/8；教师 H1–H3 各 182 产物；四服务 164/183/193/164；[PR #18](https://github.com/Viyangle/devops-2026-a/pull/18) 已合入 `da7d3c7` |
| 谢浩天 | 241250033 | [E13 交叉测试、E14 候选发布说明](docs/students/241250033/e13-e14/README.md) | A09/B09 各 C1–C8 8/8；教师 546 产物；四服务 795 产物；[PR #15](https://github.com/Viyangle/devops-2026-a/pull/15) 已合入 `4843fec` |
