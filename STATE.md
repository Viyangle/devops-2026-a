# A 组服务器 CI

本组分配主机为 `60.204.240.40`，2 CPU、2 GiB 标称内存，系统可见约 1.7 GiB。`doctor.py` 最低内存沿用 E5/E6 的 1.5 GiB；CPU、磁盘下限及资源实测保留。主机升级达到 4 GiB 后，恢复模板最低内存 4 GiB。

GitHub 托管 runner 负责检出、传输和归档；语法检查、独立 oracle、源码及历史扫描、Docker 构建、镜像扫描和八项门禁均由 `scripts/run_e7_server_ci.sh` 在本组服务器执行。`work/ci/host.json`、`commit.txt` 和 `env.json` 记录运行主机、精确源码 SHA 和资源。

仓库协作者不能注册新的 self-hosted runner，因此使用独立的 SSH 调度账号 `e7ci` 和仓库专用 Actions secret。服务器入口仅接受运行与取回证据两种命令，代码通过完整 Git bundle 传入，保留历史扫描。并发运行由工作流 concurrency 和服务器文件锁串行处理。部署入口见 `ci/server/e7-ci-dispatch.py`。

Dockerfile 沿用 E6 实测的 DaoCloud 同 digest 基础镜像及清华 Debian/PyPI 源，依赖哈希校验保留。
