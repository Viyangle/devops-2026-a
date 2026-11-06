# A 组 CI 的服务器入口

实验主机为 `60.204.240.40`。GitHub Actions 在根目录生成 `git bundle --all`，通过标准输入交给 SSH 调度器。服务端校验 `refs/source/heads/e7-ci` 与触发 SHA，检出该提交，保留其余 refs 供历史扫描。

服务器部署：

- 账号 `e7ci`，home `/var/lib/e7-a-ci`，加入 Docker 组。
- home、`.ssh/` 和 `authorized_keys` 属于 root，home 模式 755，公钥文件 644。
- `runs/` 属于 `e7ci`，模式 750；`.docker/` 属于 `e7ci`，模式 700，供 Docker/Buildx 写入配置。
- 将 `e7-ci-dispatch.py` 安装为 root 拥有、模式 755 的 `/usr/local/libexec/e7-ci-dispatch`。
- 仓库专用公钥的 authorized_keys 前缀为 `restrict,command="/usr/local/libexec/e7-ci-dispatch"`。
- 专用私钥存入仓库 Actions secret `E7_A_SERVER_SSH_KEY`；已核对的主机公钥记录存入 `E7_A_SERVER_KNOWN_HOSTS`。

入口接受 `run RUN_ID-ATTEMPT SHA true|false` 与 `fetch RUN_ID-ATTEMPT SHA`。运行目录为 `runs/RUN_ID-ATTEMPT/SHA/repository`，重试使用新的 attempt，不覆盖旧证据。25 分钟预算覆盖等待锁及执行；失败时按本次 cid 文件清理容器，写入退出码后才允许下载证据。

只允许本仓库分支运行。`e7ci` 的 Docker 权限可控制宿主 Docker，仓库写权限成员因此属于服务器代码执行的信任范围。
