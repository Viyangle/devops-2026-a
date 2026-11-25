# ADR 241250014 · E11–E12 接口契约与真实项目口径

2026-11-25 · 殷晓瑞 · A09 组长 · A 轨道

## 决策 1：E11–E12 采用 `e11e12-1` 任务 API，E2 的 `GET /v1/artifacts/{artifact_id}` 由文件接口取代

**背景**：E2 阶段 A09/B09 冻结过一版 pair09 契约：四个按 `job_type` 命名的创建端点，加上 `GET /v1/artifacts/{artifact_id}` 读取产物，并留下“E12 必须证明另一组能读取文件”的待验证项。E11–E12 课程手册给出的是一套新的单入口 API：`POST /v1/jobs`、`GET /v1/jobs/{job_id}`、`GET /v1/jobs/{job_id}/artifacts`、`GET /v1/jobs/{job_id}/files/{相对路径}`，产物用 `artifact://<job_id>/<path>` 加 SHA-256 引用。

**候选方案**：

1. 完全沿用 E2 的四个创建端点和 `GET /v1/artifacts/{artifact_id}`，在服务端按 `job_type` 分发。
2. 完全采用 E11–E12 课程手册的 `e11e12-1` API，把 E2 契约标记为历史版本，B09 按新接口对接。
3. 两套并存：新 API 为主，额外实现 `GET /v1/artifacts/{artifact_id}` 兼容层。

**采用方案 2**，理由：

- 课程 E11/E12 的操作手册、参考 `run_e11e12.py`、`server.py` 和验收命令都以 `e11e12-1` 为准；CI 的 `e11e12-integration` 也按这套接口验证。
- 方案 3 需要为 `artifact_id` 再维护一套寻址规则，而 E11–E12 的产物引用已经带 `job_id` 和相对路径，兼容层只增加歧义。
- E2 契约的价值是“产物必须有 URI + SHA-256、跨组必须能读取”，这两点在 `e11e12-1` 中保留：`artifact://job-xxx/incremental-check.json`、清单里的 `sha256`、下载响应头 `X-Content-SHA256`。

**后果**：

- B09 必须按 `e11e12-1` 实现/调整客户端，不能再按 `GET /v1/artifacts/{artifact_id}` 写死。
- 组级 `docs/E11-E12小组交接与验收.md` 和 `接口契约.md` 必须写明差异；B09 联调时以本文件和实际 HTTP 记录为准。
- 旧的 E2 契约文档保留，用于解释历史决策，不再作为 E12 的实现依据。

**兼容性与测试**：

- `labs/e11e12/test_contract.py` 覆盖 schema、commit、kind、artifact URI/hash。
- `test_server.py` 覆盖幂等、409、哈希、路径越界、重启、A→B 报告交接。
- `api_smoke.py` 实际验证 202/200/409/400、五阶段身份字段、下载头 SHA。

## 决策 2：真实项目采用外部 `antirez/sds`，并在组级文档写明口径

**背景**：课程要求“选择本组实际维护、具有真实修改记录的 C/Make 项目”。A09 的 EChecker/BuildChecker 是 Python 服务，E8–E10 的 `fixtures/md-rd` 是课程生成样例，不能算真实项目；组内没有自有的 C/Make 仓库。

**候选方案**：

1. 用课程 `fixtures/md-rd` 冒充真实项目。
2. 找 A09 成员实际维护过的 C/Make 仓库。
3. 采用外部开源项目 `antirez/sds`，记录来源、许可、base/target 完整 SHA 和适配代码。

**采用方案 3**：`antirez/sds` 有真实的 Makefile、真实的 `sds-test → sdsalloc.h` 缺失依赖、真实的上游修复提交 `9cbfaf5`，且原生测试可重复执行（46/46）。课程样例仍然单独保留为 `course-generated`，两者在 dataset 和报告里分开。

**后果与风险**：

- 课程原文的“本组实际维护”是更严格的口径；本组按“外部真实项目 + 明确来源/许可/提交”处理，并在组级文档写明理由，必要时向老师确认。
- `data/sds-input/dataset.json` 记录 `source_type=external-open-source`、`license=BSD-3-Clause`、三个完整 SHA；个人报告不把课程样例写成真实项目。
- `labs/e11e12/sds.py` 只做原生目标/编译参数适配，不改上游源码；DRAFT 的 Dockerfile 只写入分离检出的工作副本。

## 决策 3：组长新增测试放在 `pipeline.execute` 边界，而不是重复 API 单测

**背景**：241250033 的 25 项测试已经覆盖 `check_envelope`、API 幂等/哈希/重启/A→B 交接；再写一个同层测试价值不大。

**决策**：新增 `test_execute_rejects_report_for_another_target`，在 `pipeline.execute` 的 `e12-repair` 路径上构造“报告 commit 与请求 target 不一致”的场景，断言 `status=FAILED`、`error.code=STALE_REPORT`、`stages=[]`。它验证的是“提交后的执行边界”而不是单个函数，补足课程要求“报告中的 commit 必须与修复目标一致”的端到端约束。

**后果**：测试数从 25 增至 26；CI 与服务器均通过。
