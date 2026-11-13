# A 组仓库（BuildChecker 线）

本仓库是 A 组的公共仓库，从 E7 开始使用；后续实验按目录继续追加，不再按单个实验命名。

当前内容为 **E7 A 轨道验证** 与 **E8—E10 增量检测与修复教学实验**：本地门禁 + GitHub CI + main 分支保护与合并门禁。

## 目录

| 路径 | 内容 |
|---|---|
| `services/buildchecker/` | BuildChecker 实现（`fullcheck.py`、`cli.py`）与 17 项服务测试 |
| `tests/e7/` | 9 项独立判定测试（含新增的拒绝规则测试） |
| `labs/e8e10/` | E8—E10 教学实验（`lab.py`、`test_profile.py`、固定环境与 BuildChecker 参考实现） |
| `run_lab.py` | E8—E10 构建/运行入口，按学号生成 `course-e8e10:<学号>` 镜像 |
| `scripts/` | `lab_cloud.py` 入口、`run_e7_a_gate.py` 门禁、`secret_scan.py`、`doctor.py` |
| `fixtures/md-rd/` | 教学用最小 MD/RD 输入工程 |
| `ci/` | main 分支保护配置与"拒绝合并"演示测试 |
| `docs/` | `E7实验报告.md`、`E7验收记录.csv`、`E8-E10小组交接与验收.md` |
| `docs/students/<学号>/e8-e10/` | 各人 E8—E10 个人报告、ADR、AI 使用记录 |
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
```

## CI

`.github/workflows/e7-quality-gate.yml`：main push、面向 main 的 PR 与手动触发均运行。GitHub 托管 runner 负责检出精确 SHA、传输完整 Git bundle 和上传 artifact；语法检查、判定测试、源码及历史扫描、镜像构建和八项门禁在 A 组服务器 `60.204.240.40` 执行。`work/ci/` 保存主机、环境、源码 SHA 与完整场景证据。main 保留必需检查 `e7-a-quality-gate`，通过 PR 合并。

`.github/workflows/e8e10.yml`：E8—E10 教学验证（检查名 `e8e10-quality-gate`），在 GitHub 托管 runner 上构建 `course-e8e10:ci`，运行 `test_profile.py`（原包 7 项）并对 A/B 两个轨道各跑 e8、e9、e10 三个阶段，上传 `work/` 证据 artifact。该检查是 PR 合入前的第二道门禁，不影响原有必需检查。

## E8—E10 增量检测与修复教学实验

- 课程实验包已由组长按公共准备第 6 步原样导入：`labs/e8e10/`、`run_lab.py`、`.github/workflows/e8e10.yml`（[PR #5](https://github.com/Viyangle/devops-2026-a/pull/5) 合入 main，合并提交 `9332340`）。
- 每人在 `student/<学号>/e8-e10` 分支完成 E8/E9/E10，A 轨道以真实 BuildChecker 历史图、C0—C3 逐提交和六类一致性矩阵为主线，并至少增加一个有独立预期的测试。
- 组内操作步骤、环境约定与验收表见 [E8—E10 小组交接与验收](docs/E8-E10小组交接与验收.md)。

| 姓名 | 学号 | 分支 | 状态 | PR |
|---|---|---|---|---|
| 殷晓瑞（组长） | 241250014 | `student/241250014/e8-e10` | 已合入 main，合并提交 `8813889` | [#6](https://github.com/Viyangle/devops-2026-a/pull/6) |
| 谢浩天 | 241250033 | `student/241250033/e8-e10` | 待提交 | — |
| 朱鸣涛 | 241250048 | `student/241250048/e8-e10` | 待提交 | — |

## 个人实验提交

| 姓名 | 学号 | 内容 | 实验结果 |
|---|---|---|---|
| 谢浩天 | 241250033 | [E7 源码、报告、证据及完整实验包](submissions/241250033/e7/README.md) | 公共入口 9 / 17 / 8 项通过；[PR #3](https://github.com/Viyangle/devops-2026-a/pull/3) 已合入 main，见 [集成记录](submissions/241250033/e7/INTEGRATION.md) |
| 殷晓瑞 | 241250014 | [E8—E10 报告、ADR、AI 记录](docs/students/241250014/e8-e10/个人报告.md) | 10 项测试通过、E10 30 行一致性通过；[PR #6](https://github.com/Viyangle/devops-2026-a/pull/6) 已合入 main |
