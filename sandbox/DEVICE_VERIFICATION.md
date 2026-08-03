# Android 发送端真机验收

> 日期：2026-08-02

## 环境

- 设备：Xiaomi `25057RA09C`；
- Android：16 / API 36；
- 设备序列号：`6d38325e`；
- 网关：`http://127.0.0.1:8787`，通过 `adb reverse tcp:8787 tcp:8787` 访问；
- 网关活动内容：3 条视频；
- 正式守护者包 `com.mimotrust.guardian`：未安装。

## 构建

- APK：`mimotrust_controlled_content/build/app/outputs/flutter-apk/app-debug.apk`；
- 大小：`188045219` bytes；
- SHA-256：`d975e6e4d9bfeb37d315d5f8aca71d755a242259e5dc51327e4749e4452e9a44`；
- Dart 静态分析：无问题；
- Flutter 测试：`25/25` 通过；
- 网关测试：`10/10` 通过；
- 合同校验：5 个合法 Context、5 个非法 Context、3 个活动 Manifest 均符合预期；
- Android Debug 构建和真机覆盖安装：通过。

## 触发结果

清空 Logcat 并重启 App 后，普通播放未产生发送日志。随后进行以下操作：

| 操作 | 累计发送数 |
|---|---:|
| 打开评论面板 | 1 |
| 打开转发面板 | 2 |
| 完成模拟转发 | 2 |
| 点赞 | 2 |

两条发送日志的 `event_id` 不同，格式为：

```text
MiMoTrustSandbox: CONTENT_CONTEXT_SEND event_id=... type=video trigger=comment
MiMoTrustSandbox: CONTENT_CONTEXT_SEND event_id=... type=video trigger=share
```

日志未出现 `grant_code`、完整 Payload、评论正文、联系人或 Cookie。守护者缺失时 App
保持前台运行，评论和转发面板可正常使用。

## 三视频与数量结果

- 竖向滑动依次进入 `video-001`、`video-002` 和 `video-003`，三条 OSS 视频均播放；
- `video-001` 显示预置数量，并正确叠加此前持久化的点赞和本地评论；
- `video-002` 显示 `936 / 42 / 118`；
- `video-003` 初始显示 `2456 / 173 / 367`；
- `video-003` 点赞后变为 `2457`，不发送 Context；
- 完成一次模拟转发后转发数变为 `368`，发送总数仍为 2；
- 打开 `video-003` 评论面板时标题显示 `评论 173`；
- 三条视频切换过程中未产生 Context。

截图：

- `mimotrust_controlled_content/build/device-platform-bridge-comment.png`；
- `mimotrust_controlled_content/build/device-platform-bridge-share.png`。
- `mimotrust_controlled_content/build/device-three-video-001.png`；
- `mimotrust_controlled_content/build/device-three-video-002.png`；
- `mimotrust_controlled_content/build/device-three-video-003.png`；
- `mimotrust_controlled_content/build/device-video003-comment.png`；
- `mimotrust_controlled_content/build/device-video003-shared.png`。

## 尚未完成

由于 `com.mimotrust.guardian` 尚未安装，本轮只能证明沙盒发送端执行了固定目标包的
显式广播，不能证明 Receiver 已收到、校验或入队。完整跨 App 验收必须等待正式守护者
Receiver 安装后进行，不得改投 `com.mimotrust.xiaozhen`。

## 云端网关回归（2026-08-02）

- 阿里云 ECS 网关：`http://47.94.58.72`；
- 部署形态：Nginx `:80` -> Python `127.0.0.1:8787`，systemd 常驻；
- 公网验证：健康检查、grant 签发、一次兑换、视频下载、SHA-256 和重放拒绝通过；
- 构建配置：`config/cloud-debug.json`；
- APK 大小：`188045219` bytes；
- APK SHA-256：`8fc845ef522546133106e6a5dd28e6220eb49761582f68d7fa95554345add5c0`；
- Android 安装器和桌面启动器显示名称：`sandbox`；
- Dart 静态分析：无问题；Flutter 测试：`25/25`；网关测试：`10/10`；
- Xiaomi `25057RA09C` 覆盖安装成功，三视频首屏播放正常；
- `adb reverse --list` 为空，App 不依赖本地端口转发；
- 打开评论面板后记录到一条 `trigger=comment` 的 `CONTENT_CONTEXT_SEND`。

以上记录属于旧 Context 2.1 APK 的历史验收。公网入口目前是 Debug 明文 HTTP，正式演示前
必须迁移到 HTTPS 域名。

## Context 2.2 构建状态（2026-08-02）

- Schema、样例、Dart 模型、Kotlin 前台动态 Receiver 和五类当前状态快照已迁移到 2.2；
- `comment/share` 使用 `deferred_grant`，不访问网关；
- `guardian_request` 使用 Guardian 的 `request_id`，收到请求后才申请新鲜 grant；
- Dart 静态分析：无问题；Flutter 测试：`38/38`；
- 合同校验：6 个合法 Context、7 个非法 Context、3 个内置活动 Manifest；
- 云端 Debug APK 构建通过，大小 `220011733` bytes；
- APK SHA-256：`32fcbbe4db201fede4b3d917e0568d778be151659c0392157e1a1a596eccf85b`；
- 当前 ADB 未连接设备，尚未取得候选接收、主动请求、grant 响应和后端兑换的真机日志。

## 小真集成构建与云端接口闭环（2026-08-03）

- 以 `sandbox` 分支为沙盒基线，已合入 `main` 的小真 Android App 与后端；
- 小真严格接收 Context 2.2，五类内容均在合同、Android 和后端模型中支持；
- Receiver 只校验、关联 `request_id` 并调度唯一 WorkManager，不再兑换 grant 或解析 Manifest；
- 新增 `POST /v1/content-contexts`，由后端兑换 grant、校验 Manifest 并创建任务；
- 云端 `/health` 正常，Feed 实测为 7 条：4 视频、文章、图文、图集各 1；音频待素材；
- 使用云端 `article-001/v1` 的真实 grant 完成一次后端闭环，任务最终为 `completed`；
- 后端测试 `131/131`、Flutter 测试 `38/38`、Android 单元测试与 Debug 构建通过；
- 小真 Debug APK SHA-256：`bd67060484e1a823b5f9adea20683e8fd1c3656f79b0861d3be910eab6fee8ff`；
- Sandbox Debug APK SHA-256：`49038759d2c1996ba021b782407ad4d0cbb8576b157940f50d8f4bf85419a5c0`。

## Context 2.2 双向真机闭环（2026-08-03）

- 设备仍为 Xiaomi `25057RA09C`，Android 16 / HyperOS V816；
- 旧数据已先备份，再安装当前签名的 `com.mimotrust.guardian` 与
  `com.mimotrust.controlledcontent`，随后成功恢复小真历史记录和 Sandbox 偏好；
- 两个包的签名短哈希均为 `c69aa322`；悬浮窗和通知权限已开启；
- 小真后端运行于电脑 `127.0.0.1:8000`，手机通过
  `adb reverse tcp:8000 tcp:8000` 访问；内容与 grant 仍来自阿里云网关；
- 打开评论、转发面板分别产生 `trigger=comment/share`，小真均记录
  `CONTEXT_CANDIDATE_RECEIVED`；此时没有提交后端或兑换 grant；
- 点击悬浮球后依次记录 `CONTENT_CONTEXT_REQUEST_SENT`、
  `CONTENT_CONTEXT_REQUEST_RECEIVED`、`guardian_request`、
  `GUARDIAN_CONTEXT_ACCEPTED` 和 `VERIFICATION_JOB_CREATED`；
- 未先打开评论或转发面板时，直接点击悬浮球同样完成请求和任务创建。

实测任务：

| 内容 | 类型 | 任务 ID | 最终状态 |
|---|---|---|---|
| `video-001` | `video` | `545df7c3-8ddd-4ee9-8fd4-32bad26f0e7b` | `completed` |
| `video-001`（无候选直接点击） | `video` | `f73b45e5-3ffa-49e3-925a-a0b47fa6e1ed` | `completed` |
| `article-001` | `article` | `0ae3ac12-4877-45b4-a73c-619bb33e9274` | `completed` |
| `tuwen-001` | `rich_article` | `bfbeab2c-ba94-4ecb-afb2-2a6bd8c47168` | `completed` |
| `pictures-001` | `image_gallery` | `82888ff9-a716-4aa9-b005-8a0c655562ec` | `completed` |

以上任务均由 Android 接收后唯一入队，经 `POST /v1/content-contexts` 进入后端，完成
grant 兑换、Manifest 校验、资源下载与 SHA-256 校验后返回结果。云端尚无音频素材，因此
`audio` 仍只有合同和自动化测试记录。此次本地后端未配置 `MIMO_API_KEY`，任务完成结果
属于本地结构化预览，不能作为 MiMo 实际理解和证据检索效果验收。

## MiMo 与证据检索真机闭环（2026-08-03）

- 本地 `.env` 已配置 MiMo 与 Exa，`GET /api/health` 返回
  `mimo_configured: true`；
- 首次真实视频调用暴露 MiMo 视频概括响应兼容问题：该路径只读取
  `message.content`，没有兼容 `reasoning_content`，任务在 `media_extracting` 失败；
- 视频概括现统一使用结构化 JSON Schema 和公共响应读取逻辑，相关测试 `35/35` 通过；
- 真机重新核验 `video-001`，任务
  `52e0aae3-b434-4f18-9aa0-431b504af98a` 完成视频理解、主张提取、检索规划、
  Exa 检索、证据初筛和报告生成；
- 最终状态为 `completed`，识别 2 条主张、使用 4 条证据，移动端结论为
  `存在误导表达`，摘要为“基础事实有依据，但输入将不同事件混淆，形成误导性叙事。”；
- 小真历史页已真机确认显示该结果，分析用时约 43 秒。
