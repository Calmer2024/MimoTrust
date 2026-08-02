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
