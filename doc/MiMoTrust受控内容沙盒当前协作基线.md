# MiMoTrust 受控内容沙盒当前协作基线

> 状态：当前实施与联调基线  
> 更新时间：2026-08-02  
> 适用团队：受控内容沙盒、守护者 App、守护者后端、平台内容网关  
> 权威关系：本文记录当前 2.2 沙盒实现，不替代冻结规格、Schema 或 Manifest 1.0

## 1. 当前结论

受控内容沙盒的五类 Android 展示端和最小平台内容网关已经完成。沙盒在用户打开评论或
转发面板时立即发送 Context 2.2 `deferred_grant` 候选；收到 Guardian 主动请求后才申请
一次性 grant，并通过 Kotlin 向固定守护者包响应当前内容。

当前设备尚未安装正式守护者包 `com.mimotrust.guardian`。因此发送端、网关、Payload
构造和广播调用已经真机验证，Receiver 接收、授权检查、幂等入队、后端提交和报告展示
仍待守护者侧完成。

当前已完成与 Android App 分离的开发者内容管理服务，用于五类内容规范化上传、Manifest
预览和运行时 registry 发布。普通用户仍无上传入口；推荐、账号和核验逻辑不在沙盒范围内。
App 通过公开只读 `/v1/feed` 自动读取活动内容；该目录读取不申请 grant、不发送 Context，
也不修改已经冻结的跨系统合同。

2026-08-02 已完成沙盒侧 Context 2.2 主动请求迁移：`comment/share` 只通知候选并让
守护者悬浮球提示；用户点击悬浮球后，守护者先向前台沙盒请求当前内容，沙盒才申请新鲜
grant 并响应。Schema、样例、Dart、Kotlin、测试和 Debug APK 已同步更新。

同日已部署独立开发者内容管理服务 `mimotrust-content-admin.service`，监听 ECS
`127.0.0.1:8788`，通过 SSH 隧道访问。服务端支持五类草稿上传、资源规范化、Manifest
预览和原子发布。运行时 registry 位于 `/var/lib/mimotrust/content_registry`，当前包含三条
视频、文章、图文和图集；公网网关健康检查当前 `content_count=6`。当前云端配置 APK 已支持
五类模型和渲染器，启动、前台恢复或手动刷新时获取目录；失败时回退到打包的三条视频。

## 2. 当前与目标协议

| 项目 | 固定值 |
|---|---|
| 沙盒 applicationId | `com.mimotrust.controlledcontent` |
| Android 启动器显示名称 | `sandbox`（仅显示名称，不改变协议） |
| 守护者 applicationId | `com.mimotrust.guardian` |
| Flutter MethodChannel | `com.mimotrust.controlledcontent/context` |
| 守护者请求 Action | `com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT` |
| 请求目标 / Extra | `com.mimotrust.controlledcontent` / `request_id` |
| 沙盒响应/候选 Action | `com.mimotrust.intent.action.CONTENT_CONTEXT` |
| 响应目标 / Extra | `com.mimotrust.guardian` / `payload` |
| Context Schema | `2.2` |
| Manifest Schema | `1.0` |
| Provider ID | `mimotrust_sandbox` |
| Audience | `mimotrust_guardian_backend` |
| `source_app` | `mimotrust_controlled_content` |
| 可选签名权限 | `com.mimotrust.permission.SEND_CONTENT_CONTEXT` |

Flutter 与 Kotlin 之间的内部方法名为 `sendContentContext`，参数是单个已序列化的
Context 2.2 JSON 字符串。它不是跨 App 协议，不允许据此创建第二套 Action、Extra 或
Payload。

Debug 联调阶段暂不启用 signature 权限。双方统一签名证书后，再共同启用固定权限。

## 3. 系统责任

| 系统 | 负责 | 不负责 |
|---|---|---|
| 受控内容沙盒 | 展示固定内容、本地维护当前状态；候选通知；主动请求时申请 grant 并响应 | 搜索、真假判断、核验任务、报告展示 |
| 平台内容网关 | 校验内容身份、签发/兑换一次性 grant、返回 Manifest | 上传页面、推荐、分析、证据检索 |
| 守护者 App | 用户授权、悬浮球、主动请求/超时、Receiver 校验、候选提示、请求响应幂等入队、状态展示 | 因候选自动获取资源；在 `onReceive()` 中执行下载、HTTP、模型或检索 |
| 守护者后端 | 兑换 grant、读取内容、校验哈希、缓存、分析、检索、证据和任务状态 | 信任设备时间或把广播成功当作任务成功 |

## 4. 当前实施状态

| 模块 | 状态 | 当前结果 |
|---|---|---|
| Context 2.2 Schema | 完成 | 6 个合法样例通过，7 个非法样例拒绝 |
| Manifest 1.0 | 完成 | 3 个活动视频 Manifest 通过校验 |
| 最小内容网关 | 完成并部署 Debug 环境 | 阿里云 ECS `http://47.94.58.72`，5 个路由，运行时 registry 自动重载，内存 grant，180 秒过期，单次兑换 |
| Flutter Android App | 完成远程多类型 Feed 阶段 | 远程优先、内置回退；文章/图文/画廊采用 Feed 预览与独立详情；五类模型/渲染器、本地互动和异常降级 |
| Flutter 到 Kotlin | 完成 | 固定 MethodChannel，单字符串 Payload |
| Kotlin 显式广播 | 完成 | 固定 Action、目标包和 Extra，32 KB 上限 |
| 沙盒主动请求 Receiver | 完成，待真机验收 | 仅在 `MainActivity` resumed 时动态注册 |
| 守护者悬浮球/主动请求 | main 已实现视频流程，待联调 | 包含权限、前台服务、状态机、5 秒超时和防抖 |
| 守护者 Receiver | main 已实现视频流程，待联调 | 当前严格接受 2.2，非视频资源消费待扩展 |
| 守护者可靠入队 | 待守护者团队完成 | 需要授权、幂等存储和 WorkManager |
| 守护者后端 | 待后端团队确认 | 部署地址、认证和负责人尚未提供 |
| 文章/图文/图片 | 已实现渲染能力 | `article-001/v1` 已进入远程 Feed；富文章和图集等待真实发布内容 |
| 音频 | 渲染能力完成，素材待提供 | 使用 `just_audio`，不得生成伪造的活动 Manifest |

## 5. 当前演示内容

| 内容 | 标题 | 时长 | 分辨率 | 初始点赞/评论/转发 |
|---|---|---:|---:|---:|
| `video-001:v1` | SkyNomad 澎程事故传言 | 22.467 秒 | 720×1280 | 1284 / 86 / 214 |
| `video-002:v1` | 2026年城乡居民基础养老金月最低标准再提高20元 | 19.301 秒 | 720×1280 | 936 / 42 / 118 |
| `video-003:v1` | 未成年人网络游戏防沉迷新规 | 28.320 秒 | 720×1066 | 2456 / 173 / 367 |
| `article-001:v1` | 17岁男孩因敌敌畏溅裤子上进了ICU，公共消杀不该成为有毒的“陷阱” | - | 纯文本 | 0 / 0 / 0 |

完整 URL、SHA-256、资源大小和存储信息以以下文件为准：

- `sandbox/content_registry/registry.json`；
- `sandbox/content_registry/manifests/video-001.v1.json`；
- `sandbox/content_registry/manifests/video-002.v1.json`；
- `sandbox/content_registry/manifests/video-003.v1.json`。

`display_metrics` 只用于沙盒界面。点赞数叠加本机点赞状态，评论数叠加本地评论，
转发数叠加本次运行完成的模拟转发。所有互动数量均不进入 Manifest 1.0 或 Context 2.2。

## 6. 当前 2.2 触发语义

| 用户动作 | 发送 Context | 本地效果 |
|---|---:|---|
| 浏览、播放、暂停、拖动进度 | 否 | 只改变播放状态 |
| 上下切换视频 | 否 | 切走暂停，当前页播放 |
| 页面停留、后台、恢复前台 | 否 | 执行生命周期策略 |
| 点赞或取消点赞 | 否 | 状态和数量按内容版本持久化 |
| 打开评论面板 | 是，`comment` | 展示预置和本地评论 |
| 提交本地评论 | 否 | 评论和数量保存在本机 |
| 打开转发面板 | 是，`share` | 展示固定虚拟联系人 |
| 完成模拟转发 | 否 | 本次运行的转发数加一 |

`comment` 表示“打开评论面板”，不表示提交评论；`share` 表示“打开转发面板”，不表示
分享完成。Payload 不得包含评论正文、联系人、用户稳定标识、Cookie、长期凭据、媒体
二进制、完整浏览历史或核验结论，UTF-8 编码后不得超过 32 KB。

当前 APK 在 `comment/share` 时不访问网关，只发送 `deferred_grant` 候选。只有收到合法
`REQUEST_CONTENT_CONTEXT` 后才申请 grant 并返回 `guardian_request`。

## 7. 当前 2.2 数据流

```mermaid
sequenceDiagram
    participant U as 用户
    participant S as 受控内容沙盒
    participant G as 平台内容网关
    participant R as 守护者 Receiver
    participant W as 守护者后台任务
    participant B as 守护者后端

    U->>S: 打开评论或转发面板
    S->>R: Context 2.2 deferred_grant 候选
    U->>R: 点击悬浮球
    R->>S: REQUEST_CONTENT_CONTEXT(request_id)
    S->>G: POST /v1/context-grants
    G-->>S: 一次性 grant + content_ref
    S->>R: guardian_request，event_id=request_id
    Note over S,R: 当前代码和 APK 已完成，双向真机待验证
    R->>R: 授权、Schema、event_id 幂等
    R->>W: 唯一可靠后台工作
    W->>B: POST /v1/content-contexts
    B->>G: POST /v1/grants/exchange
    G-->>B: Manifest 1.0
    B-->>W: cache/task 状态
```

两个方向的广播均为尽力交付，不提供业务 ACK。`sendBroadcast()` 返回不代表 Receiver 已接收，
更不代表后端已创建核验任务。

### 7.1 Context 2.2 详细数据流

```mermaid
sequenceDiagram
    participant U as 用户
    participant S as 受控内容沙盒
    participant G as 守护者 App
    participant P as 平台内容网关
    participant B as 守护者后端

    Note over S: 普通浏览只更新 App 内当前状态，不跨 App 发送
    opt 打开评论或转发面板
        S->>G: CONTENT_CONTEXT (2.2, comment/share, deferred_grant)
        G->>G: 保存候选，悬浮球 AVAILABLE/闪烁
        Note over G,P: 不提交后端、不兑换 grant、不下载资源
    end
    U->>G: 点击悬浮球
    G->>G: 生成 UUID request_id，进入 REQUESTING
    G->>S: REQUEST_CONTENT_CONTEXT (request_id)
    S->>S: 快照当前 content_ref/view_state
    S->>P: POST /v1/context-grants
    P-->>S: 新鲜 180 秒一次性 grant
    S->>G: CONTENT_CONTEXT (2.2, guardian_request, event_id=request_id)
    G->>G: 校验、关联、幂等入队，进入 PROCESSING
    G->>B: POST /v1/content-contexts
    B->>P: POST /v1/grants/exchange
    P-->>B: Manifest 1.0 + 短期资源
    B-->>G: 缓存/任务/报告状态
```

用户无需先触发 `comment/share`。只要沙盒在前台且有有效当前内容，悬浮球在 `IDLE` 状态也可点击。沙盒退后台或无内容时不响应，守护者在 3–5 秒后显示不可用。不得使用无障碍或屏幕抓取扩展到第三方 App。

## 8. 平台内容网关合同

当前云端 Debug 网关地址：

```text
http://47.94.58.72
```

路由：

```text
GET  /health
GET  /v1/feed
POST /v1/context-grants
POST /v1/grants/exchange
GET  /assets/...
```

申请 grant：

```json
{
  "content_id": "video-003",
  "content_version": "v1",
  "audience": "mimotrust_guardian_backend",
  "scopes": ["manifest:read", "asset:read"]
}
```

兑换时提交 `grant_code`、`audience`、`content_id` 和 `content_version`。成功响应为：

```json
{
  "grant_id": "...",
  "manifest": { "manifest_version": "1.0" }
}
```

当前网关错误至少区分：

```text
GRANT_EXPIRED
GRANT_REPLAYED
AUDIENCE_MISMATCH
CONTENT_MISMATCH
CONTENT_UNAVAILABLE
```

云端当前为 ECS 单实例、Nginx HTTP 入口和内存 grant，已通过公网健康检查、签发、兑换、
视频下载、SHA-256 和重放拒绝验证。该地址和内存实现不是生产合同。后期允许替换数据源、域名和持久化实现，但必须保持
请求语义、Audience、Manifest 1.0 和单次 grant 兑换约束。

## 9. Android 广播合同

当前 2.2 沙盒候选和响应发送方式为：

```kotlin
Intent("com.mimotrust.intent.action.CONTENT_CONTEXT")
    .setPackage("com.mimotrust.guardian")
    .putExtra("payload", payloadJson)
```

当前守护者请求方式为：

```kotlin
Intent("com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT")
    .setPackage("com.mimotrust.controlledcontent")
    .putExtra("request_id", requestId)
```

守护者 Receiver 的目标处理顺序：

```text
验证 Action 和 payload 存在
  -> 检查用户当前授权
  -> 检查 32 KB 上限
  -> 解析并校验 Context 2.2（main 当前未实现 2.1 只读兼容）
  -> comment/share: 去重保存候选并提示悬浮球，立即返回
  -> guardian_request: 校验 event_id = 待处理 request_id
  -> 以 event_id 插入唯一待处理记录并调度唯一后台上传工作
  -> 立即返回
```

`onReceive()` 不得执行 HTTP、媒体下载、数据库长事务、MiMo 调用、检索或轮询。没有
既有可靠调度方案时使用 WorkManager，唯一工作名建议为
`content-context-{event_id}`。

Receiver 至少区分：

```text
CONSENT_REQUIRED
INVALID_ACTION
PAYLOAD_MISSING
PAYLOAD_TOO_LARGE
UNSUPPORTED_SCHEMA
INVALID_FIELD
DUPLICATE_EVENT
UNSUPPORTED_CONTENT_TYPE
UNSUPPORTED_ACCESS_MODE
```

## 10. 守护者到后端合同

建议提交接口：

```http
POST /v1/content-contexts
```

```json
{
  "request_id": "8f052041-20f1-4a38-82be-5663dad7787e",
  "guardian_app_version": "0.1.0",
  "context": { "schema_version": "2.2", "trigger": "guardian_request" }
}
```

建议响应：

```json
{
  "request_id": "8f052041-20f1-4a38-82be-5663dad7787e",
  "task_id": "task-001",
  "accepted": true,
  "cache_status": "miss",
  "task_status": "queued"
}
```

任务查询：

```http
GET /v1/verification-tasks/{task_id}
```

后端部署地址、认证方式和负责人仍待后端团队提供。守护者不得在这些值未确认时自行把
开发假地址固化为生产合同。

## 11. 联调日志

统一格式：

```text
MiMoTrustSandbox:  CONTENT_CONTEXT_SEND event_id=... type=... trigger=...
MiMoTrustGuardian: CONTENT_CONTEXT_REQUEST request_id=...
MiMoTrustSandbox:  CONTENT_CONTEXT_REQUEST_RECEIVED request_id=...
MiMoTrustReceiver: CONTENT_CONTEXT_RECEIVED event_id=... type=... trigger=...
MiMoTrustReceiver: CONTENT_CONTEXT_REJECTED event_id=... reason=...
MiMoTrustGuardian: CONTEXT_UPLOAD_ENQUEUED event_id=... request_id=...
MiMoTrustGuardian: VERIFY_TASK_ACCEPTED request_id=... task_id=... cache=...
MiMoTrustGateway:  CONTENT_GRANT_EXCHANGED grant_id=... content_id=...
```

日志不得记录完整 Payload、`grant_code`、签名 URL、评论正文、联系人、Cookie 或账号
凭据。

## 12. 云端与本地联调

云端 Debug APK 使用：

```powershell
cd sandbox\mimotrust_controlled_content
flutter build apk --debug --dart-define-from-file=config/cloud-debug.json
```

只有切回本地开发网关时才需要：

```powershell
python -m sandbox.content_gateway.server --host 127.0.0.1 --port 8787
adb reverse tcp:8787 tcp:8787
```

安装当前沙盒 APK：

```powershell
adb install -r sandbox\mimotrust_controlled_content\build\app\outputs\flutter-apk\app-debug.apk
```

当前构建：

```text
大小：220011733 bytes
SHA-256：9c6a4af36935dae12d6bbad667f6827a38605fd9f90e530831fb928ac262fccf
网关配置：http://47.94.58.72
状态：构建完成；当前 ADB 无设备，本次多类型版本尚未完成真机安装
```

建议联调日志命令：

```powershell
adb logcat -c
adb logcat -s MiMoTrustSandbox:I MiMoTrustReceiver:I MiMoTrustGuardian:I *:S
```

联调前必须确认：

```powershell
adb shell pm list packages com.mimotrust.guardian
adb reverse --list
```

不得为了测试方便把目标包临时改为 `com.mimotrust.xiaozhen` 或其他包。

## 13. 当前验收证据

- Dart 静态分析：无问题；
- Flutter 测试：38/38；
- 网关测试：13/13；
- 开发者内容管理服务测试：13/13；
- 合同校验：6 个合法 Context、7 个非法 Context、3 个内置活动 Manifest；
- Xiaomi `25057RA09C`，Android 16 / API 36 真机安装和播放通过；
- 三条视频竖向切换不发送 Context；
- 点赞、评论提交、模拟转发完成不发送 Context；
- 打开评论和转发面板各发送一条，`event_id` 不同；
- 守护者缺失、网关失败或媒体失败不使沙盒崩溃；
- 发送日志未出现 Payload、grant、评论、联系人或 Cookie。

详细记录和截图索引见 `sandbox/DEVICE_VERIFICATION.md`。

## 14. 下一轮协作顺序

1. 在目标真机安装本次 Context 2.2 Debug APK，并确认 main Guardian 已安装且悬浮窗启用；
2. 覆盖视频 `comment/share` 候选闪烁和无前置候选主动点击，保存双向广播与 grant 日志；
3. 验证 5 秒超时、重复点击、断网、沙盒后台和 grant 重放拒绝；
4. 扩展 main Guardian 的解析、资源选择和任务提交，支持音频、文章、图文和图集；
5. 后端确认五类资源输入并完成缓存、分析、检索和报告状态；
6. 决定是否按冻结迁移条款补回 Guardian 对旧 2.1 候选的只读兼容；
7. 归档 APK、SHA-256、双向日志、网关兑换日志和录屏。

## 15. 待确认事项

| 事项 | 责任方 | 当前状态 |
|---|---|---|
| 守护者工程目录和技术栈 | 守护者 App | 待确认 |
| Receiver 组件名与安装包 | 守护者 App | 待提供 |
| 用户授权状态的数据来源 | 守护者 App | 待确认 |
| 悬浮窗权限与厂商后台限制 | 守护者 App | 需在目标真机验证 |
| 无悬浮窗权限时的通知入口 | 守护者 App | 合同要求提供降级入口 |
| 后端部署地址和认证 | 守护者后端 | 待提供 |
| `POST /v1/content-contexts` 负责人 | 守护者后端 | 待指定 |
| 报告第一版展示形态 | 守护者 App/产品 | 待确认 |
| 双方统一签名证书 | Android 双方 | 后置处理 |
| 最终命名的私有 OSS Bucket | 平台侧 | 正式演示前处理 |
| 音频真实素材 | 内容侧 | 尚未提供 |

## 16. 变更规则

- 代码与口头约定冲突时，以冻结 Schema、合同样例和冻结规格为准；
- 增加可选字段可保持 `2.x`，删除字段、改变类型或语义必须升级主版本；
- 迁移期守护者兼容 Context 2.1/2.2；2.1 `comment/share` 也只能按候选处理；
- 悬浮球点击固定使用 `guardian_request`，不得伪装成 `comment/share`；
- 未识别的 `trigger`、`content_type` 或访问模式必须拒收；
- 合同变更必须同步更新 Schema、正反样例、沙盒、Receiver、后端和网关测试；
- 包名、Action、Extra、Schema、Provider ID 和 Audience 不得由任一团队单方修改；
- 运行环境事实不属于协议，例如设备序列号、当前 PID、Debug 网关端口和守护者是否安装。

## 17. 关联文件

- `doc/沙盒下阶段实现交接说明.md`；
- `doc/MiMoTrust受控内容沙盒冻结规格.md`；
- `doc/MiMoTrust受控内容沙盒跨系统协作文档.md`；
- `doc/MiMoTrust受控内容沙盒首轮交付报告.md`；
- `doc/MiMoTrust非视频内容后端方案评审确认单.md`；
- `contracts/content_context.schema.json`；
- `contracts/content_manifest.schema.json`；
- `sandbox/IMPLEMENTATION_CONTRACT.md`；
- `sandbox/DEVICE_VERIFICATION.md`；
- `sandbox/content_gateway/README.md`；
- `sandbox/mimotrust_controlled_content/README.md`。
