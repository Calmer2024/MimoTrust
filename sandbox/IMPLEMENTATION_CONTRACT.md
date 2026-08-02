# MiMoTrust 受控内容沙盒实施合同

> 状态：已冻结  
> 日期：2026-08-02
> 当前实现依据：《MiMoTrust 受控内容沙盒跨系统协作文档》Context 2.2
> 实施状态：沙盒代码、Schema、样例、测试和 Debug APK 已迁移；双向真机联调待完成

## 固定标识

| 项目 | 固定值 |
|---|---|
| 沙盒 applicationId | `com.mimotrust.controlledcontent` |
| 守护者 applicationId | `com.mimotrust.guardian` |
| MethodChannel | `com.mimotrust.controlledcontent/context` |
| Broadcast Action | `com.mimotrust.intent.action.CONTENT_CONTEXT` |
| Intent Extra | `payload` |
| Context Schema | `2.2` |
| Manifest Schema | `1.0` |
| Provider ID | `mimotrust_sandbox` |
| Audience | `mimotrust_guardian_backend` |
| source_app | `mimotrust_controlled_content` |

Flutter 与 Kotlin 之间使用内部方法 `sendContentContext`，参数是单个已序列化的
Context 2.2 JSON 字符串。该方法只属于 App 内部桥接，不新增外部协议；Kotlin 不重组
Payload，直接使用上表固定的 Action、目标包和 Extra 发送。

不得引入第二套包名、Action、Extra、Schema 或字段语义。

## 固定行为

- 内容类型为 `video`、`audio`、`article`、`rich_article`、`image_gallery`；
- 打开评论面板时发送 `comment` 候选，打开转发面板时发送 `share` 候选；
- 用户点击守护者悬浮球后，前台沙盒响应 `guardian_request`；
- 浏览、播放、切页、页面停留、进入后台和恢复前台均不发送上下文；
- Payload 不包含评论正文、联系人、用户稳定标识、Cookie、长期凭据或媒体二进制；
- 两个方向均使用显式、尽力交付广播，不提供业务 ACK；
- 守护者、网关或媒体不可用时，沙盒继续浏览和互动；
- 普通用户不具备上传能力；开发者可通过独立的 `content_admin` 管理服务规范化上传，
  服务端生成并校验 Manifest 1.0 后更新运行时 registry。该管理服务不属于 Android App，
  不改变 Context、grant 或跨 App 协议。

## Android 基线

- 首版 `minSdk` 为 24，`compileSdk` 和 `targetSdk` 为 36；
- Debug 联调暂不启用 `com.mimotrust.permission.SEND_CONTENT_CONTEXT`；
- 双方统一签名证书后再启用 signature 权限；
- 目标真机型号、Android 版本和守护者 Receiver 安装状态属于联调环境事实，不改变协议合同。

## 当前素材约束

- 三条视频已有 OSS URL、真实 SHA-256、封面和已读取的媒体元数据；
- 纯文章、图文和图片资源已有本地固定快照；
- 音频素材尚未提供，注册表中只能标为 `pending_asset`，不得生成伪造的有效 Manifest；
- 原始素材不移动、不覆盖，沙盒只保存用于固定演示快照的副本。

## 当前合同：Context 2.2

以下行为已在沙盒代码、合同测试、Flutter 测试和 Debug APK 中实现；真实 Guardian 双向
广播、超时和后端资源读取仍需真机验收。

| 项目 | 固定值 |
|---|---|
| 守护者请求 Action | `com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT` |
| 请求目标包 | `com.mimotrust.controlledcontent` |
| 请求 Extra | `request_id`（UUID） |
| 沙盒响应 Action | `com.mimotrust.intent.action.CONTENT_CONTEXT` |
| 响应目标包 | `com.mimotrust.guardian` |
| 响应 Extra | `payload` |
| Context Schema | `2.2` |
| 主动请求 trigger | `guardian_request` |

当前行为：

- 普通浏览、播放、切页和停留仍不发送跨 App 消息；Flutter 仅在 App 内维护当前内容和查看状态；
- `comment/share` 发送 `content_access.mode = deferred_grant` 的候选通知，不申请可用 grant；
- 候选只使守护者悬浮球进入 `AVAILABLE`/闪烁，不自动上传、兑换或下载；
- 用户点击悬浮球后，守护者先发送带 `request_id` 的显式请求；无需先触发候选通知；
- 沙盒请求 Receiver 只在 `MainActivity` resumed 时动态注册；无前台有效内容时不响应；
- 沙盒收到请求后快照当前内容/查看状态，申请新鲜 180 秒一次性 grant，并返回 `trigger = guardian_request`、`event_id = request_id` 的 Context 2.2；
- 守护者以 3–5 秒超时、防抖和 `event_id` 唯一约束处理重复点击/响应；只有 `guardian_request` 响应进入后端队列；
- main 分支 Guardian 当前严格读取 2.2；旧 2.1 APK 与其不兼容，不得混装联调；
- 悬浮球点击不得伪装成 `comment/share`，不得使用无障碍或屏幕抓取取得第三方 App 内容；
- 统一签名后，`com.mimotrust.permission.SEND_CONTENT_CONTEXT` 同时保护请求和响应方向；Debug 联调暂不启用。

当前沙盒五类内容均可生成 2.2 响应，但 main 分支 Guardian 的资源兑换和任务创建仍只支持
`video`。非视频端到端核验需要继续扩展 Guardian/后端，不能仅以沙盒响应成功作为交付依据。
