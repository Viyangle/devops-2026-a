# A 组仓库（BuildChecker 线）

本仓库是 A 组的公共仓库，从 E7 开始使用；后续实验按目录继续追加，不再按单个实验命名。

当前内容为 **E7 A 轨道验证**：本地八项门禁 + GitHub CI + main 分支保护与合并门禁。

## 目录

| 路径 | 内容 |
|---|---|
| `services/buildchecker/` | BuildChecker 实现（`fullcheck.py`、`cli.py`）与 17 项服务测试 |
| `tests/e7/` | 9 项独立判定测试（含新增的拒绝规则测试） |
| `scripts/` | `lab_cloud.py` 入口、`run_e7_a_gate.py` 门禁、`secret_scan.py`、`doctor.py` |
| `fixtures/md-rd/` | 教学用最小 MD/RD 输入工程 |
| `ci/` | main 分支保护配置与"拒绝合并"演示测试 |
| `docs/` | `E7实验报告.md`、`E7验收记录.csv` |
| `work/` | 运行证据（不进 Git，随实验包归档） |

## 常用命令

```bash
python3 scripts/lab_cloud.py doctor
python3 scripts/lab_cloud.py build --out work/build-01 --build-timeout 1200
python3 -m unittest discover -s tests/e7 -v
python3 scripts/lab_cloud.py gate --out work/e7-01
```

## CI

`.github/workflows/e7-quality-gate.yml`：main push、面向 main 的 PR 与手动触发均运行。GitHub 托管 runner 负责检出精确 SHA、传输完整 Git bundle 和上传 artifact；语法检查、判定测试、源码及历史扫描、镜像构建和八项门禁在 A 组服务器 `60.204.240.40` 执行。`work/ci/` 保存主机、环境、源码 SHA 与完整场景证据。main 保留必需检查 `e7-a-quality-gate`，通过 PR 合并。

## 个人实验提交

| 姓名 | 学号 | 内容 | 实验结果 |
|---|---|---|---|
| 谢浩天 | 241250033 | [E7 源码、报告、证据及完整实验包](submissions/241250033/e7/README.md) | 公共入口 9 / 17 / 8 项通过；[PR #3](https://github.com/Viyangle/devops-2026-a/pull/3) 已合入 main，见 [集成记录](submissions/241250033/e7/INTEGRATION.md) |
