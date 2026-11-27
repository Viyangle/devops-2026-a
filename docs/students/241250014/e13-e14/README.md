# E13–E14 实验入口（组长）

殷晓瑞 · 241250014 · 鼓楼 · A09 · A 轨道 · 2026-11-27

- [E13 交叉测试记录](交叉测试记录.md)
- [E14 候选发布说明](候选发布说明.md)
- [AI 使用记录](AI_USAGE.md)
- 组级：[E13—E14 小组交接与验收](../../E13-E14小组交接与验收.md)

本目录是组长 241250014 的独立执行记录。它与 241250033 的
[`docs/students/241250033/e13-e14/`](../241250033/e13-e14/README.md) 是两条独立执行线：
输入 SHA 相同，执行者、镜像、证据目录不同，结果互不替代。

## 固定版本

| 项 | 值 |
| --- | --- |
| 集成代码 | `4843fec41915ce87ded8b2ae0f15c8870ac413c4`（PR #15 合并后的 `main`） |
| 教学镜像 | `course-e11e12:241250014` = `sha256:8820cd5a108e532a3a908e069f0a98e06f17e071234862b5a4d9cf9ed2513e03` |
| A09 项目 | base `0ef512bc6b3b4b4363045deb13033b2f7e28e692` → target `62770bc46cf558cbbf5858bfc327ba04b7c8da42` |
| B09 项目 | base `30ffe4c41492334478a2446a8be0662d3f31d478` → target `a7e3b644ca9b1b9d0b26bd41e839fcbf5ea1c293` |
| 教师项目 | H1 jsmn `66a6daf`→`948a1d3`；H2 inih `aafc740`→`3aadb81`；H3 tiny-AES-c `dc80993`→`5640bb6` |
| 服务器工作区 | `60.204.240.40:/root/devops-students/241250014/e13e14` |

## 输入

- 交换输入来自 `E13-A09-exchange-241250033-r2.tar.gz`（SHA-256 `e64a0617…`）与
  `E13-E14-A09-241250033-20261127-r2.tar.gz` 的 `course-server/data/` 快照；A09/B09 项目仓库、
  教师 `e13-upstream-student.zip` 的提交号均按上表核对。
- 本机没有 241250033 曾用的 `127.0.0.1:18128` 镜像仓，所有请求改用本机已缓存的
  `m.daocloud.io/docker.io/library/python@sha256:f82c9645…` 作为 DRAFT 基础镜像，
  通过 `draft_image_override` 固定，不改变候选内容哈希。

## 复现

```bash
cd /root/devops-students/241250014/e13e14
python3 run_e11e12.py test
python3 -m unittest discover -s labs/e13e14/tests -p 'test_*.py' -v

# E13：C1–C8，需要 API（C8 幂等/409）
python3 run_e11e12.py serve --port 18433 &
python3 labs/e13e14/verify_exchange.py \
  --request data/a09/request-241250014.json \
  --out work/e13-241250014-a09-01 \
  --image course-e11e12:241250014 \
  --api-url http://127.0.0.1:18433 \
  --scope paired-exchange --provider A09 --executor "A09 / 241250014" \
  --source-url https://github.com/Viyangle/devops-2026-a/tree/62770bc46cf558cbbf5858bfc327ba04b7c8da42

# E13：教师三个项目（用派生 runtime 候选，见交叉测试记录“适配范围”）
python3 run_e11e12.py run \
  --request data/e13-upstream-student/H1-jsmn/request-241250014.json \
  --out work/e13-241250014-H1-jsmn-02

# E14：四服务
export E14_ROOT="$PWD" E14_IMAGE=course-e11e12:241250014
export E14_BUILDCHECKER_PORT=18281 E14_ECHECKER_PORT=18282
export E14_DRAFT_PORT=18283 E14_MDFIXER_PORT=18284
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250014 up -d --wait
python3 labs/e13e14/orchestrate.py --request data/integration-sample/e12-241250014.json --out work/e14-241250014-sample-01
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250014 logs --no-color > work/e14-services-241250014.log
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250014 down
```

证据归档：`lab13-14/submissions/A09-E13-E14-20261127/`；服务器归档
`/root/devops-submissions/241250014/E13-E14-241250014-20261127.tar.gz`。

## 边界

- 代码合并、本地/服务器复跑都不等于 E13 门禁通过：B09 独立回执与教师隐藏测试仍未完成。
- `v0.9-rc` 未创建；E14 状态为“候选待发布”。
- 教师原始候选只装 `build-essential`，需要派生含 `git`、`strace` 的 runtime 候选，详见交叉测试记录。
