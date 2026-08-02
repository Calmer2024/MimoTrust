# 受控短视频 App 演示沙盒快速交付说明

> **历史资料提示（2026-08-01）：** 本文保留用于理解最早的视频原型和工程排错，其中 `com.sourcecheckcheck.*`、`VIDEO_CONTEXT`、仅视频的 Payload 及停留 1.5 秒触发均已被后续跨系统方案取代，不得用于新工程。当前实施范围、品牌和接口以《MiMoTrust 守护者 App 跨系统协作文档》与《MiMoTrust 受控内容沙盒冻结规格》为准；新工程统一使用 `mimotrust` 技术标识。

> 目标：从零开始，用最少时间完成一个可安装、可演示、可完整测试的 Android 短视频沙盒。  
> 原则：不继承现有实现，不产品化，不承担信源核查，只服务于双 App 演示闭环。

本文档目标是回答以下问题：

1. 从零开始时，采用 Flutter 还是原生 Android 才能更快完成；
2. 新项目需要提前准备什么，第一步如何创建；
3. 最少需要哪些页面、文件、模型和依赖；
4. 演示视频、评论、点赞和转发信息放在哪里；
5. 打开评论和打开转发如何通知信源守护者；
6. 如何在 Android 真机上安装、捕获广播并完成全流程验收；
7. 哪些功能明确不做，遇到问题时如何快速降级；
8. 做到什么程度必须停止继续投入并冻结交付物。

---

## 一、项目定位与完成定义

短视频 App 只是一个团队可控的演示环境，用来稳定复现以下链路：

```text
用户观看视频
  -> 打开评论 / 打开转发
  -> 短视频 App 发送当前视频 URL 和元数据
  -> 信源守护者 App 接收
  -> 信源守护者独立进行后续分析
```

新 App 满足以下九项即可视为完成：

1. Debug APK 能安装并运行在目标 Android 真机；
2. 至少三条开发者准备的视频能够播放和上下切换；
3. 当前视频自动播放，离开页面后停止播放；
4. 点赞、评论和模拟转发能够操作；
5. 打开评论面板发送 `comment`；
6. 打开转发面板发送 `share`；
7. 普通播放和停留不自动发送上下文；
8. 信源守护者能收到包含正确 `video_url` 的广播；
9. 信源守护者不存在或接收失败时，短视频 App 仍能正常使用。

九项通过后立即冻结，不继续扩展短视频产品能力。

---

## 二、技术选择

### 2.1 本次默认选择

```text
Flutter + Dart：页面、视频 Feed 和互动
Kotlin：MethodChannel 和 Android 显式广播
OSS：演示视频公网 URL
shared_preferences：本地点赞和评论
```

### 2.2 为什么从零仍推荐 Flutter

- 当前开发环境已经具备 Flutter、Dart 和 Android SDK；
- `PageView` 可以快速完成竖向视频 Feed；
- `video_player` 可以直接播放网络 MP4；
- 评论和分享面板使用 Flutter BottomSheet 即可完成；
- Hot Reload 适合快速调整演示 UI；
- 可以先在 Web 上检查布局，再进行一次 Android 真机收口；
- Android 特有部分只有广播，Kotlin 代码量很小。

选择 Flutter 是为了压缩沙盒 UI 的开发时间，不是为了建设跨平台正式产品。

### 2.3 什么时候改用原生 Android

只有满足以下任一条件时才改用 Kotlin + Jetpack Compose：

- 团队成员明显更熟悉 Compose 和 Media3；
- 最终只允许提交原生 Android 工程；
- 必须深度使用系统服务、前台服务或 HyperOS 专有接口；
- Flutter 播放器在目标真机上出现无法绕过的兼容问题。

不要同时开发 Flutter 和 Compose 两套 App。项目开始后 60 分钟内完成技术路线确认，之后不再切换。

### 2.4 原生 Android 对应范式

若被迫使用原生方案，保持最小结构：

```text
Jetpack Compose UI
  -> ViewModel + StateFlow
  -> Repository
  -> Media3 ExoPlayer / DataStore

ContextDispatcher
  -> 显式 Broadcast Intent
```

原生方案不需要 MethodChannel，但 UI、播放器生命周期和本地互动仍需要重新实现。

---

## 三、开始前准备

### 3.1 必备软件

- Flutter SDK；
- Android Studio；
- Android SDK Platform、Build Tools 和 Platform Tools；
- Android Studio 自带 JBR；
- 一台开启 USB 调试的 Android 真机；
- 三个可公网访问的 HTTPS MP4 URL；
- 信源守护者 App 的包名和广播协议。

### 3.2 环境检查

```powershell
flutter --version
dart --version
flutter doctor -v
adb version
adb devices -l
```

开始编码前必须确保 `flutter doctor -v` 没有阻断 Android 构建的问题。手机暂时未连接不阻塞 UI 开发，但最终验收必须使用真机。

### 3.3 磁盘和网络

- Flutter Android 首次构建预留至少 15 GB；
- 项目、Pub Cache 和构建目录尽量位于同一磁盘；
- 国内网络提前配置可信的 Gradle、Maven 和 Flutter 制品镜像；
- 不要同时启动多个 `flutter run` 或 `assembleDebug`；
- 不要等到最终验收时才首次下载 NDK、CMake 和 SDK Platform。

---

## 四、从零创建项目

### 4.1 创建命令

在目标父目录执行：

```powershell
flutter create --platforms android --org com.sourcecheckcheck controlledvideo
cd controlledvideo
```

该命令生成的目标 applicationId 为：

```text
com.sourcecheckcheck.controlledvideo
```

applicationId、Kotlin `namespace` 和 `MainActivity.kt` 的 package 必须一致。创建后不要再临时修改包名。

### 4.2 最小依赖

`pubspec.yaml` 只增加：

```yaml
dependencies:
  flutter:
    sdk: flutter
  video_player: ^2.13.0
  shared_preferences: ^2.5.5
```

然后执行：

```powershell
flutter pub get
```

不要加入状态管理框架、数据库、路由框架、网络框架和代码生成工具。沙盒规模不需要这些依赖。

### 4.3 Android 网络权限

在 `android/app/src/main/AndroidManifest.xml` 的 `<manifest>` 下、`<application>` 外加入：

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

不要把 `uses-permission` 放进 `<application>`。

---

## 五、最小工程结构

从零创建后，只需要补充以下文件：

```text
lib/
  main.dart
  models/
    video_item.dart
  pages/
    video_feed_page.dart
  widgets/
    video_player_item.dart
    comments_sheet.dart
    share_sheet.dart
  services/
    video_repository.dart
    local_store.dart
    context_dispatcher.dart

assets/
  data/
    videos.json
  images/
    cover_1.jpg
    cover_2.jpg
    cover_3.jpg

android/app/src/main/kotlin/com/sourcecheckcheck/controlledvideo/
  MainActivity.kt

test/
  video_item_test.dart
```

不要为了目录整洁增加 Controller、UseCase、DI、EventBus 和多层 Repository。单个 Feed 页面允许直接管理少量演示状态。

---

## 六、演示数据与存储

### 6.1 视频

开发者提前把三条 MP4 上传到 OSS。短视频 App 不提供上传页面，只在 `assets/data/videos.json` 中配置 URL 和元数据。

```json
[
  {
    "id": "video-001",
    "title": "演示视频一",
    "description": "用于完整链路测试",
    "author": "开发者",
    "published_at": "2026-07-31T00:00:00+08:00",
    "video_url": "https://example.com/video-001.mp4",
    "cover_asset": "assets/images/cover_1.jpg",
    "content_hash": "sha256-hex",
    "duration_ms": 20000,
    "like_count": 100,
    "comments": []
  }
]
```

视频 URL 必须满足：HTTPS、无需 Cookie、支持模型后端访问、有效期覆盖完整演示。建议使用 MP4/H.264/AAC。

### 6.2 本地互动

| 数据 | 本次存储方式 |
|---|---|
| 视频文件 | OSS 公网 URL |
| 视频清单 | Flutter asset JSON |
| 封面 | Flutter assets |
| 预置评论 | `videos.json` |
| 新增评论 | `shared_preferences` |
| 点赞状态 | `shared_preferences` |
| 分享记录 | 不持久化，只显示成功提示 |
| 播放位置 | 内存 Map |

本次不配置数据库。删除 App 后本地评论和点赞丢失是可接受行为。

### 6.3 内容哈希

开发者上传视频后计算一次 SHA-256，并写入 JSON。视频内容变化时同步修改 ID 版本或哈希。不要把带签名参数的 URL 当作内容唯一标识。

---

## 七、最小功能实现顺序

严格按以下顺序开发；前一步不能运行时，不进入下一步。

### 7.1 第一步：静态视频 Feed

- 从 `videos.json` 解析三条视频；
- 使用纵向 `PageView.builder`；
- 先展示封面、标题和作者；
- 完成加载、失败和空数据状态。

验收：三页可以上下切换，数据与 JSON 一致。

### 7.2 第二步：播放器

- 每个页面使用 `VideoPlayerController.networkUrl`；
- 仅当前页面播放；
- 设置循环播放；
- 页面切换时暂停旧视频；
- 页面销毁时释放 Controller；
- 增加加载指示和重试。

验收：三条视频可播放，快速切页不崩溃，不出现多个视频同时播放。

### 7.3 第三步：本地互动

- 点赞按钮切换状态并保存；
- 评论 BottomSheet 展示预置和本地评论；
- 评论输入只保存在本机；
- 分享 BottomSheet 使用固定虚拟联系人；
- 不接系统联系人，不接真实分享 SDK。

验收：重启 App 后点赞和本地评论仍存在。

### 7.4 第四步：统一上下文

建立唯一方法：

```dart
sendVideoContext(trigger, currentVideo, currentPosition)
```

两个触发点只能调用该方法，不得分别拼装两套 JSON。

### 7.5 第五步：绑定评论与转发入口

```text
用户打开评论或转发面板
  -> 读取当前页面内容 ID、URL 和播放位置
  -> 调用统一上下文方法
  -> 立即打开原面板，不等待守护者响应
```

普通播放、停留、切页、进入后台和恢复前台均不自动发送上下文。不要实现停留计时器。

### 7.6 第六步：Android 广播

- Flutter 使用 MethodChannel 调用 Kotlin；
- Kotlin 将 Map 转为 JSON；
- Intent 设置固定 Action；
- `setPackage` 指向信源守护者；
- Extra 名称固定为 `payload`；
- 发送失败只写日志，不阻塞 UI。

### 7.7 第七步：真机收口

- 先构建和安装短视频 App；
- 再安装带 Receiver 的信源守护者 App；
- 用 Logcat 观察发送和接收；
- 只修阻断演示的问题。

---

## 八、广播协议

### 8.1 固定标识符

| 项目 | 值 |
|---|---|
| 短视频包名 | `com.sourcecheckcheck.controlledvideo` |
| 守护者包名 | `com.sourcecheckcheck.guardian` |
| MethodChannel | `com.sourcecheckcheck.controlledvideo/context` |
| Action | `com.sourcecheckcheck.controlledvideo.VIDEO_CONTEXT` |
| Extra | `payload` |

### 8.2 最小 payload

```json
{
  "schema_version": "1.0",
  "trigger": "comment",
  "source_app": "controlled_video_app",
  "content_id": "video-001",
  "content_version": "v1",
  "content_hash": "sha256-hex",
  "video_url": "https://example.com/video-001.mp4",
  "title": "演示视频一",
  "author": "开发者",
  "published_at": "2026-07-31T00:00:00+08:00",
  "position_ms": 3500,
  "duration_ms": 20000,
  "observed_at": "2026-07-31T10:00:00+08:00"
}
```

`trigger` 只允许：

- `comment`：用户打开评论面板；
- `share`：用户打开转发面板。

`comment` 不表示评论已经发布，`share` 不表示分享已经完成。

### 8.3 Android 11 包可见性

发送端 Manifest 的 `<queries>` 内加入：

```xml
<package android:name="com.sourcecheckcheck.guardian" />
```

这样 `queryBroadcastReceivers()` 才能更可靠地返回目标接收器数量。

### 8.4 接收端

守护者 App 注册 exported Receiver，收到后只做三件事：

1. 检查 Action；
2. 读取并打印 `payload`；
3. 交给守护者自己的任务逻辑。

Receiver 中不要直接下载视频或调用模型。

---

## 九、从零开发时间盒

| 阶段 | 最长投入 | 退出条件 |
|---|---:|---|
| 环境检查和创建项目 | 45 分钟 | 空项目可在 Web/Android 启动 |
| JSON 和静态 Feed | 60 分钟 | 三页可上下切换 |
| 网络视频播放 | 120 分钟 | 三条视频可播放且只播放当前项 |
| 点赞、评论、模拟转发 | 90 分钟 | 三个交互可操作 |
| 上下文模型和两种触发 | 45 分钟 | Dart 日志正确，普通停留无事件 |
| Kotlin 广播桥接 | 60 分钟 | 发送端 Logcat 有完整 payload |
| 守护者 Receiver 联调 | 60 分钟 | 接收端打印相同 payload |
| 真机回归和阻断修复 | 120 分钟 | 九项完成标准通过 |
| 录屏和归档 | 45 分钟 | APK、日志、录屏已保存 |

总时间控制在 10-12 小时。超过时间盒时优先降级，不重构、不换框架。

---

## 十、明确不做

- 不继承或迁移已有 App 代码；
- 不开发视频上传管理页面；
- 不开发短视频后端；
- 不配置 PostgreSQL、Redis 或消息队列；
- 不实现用户注册和登录；
- 不实现真实评论服务器；
- 不实现关注、推荐、私信和真实社交；
- 不读取系统联系人；
- 不实现 iOS 版本；
- 不实现 HLS、多码率和 CDN 调度；
- 不在短视频 App 中显示核验结果；
- 不建设事件总线、Clean Architecture 或复杂状态管理；
- 不为沙盒搭建完整 CI/CD；
- 不做应用商店 Release 发布。

新需求只有直接影响九项完成标准时才进入开发。

---

## 十一、真机测试流程

### 11.1 连接

```powershell
adb devices -l
```

必须显示 `device`。`unauthorized` 时解锁手机并同意 USB 调试授权。

### 11.2 构建与安装

```powershell
flutter build apk --debug
adb install -r build\app\outputs\flutter-apk\app-debug.apk
adb shell am start -n com.sourcecheckcheck.controlledvideo/.MainActivity
```

### 11.3 捕获日志

```powershell
adb logcat -c
adb logcat -v time -s ControlledVideo:I GuardianReceiver:I flutter:I *:S
```

预期看到：

```text
ControlledVideo: VIDEO_CONTEXT_SEND ... payload={...}
GuardianReceiver: VIDEO_CONTEXT_RECEIVED payload={...}
```

ADB 不能直接监听任意广播，必须由守护者 Receiver 接收后写入 Logcat。

### 11.4 验收顺序

1. 第一条视频持续播放，确认普通停留不发送上下文；
2. 打开评论，验证 `comment`；
3. 打开转发，验证 `share`；
4. 切换第二、第三条视频，验证 ID 和 URL 跟随变化；
5. 快速切页，确认切页本身不发送上下文；
6. App 进入后台和恢复前台，确认不产生自动事件；
7. 停止守护者，确认短视频 App 不崩溃；
8. 重新启动守护者，完成最终录屏。

---

## 十二、只修阻断性问题

必须修：

- App 无法创建、构建、安装或启动；
- 三条视频全部无法播放；
- 上下切换失效；
- 评论或转发导致崩溃；
- `comment/share` 未发送，或普通停留错误发送上下文；
- payload 对应了错误视频；
- 守护者无法接收广播；
- 稳定复现的红屏、黑屏或卡死。

不阻塞：

- Debug APK 较大；
- 没有真实账号、数据库和云端评论；
- 分享对象是虚拟联系人；
- UI 不等同商业短视频 App；
- 没有上传管理端、推荐算法和 Release AAB；
- 没有 iOS 版本。

---

## 十三、常见问题与快速处理

| 问题 | 快速处理 |
|---|---|
| `adb unauthorized` | 手机确认 RSA；撤销 USB 调试授权后重连 |
| 一直 `assembleDebug` | 检查首次依赖下载、旧 Gradle 进程和磁盘空间 |
| Gradle TLS 失败 | 配置可信国内镜像，不只修改 Gradle zip |
| Kotlin different roots | 项目和 Pub Cache 放同盘，或关闭 Kotlin 增量编译 |
| Android 视频黑屏 | 检查 HTTPS、编码、Range 和真机解码支持 |
| Web 能播而真机不能播 | 重新检查 Android 网络和媒体编码，不能用 Web 结论替代 |
| 评论关闭时断言 | Controller 由 BottomSheet 自己持有和销毁 |
| 评论 List 无法追加 | 不使用 fixed-length List，采用不可变替换 |
| `receivers=0` | 检查守护者包名、Receiver、安装状态和 `<queries>` |
| 守护者收到但没有分析 | 问题属于守护者任务链，不修改短视频 App |

---

## 十四、降级策略

| 问题 | 降级方案 |
|---|---|
| Flutter 真机热调试不稳定 | 构建 APK 后使用 `adb install -r` |
| 某条视频编码不兼容 | 替换为已验证的 MP4/H.264 |
| OSS 不稳定 | 使用稳定公共 HTTPS URL；必要时打包一条本地兜底视频 |
| 真实评论来不及 | 使用预置评论和本地新增评论 |
| 系统分享来不及 | 使用固定虚拟联系人面板 |
| Receiver 来不及接分析后端 | Receiver 只打印 JSON，先证明跨 App 链路 |
| 守护者分析时间过长 | 使用守护者缓存或预置结果，不修改短视频 App |
| UI 打磨超时 | 保证控件可用和不遮挡，停止视觉扩展 |

---

## 十五、冻结与交付

九项完成标准通过后立即执行：

1. 不再重构或更换技术栈；
2. 不再升级 Flutter、Gradle 和播放器依赖；
3. 固定三个视频 ID、URL 和哈希；
4. 固定 applicationId、Action、Extra 和 Schema 1.0；
5. 保存可安装 Debug APK；
6. 记录 APK SHA-256；
7. 保存一份三种 trigger 的发送和接收日志；
8. 保存最终演示录屏；
9. 后续精力全部转向信源守护者和核验主链。

交付物只有：

```text
短视频 App 源码
Debug APK
三条演示视频配置
广播协议说明
真机测试日志
演示录屏
```

---

## 十六、结论

最终短视频 App 需要从零创建，但仍然只是一套演示沙盒。最稳妥的路线是使用 Flutter 快速完成视频和交互，用少量 Kotlin 完成广播；视频由开发者提前上传 OSS，互动只保存在本机，不建设后端和数据库。

工程重点不是代码复用，而是尽早冻结接口和完成顺序：先播放，再互动，再上下文，再广播，最后真机验收。九项完成标准通过后立即停止投入。
