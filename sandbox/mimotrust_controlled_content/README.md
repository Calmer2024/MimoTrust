# MiMoTrust 受控内容 Android App

Flutter 3.44.2 / Dart 3.12.2 创建的全新 Android 工程。

当前阶段实现：

- 固定 applicationId：`com.mimotrust.controlledcontent`；
- 从打包的 `registry.json` 按 `display_order` 加载三条视频 Manifest；
- 校验 Manifest 1.0、Provider、内容身份和分析资源哈希；
- 显示固定封面、标题、作者和发布日期；
- 网络 MP4 自动播放、循环、点击暂停/继续、静音和进度拖动；
- 使用竖向 Feed 切换视频，只有当前页播放；
- App 进入后台时暂停，恢复后按原状态继续；
- 点赞状态使用 `shared_preferences` 按内容 ID 和版本持久化；
- 评论面板展示预置评论，新增评论仅保存在本机并在重启后保留；
- 转发面板只使用固定虚拟联系人，不读取系统联系人、不启动真实分享；
- 互动栏显示每条视频独立的点赞、评论和转发数量；
- 点赞数叠加持久化点赞状态，评论数叠加本地评论，转发数叠加本次运行的模拟转发；
- 打开评论或转发面板时暂停视频，关闭后按打开前状态恢复；
- 打开评论/转发面板时冻结当前播放位置并通过统一入口准备 Context 2.1；
- 向最小内容网关申请绑定 `mimotrust_guardian_backend` 的一次性 grant；
- 校验网关返回的内容 ID、版本、SHA-256、canonical URL、audience 和 scopes；
- 网关不可用或响应不合法时只记录脱敏错误，不阻塞原面板；
- 通过固定 MethodChannel `com.mimotrust.controlledcontent/context` 将单个
  Context 2.1 JSON 字符串交给 Kotlin；
- Kotlin 校验非空和 32 KB 上限后，使用固定 Action、目标包和 Extra 发送显式广播；
- 发送日志只记录 `event_id`、内容类型和触发类型，不记录完整 Payload 或 grant；
- 守护者未安装或平台桥接失败时不阻塞评论、转发和其他本地互动；
- 内容清单或媒体失败时显示重试状态。

内部 MethodChannel 方法名为 `sendContentContext`，它不是跨 App 协议的一部分。
`CONTENT_CONTEXT_SEND` 只表示 Android 已执行尽力发送，不表示守护者已接收或创建任务。
点赞、提交本地评论和完成模拟转发均不准备或发送上下文。

Debug 真机联调默认使用 `http://127.0.0.1:8787`，需要先启动网关并转发端口：

```powershell
python -m sandbox.content_gateway.server --host 127.0.0.1 --port 8787
adb reverse tcp:8787 tcp:8787
```

可在构建时通过 `--dart-define=MIMOTRUST_GATEWAY_URL=...` 覆盖开发网关地址。
明文 HTTP 仅在 `android/app/src/debug/AndroidManifest.xml` 中启用。

## 验证

```powershell
flutter pub get
dart analyze
flutter test
flutter build apk --debug
```

Debug APK：

```text
build/app/outputs/flutter-apk/app-debug.apk
```

最新真机验收结果见 `../DEVICE_VERIFICATION.md`。

工程位于 D 盘而 Pub Cache 位于 C 盘，因此通过 `android/gradle.properties` 关闭 Kotlin
增量编译，避免 Kotlin 缓存的跨盘 `different roots` 错误。
