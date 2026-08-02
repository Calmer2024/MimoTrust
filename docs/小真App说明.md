# “小真核验”App 首版实现说明

## 已实现闭环

当前版本已把原同步核验包装为移动端异步任务：

```text
短视频分享文案 / 预留 Agent context
  → POST /v1/jobs（立即 202）
  → ARQ Worker / 本地进程内 Worker
  → 内容解析与结构化主张
  → 多源检索、证据筛选、报告生成
  → Redis Streams / 本地 EventBus
  → SSE → Room → Compose 与 Android 通知
  → 最终中性结论卡片
```

- 后端保留原 `/api/analyze`，新增 `/v1/jobs` 协议；
- `device_id + client_request_id` 是幂等键；
- 生产模式由 PostgreSQL 保存任务事实状态、Redis Streams 保存阶段事件、ARQ 执行任务；
- 完整分析 JSON（含关键帧 OCR/画面证据元数据）和报告在配置 MinIO/S3 后写入 `jobs/<job_id>/analysis.json`、`report.md`；原始媒体二进制仍待抽取 Worker 对接对象存储；
- 开发模式 `MIMO_JOB_MODE=memory` 不要求外部服务；
- Android 分享入口收到 `ACTION_SEND text/plain` 后用 WorkManager 投递并立即关闭；
- Room 保存本地任务摘要，OkHttp SSE 按 `Last-Event-ID` 恢复，旧 `sequence` 不会覆盖新状态；
- Compose UI 使用参考图的黑白、高圆角卡片、圆形动作按钮和纵向任务时间线；
- 一个 Job 固定使用 `jobId.hashCode()` 作为通知 ID，阶段更新不会堆出多条通知。

## API 示例

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H 'Content-Type: application/json' \
  -H 'X-Device-Id: demo-phone' \
  -d '{"source":{"type":"shared_url","value":"https://v.douyin.com/example","platform_hint":"douyin"},"mode":"auto","client_request_id":"demo-request-0001"}'
```

返回的 `event_url` 可直接用 `curl -N` 观察。前台 SSE 只展示阶段和耗时，不展示模型内部思维过程，也不会把流程百分比称作“可信度”。

## 运行模式

开发：

```powershell
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# 填写 MIMO_API_KEY；MIMO_JOB_MODE 保持 memory
uvicorn app.main:app --reload
```

生产式本地栈：

```powershell
docker compose up --build
```

Android 模拟器默认 API 是 `http://10.0.2.2:8000/`。真机应使用电脑局域网地址；正式环境必须改成 HTTPS，并移除明文网络许可。

## 小米能力接入点

`XiaomiFocusAdapter` 当前只探测厂商和 `notification_focus_protocol`，不会伪造或猜测 `miui.focus.param`。原因是超级岛/焦点通知模板和节点必须与小米审批的固定包名、Channel、场景方案一致。拿到审批材料后，仅在该适配器内加入已批准模板；普通通知始终保留。

MiPush 的服务端 AppId/AppKey、客户端 SDK 和 Receiver 也需要申请结果，因此当前 SSE 闭环可运行，但“App 进程被系统回收后仍更新通知”必须在获得 MiPush 凭据后补齐。Push payload 应直接复用 `JobEvent` 字段，并拒绝不大于 Room 当前 `sequence` 的乱序消息。

小米 Agent / 自有短视频平台能力统一接到 `XiaozhenAgentGateway`。普通 APK 不尝试跨 App 偷读当前视频，也不使用无障碍自动点击；未拿到系统当前场景上下文时，只使用分享入口。

## 外部待办

1. 固定正式 `applicationId`、签名和通知 Channel，提交小米焦点通知/超级岛场景申请；
2. 申请小米 Agent 生态“小真”测试资格，并书面确认当前场景上下文字段和授权流程；
3. 申请 MiPush 凭据并实现 Receiver → `JobRepository`/通知的序列化更新；
4. 接入自有短视频平台后，实现 `XiaozhenAgentGateway`，后端 `platform_api` source 已预留；
5. 正式环境增加 access token、设备密钥、限流、Alembic 迁移和 S3 生命周期策略。
