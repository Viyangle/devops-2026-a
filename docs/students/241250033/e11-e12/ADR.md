# ADR 241250033 · E11–E12 接口和执行镜像

2026-11-25 · 谢浩天 · A09

## EChecker 报告交接

共享编排器支持单个 E12 任务，也支持 A 先完成检测、B 再独立修复。交接使用 `artifact://<job_id>/incremental-check.json` 和 SHA256。任务库用 A 的产物清单核对引用，MDFixer 用报告字节重新算摘要，并核对 `kind` 和目标提交。B 的产物保留原引用，便于从补丁追到源报告。固定报告继续只从 E11-B 入口消费。

## DRAFT 镜像

课程参考构建在 DRAFT 环节运行候选镜像。本次候选安装 GCC、Make、Git 和 strace。DRAFT 测试通过后，编排器按镜像 ID 启动后续检测与复验容器，挂载只读组件代码和本次产物目录。程序运行和检测使用同一工具链。`image-execution.json` 记录实际启动命令和镜像 ID。

## 外部项目

SDS 的原生 Makefile 直接从 `sds.c` 生成 `sds-test`。复用 E8–E10 的扫描、计划、补丁和验证逻辑，额外传入原生目标、编译参数和 `sdsalloc.h`。修复验收要求两次原生测试均通过，并验证仅触碰头文件即可重新生成二进制。新 Dockerfile 只写入工作副本。
