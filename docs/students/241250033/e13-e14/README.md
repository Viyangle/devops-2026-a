# E13–E14 实验入口

谢浩天 · 241250033 · 鼓楼 A09 · A 轨道 · 2026-11-27

- [E13 交叉测试记录](交叉测试记录.md)
- [E14 候选发布说明](候选发布说明.md)
- [A09 库存补货判定项目](https://github.com/Viyangle/devops-2026-a/tree/62770bc46cf558cbbf5858bfc327ba04b7c8da42)
- [A09 实验 PR #15](https://github.com/Viyangle/devops-2026-a/pull/15)

## E13

在 Linux Docker 宿主机的仓库根目录运行。保留 E11–E12 的工具镜像。A09 交换项目放到 `data/a09/repo`，将构建候选、完整 base/target SHA 和预期输出填进 `data/a09/request-e12.json`。从 `/course` 起写容器内路径。教师的 jsmn、inih、tiny-AES-c 各有自己的请求和结果。

```bash
python3 run_e11e12.py test
python3 -m unittest discover -s labs/e13e14/tests -v
python3 run_e11e12.py serve --port 18433
```

在另一个终端跑自测。两个输出目录都要用新的名称。

```bash
python3 labs/e13e14/verify_exchange.py \
  --request data/a09/request-e12.json \
  --out work/e13-self-test-02 \
  --image course-e11e12:241250033 \
  --api-url http://127.0.0.1:18433 \
  --source-url https://github.com/Viyangle/devops-2026-a/tree/62770bc46cf558cbbf5858bfc327ba04b7c8da42
python3 labs/e13e14/scan_runtime_logs.py work/e13-self-test-02
```

正式交换时，仓库和两个 SHA 来自提供方。用 `--scope paired-exchange`、`--provider` 和 `--executor` 记录双方身份。B09 的交换包附 `request-b09.json`，其中 `fixed_report_sha256` 校验信封字节，`expected_source_report` 固定 A 原报告的 job、trace、URI、SHA 和字节数。

## E14

```bash
export E14_ROOT="$PWD" E14_IMAGE=course-e11e12:241250033
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250033 config --quiet
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250033 up -d --wait
python3 labs/e13e14/orchestrate.py \
  --request data/a09/request-e12.json \
  --out work/e14-a09-02
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250033 logs --no-color > work/e14-a09-02-services.log
python3 labs/e13e14/scan_runtime_logs.py work/e14-a09-02 work/e14-a09-02-services.log
docker compose -f labs/e13e14/compose.yaml -p e14-a09-241250033 down
```

四个健康检查端口默认是宿主机回环地址的 18081–18084。已归档的请求保留课程服务器当次镜像地址。复现时若直接访问上游镜像，删除请求的 `draft_image_override`。课程服务器经镜像缓存运行，可将该值更新为同一基础镜像的已核验平台摘要。
