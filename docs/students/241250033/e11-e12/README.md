# E11–E12 实验入口

谢浩天 · 241250033 · 鼓楼 A09 · A 轨道

在 Linux Docker 宿主机的仓库根目录运行。镜像用当前仓库的数字学号配置命名。

```bash
git config --local user.name 241250033
python3 run_e11e12.py build
python3 run_e11e12.py test
python3 run_e11e12.py prepare
python3 run_e11e12.py run --request data/integration-sample/e11-a.json --out work/e11-a
python3 run_e11e12.py run --request data/integration-sample/e11-a-reuse.json --out work/e11-a-reuse
python3 run_e11e12.py run --request data/integration-sample/e11-b.json --out work/e11-b
python3 run_e11e12.py run --request data/integration-sample/e12.json --out work/e12
```

`prepare` 保留已有样例。重复实验时给 `--out` 换一个目录。默认基础镜像沿用本组 E8–E10 配置，GitHub Actions 通过 `--base-image` 选用同摘要的 Docker Hub 镜像。

## SDS 外部仓库

```bash
git clone https://github.com/antirez/sds.git data/sds
python3 run_e11e12.py prepare-sds
python3 run_e11e12.py run --request data/sds-input/e12.json --out work/sds-e12
python3 run_e11e12.py run --request data/sds-input/e11-a-upstream-fix.json --out work/sds-upstream-fix
```

`data/sds-input/dataset.json` 记录上游来源及三次提交。检测使用 SDS 自带的 `sds-test` 规则和实际编译选项。DRAFT 用的 Dockerfile 放进流水线的分离检出，源仓库和提交历史保持原样。

## A/B API

在服务端启动 `python3 run_e11e12.py serve`。服务在宿主机监听 `127.0.0.1:8080`。远端客户端通过 SSH 转发访问服务端端口。

```bash
ssh -N -L 18080:127.0.0.1:8080 用户@服务器
python3 labs/e11e12/api_smoke.py --url http://127.0.0.1:18080 \
  --request data/integration-sample/e12.json --out work/api-client
```

客户端使用与服务端同一份请求 JSON。所有路径指向服务端容器的 `/course/data`。同一主机直接验证时可省略 `--url`，默认访问 8080。客户端保存两次独立的 A、B 任务、完整 E12 任务、响应头及下载产物。

[接口契约](接口契约.md) · [ADR](ADR.md)
