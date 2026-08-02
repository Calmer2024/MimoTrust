# MiMoTrust 受控内容沙盒冻结规格

> 状态：已冻结目标合同；实现迁移中
> 版本：0.5
> 日期：2026-08-02
> 目标：以最小实现验证“平台授权提供当前内容，守护者完成缓存或核验”的完整链路。
> 实施现状：目标为 Context 2.2；当前 APK、JSON Schema、样例和代码仍是 Context 2.1

> 命名说明：对外产品名和英文标识统一为 `MiMoTrust`；下文统一使用小写技术标识 `mimotrust`。

## 1. 冻结范围

沙盒由三部分组成：

```text
受控内容 Android App
  -> 模拟真实浏览、评论和转发场景
  -> comment/share 只发送候选通知
  -> 响应守护者主动请求，发送当前查看状态和一次性 grant

最小平台内容网关
  -> 签发和兑换 grant
  -> 返回版本化 Content Manifest

内容资源与准备脚本
  -> 管理固定演示数据
  -> 计算 SHA-256 并生成 Manifest
```

沙盒不包含 MiMo、搜索、证据处理、核验任务、核验结果 UI、推荐系统、账号、上传、真实社交和内容管理后台。

## 2. 技术路线与目录

| 部分 | 冻结选择 |
|---|---|
| App UI | Flutter 3.44.2 + Dart 3.12.2 |
| Android 通信 | Kotlin + MethodChannel + 显式广播 |
| 视频/音频 | 视频使用 `video_player`，音频使用 `just_audio` |
| 本地互动 | `shared_preferences` |
| 网关请求 | `http` |
| 平台网关 | Python 3.12 标准库，无第三方服务端依赖 |
| 网关状态 | 内存 grant + 静态 JSON 内容注册表 |
| 媒体 | 公网 HTTPS OSS |
| 配置 | Flutter `--dart-define`，不在代码写死环境域名 |

新工程目录：

```text
sandbox/
  mimotrust_controlled_content/  # 全新 Flutter Android 工程
  content_gateway/               # 最小 Mock 网关
  content_registry/              # 内容元数据和 Manifest
  tools/                         # 哈希、可访问性和 Manifest 生成脚本
contracts/                       # 跨系统 Schema 和样例
```

固定标识：

```text
Flutter project:  mimotrust_controlled_content
applicationId:    com.mimotrust.controlledcontent
guardian package: com.mimotrust.guardian
MethodChannel:    com.mimotrust.controlledcontent/context
Request Action:   com.mimotrust.intent.action.REQUEST_CONTENT_CONTEXT
Request Extra:    request_id
Response Action:  com.mimotrust.intent.action.CONTENT_CONTEXT
Response Extra:   payload
Context Schema:   2.2 (target; current implementation is 2.1)
Manifest Schema:  1.0
```

## 3. App 页面与交互

首屏直接进入纵向内容 Feed，不制作登录、首页宣传或管理页面。

- 视频：当前页自动播放、循环，点击暂停/继续，静音按钮，简化进度条；
- 音频：封面、播放/暂停、进度条，离开页面停止；
- 文章：标题、作者、发布时间和可滚动正文；
- 图文：按 Manifest 顺序渲染文本块和图片块；
- 图片：单图查看或多图横滑，显示当前序号；
- 通用互动：点赞、预置+本地评论、虚拟联系人转发面板；
- 加载、空数据、媒体失败和重试状态必须可见。

点赞和本地评论重启后保留；转发记录不持久化。

## 4. 演示内容

最终数据集：

- 3 条视频；
- 1 条音频；
- 1 篇纯文章；
- 1 篇图文；
- 1 条单图；
- 1 条多图画廊。

开发顺序为“1 条视频端到端打通 -> 3 条视频 -> 文章/图片 -> 音频”。各类型只增加数据和渲染组件，不增加新的跨 App 协议。

当前三条视频 URL 可访问且支持 Range；首条视频已完成标准 Content Manifest 和 SHA-256 校验。仍存在一个发布前处理项：

1. OSS 域名仍含旧项目命名，只能作为开发期临时资源，正式演示资源应迁移到最终命名的私有 Bucket。

每条内容入库前必须通过：HTTPS、MIME、大小、可访问性、SHA-256、时长/尺寸和 Manifest Schema 校验。

内容上架全部采用手工流程：开发者通过阿里云 OSS 控制台上传文件，记录 URL 和资源属性，在本地计算 SHA-256，然后手工更新 Manifest 与内容注册表。内容上传操作在项目外完成，沙盒不建设内容上传能力。

## 5. 三种触发的冻结语义

| 触发 | 精确定义 |
|---|---|
| `comment` | 打开评论面板时发送候选通知，不表示提交评论，不传评论正文，不申请或携带可用 grant |
| `share` | 打开转发面板时发送候选通知，不表示分享完成，不传联系人，不申请或携带可用 grant |
| `guardian_request` | 用户点击守护者悬浮球后，守护者请求沙盒当前内容；沙盒即时快照状态并申请新鲜 grant 后响应 |

普通浏览、播放、切页和页面停留不发送跨 App 上下文，沙盒不实现停留计时器或自动预分析。Flutter 仅在 App 内维护当前内容和查看状态。`comment/share` 只让守护者保存候选并使悬浮球闪烁，不自动提交后端、兑换 grant 或下载资源。

用户无需先打开评论或转发面板。只要受控内容沙盒在前台且存在有效当前内容，点击悬浮球就能发起 `guardian_request`。该“任何时候”不覆盖第三方 App；禁止使用无障碍、屏幕抓取或常驻监听推断当前内容。

## 6. 广播与网关

目标双向广播严格遵循《MiMoTrust 守护者 App 跨系统协作文档》Context 2.2，不传输媒体二进制、评论正文、联系人、Cookie 和长期凭证：

```text
守护者 -> 沙盒：REQUEST_CONTENT_CONTEXT，目标 com.mimotrust.controlledcontent，Extra request_id
沙盒 -> 守护者：CONTENT_CONTEXT，目标 com.mimotrust.guardian，Extra payload
guardian_request 响应：event_id = request_id
```

沙盒请求 Receiver 只在 `MainActivity` resumed 期间动态注册；退后台或无有效内容时不响应。守护者使用 3–5 秒超时并显示不可用，不得无限等待。双方统一签名后，同一个 signature 权限 `com.mimotrust.permission.SEND_CONTENT_CONTEXT` 保护两个方向；Debug 联调阶段暂不开启。

网关最小接口：

```text
GET  /health
POST /v1/context-grants
POST /v1/grants/exchange
```

`comment/share` 的 `content_access.mode` 固定为 `deferred_grant`，不含可兑换 grant。仅 `guardian_request` 响应使用 `grant_exchange`：沙盒在收到请求后申请默认 180 秒、一次性兑换并绑定 `mimotrust_guardian_backend` audience、内容 ID、版本和 scope 的新鲜 grant。续期接口只在端到端分析证明确实需要时增加。

迁移期间守护者兼容读取 2.1 和 2.2；任何 2.1 `comment/share` 中已有 grant 也只能作为候选，不允许自动兑换。悬浮球点击不得伪装成 `comment` 或 `share`。

## 7. 验收标准

1. Debug APK 可在目标 Android 真机安装运行；
2. 五种内容类型可浏览，当前音视频唯一播放；
3. `comment/share` 只提示候选，单纯停留不发送，三者均不自动获取资源；
4. 沙盒前台有内容时，无需 `comment/share` 前置动作，点击悬浮球能取得 Context 2.2；
5. `guardian_request` Payload 的 `event_id/request_id`、ID、版本、SHA-256 和查看位置与响应瞬间当前项一致；
6. 沙盒退后台或无内容时在 3–5 秒内显示不可用；快速重复点击只创建一个请求/任务；
7. 守护者缺失、网关失败和媒体加载失败均不导致 App 崩溃；
8. grant 可正常兑换一次，过期、重放和错误 audience 被拒绝；
9. 守护者后端能读取 Manifest、下载资源并校验 SHA-256；
10. 真机完成视频、文章、画廊状态、快速切页、后台、断网和网关拒绝回归；
11. 归档 APK、APK SHA-256、请求/响应/兑换日志和演示录屏。

## 8. 实施顺序与时间盒

```text
Context 2.2 Schema、正反样例及 2.1 兼容读取
  -> 守护者悬浮球、前台服务/通知降级与状态机
  -> 守护者主动请求、超时、防抖和请求关联
  -> 沙盒前台动态 Receiver 与当前状态快照
  -> comment/share deferred_grant 候选通知
  -> guardian_request 新鲜 grant 响应
  -> 守护者可靠入队与后端提交
  -> 网关兑换和一条视频端到端联调
  -> 扩展其他内容类型
  -> 异常、缓存和真机验收
```

三人协作的目标时间盒为 4 个工作日，其中第 1 个工作日必须打通“固定上下文 -> 网关兑换 -> Manifest”，第 3 个工作日前必须打通一条视频的端到端链路。如进度受阻，先保留三条视频、一篇图文和一组多图，音频作为最后扩展项。

## 9. 当前环境结论

| 检查项 | 结果 |
|---|---|
| Flutter / Dart | Flutter 3.44.2 / Dart 3.12.2；当前三视频工程已完成构建、分析和测试 |
| ADB | 36.0.0 可用 |
| Android 真机 | 已在 Xiaomi 25057RA09C、Android 16 / API 36 完成 2.1 发送端验证；当前会话未连接 |
| Java / Android SDK | JDK 17.0.10 可用；现有工程已成功构建 targetSdk 36 APK |
| Python | 3.12.2 可用 |
| 本地网关 | 代码与测试已完成；当前未运行，默认使用 `127.0.0.1:8787` 和 `adb reverse` |
| 现有视频网络 | 3 条 URL 均返回 HTTP 200、`video/mp4` 并支持 Range |

## 10. 下一阶段动作

1. 更新 Context 2.2 Schema、样例和合同测试；
2. 创建守护者工程并实现悬浮球主动请求链路；
3. 在现有沙盒工程增加 resumed 动态 Receiver、状态快照和 Context 2.2 响应；
4. 以一条视频完成双向端到端链路，再覆盖文章和画廊状态；
5. 每完成一层立即验证，不等到最后集中排错。
