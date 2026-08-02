# MiMoTrust 受控内容沙盒实施合同

> 状态：已冻结  
> 日期：2026-08-01  
> 依据：《MiMoTrust 受控内容沙盒跨系统协作文档》Context 2.1

## 固定标识

| 项目 | 固定值 |
|---|---|
| 沙盒 applicationId | `com.mimotrust.controlledcontent` |
| 守护者 applicationId | `com.mimotrust.guardian` |
| MethodChannel | `com.mimotrust.controlledcontent/context` |
| Broadcast Action | `com.mimotrust.intent.action.CONTENT_CONTEXT` |
| Intent Extra | `payload` |
| Context Schema | `2.1` |
| Manifest Schema | `1.0` |
| Provider ID | `mimotrust_sandbox` |
| Audience | `mimotrust_guardian_backend` |
| source_app | `mimotrust_controlled_content` |

Flutter 与 Kotlin 之间使用内部方法 `sendContentContext`，参数是单个已序列化的
Context 2.1 JSON 字符串。该方法只属于 App 内部桥接，不新增外部协议；Kotlin 不重组
Payload，直接使用上表固定的 Action、目标包和 Extra 发送。

不得引入第二套包名、Action、Extra、Schema 或字段语义。

## 固定行为

- 内容类型为 `video`、`audio`、`article`、`rich_article`、`image_gallery`；
- 只有打开评论面板时发送 `comment`，打开转发面板时发送 `share`；
- 浏览、播放、切页、页面停留、进入后台和恢复前台均不发送上下文；
- Payload 不包含评论正文、联系人、用户稳定标识、Cookie、长期凭据或媒体二进制；
- 广播为显式、单向、尽力交付，不提供业务 ACK；
- 守护者、网关或媒体不可用时，沙盒继续浏览和互动；
- 内容全部由开发者在 OSS 控制台手工上传，项目不提供任何上传能力。

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
