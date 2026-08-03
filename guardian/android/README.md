# 小真 Android App

Kotlin + Jetpack Compose 核验客户端。

## 构建

```powershell
cd guardian\android

# 本地后端（真机通过 adb reverse 访问 127.0.0.1:8000）
.\gradlew.bat assembleDebug

adb reverse tcp:8000 tcp:8000

# 指定后端地址
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://47.94.58.72:8000/

# 云服务器
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://47.94.58.72:8000/
```

APK 输出：`app/build/outputs/apk/debug/app-debug.apk`

仓库统一交付目录为 `artifacts/apk/`；根目录构建与归档流程会将最终 APK 复制到该目录。

## 模块结构

```
app/src/main/java/com/mimotrust/xiaozhen/
├── ui/                          # Compose UI
│   ├── MimoTrustApp.kt          # 主界面（对话/历史/设置）
│   ├── MainViewModel.kt         # ViewModel
│   └── Theme.kt                 # 颜色与主题
├── data/                        # 数据层
│   ├── JobRepository.kt         # Job 管理 + SSE 监听 + 文件上传
│   ├── LocalAttachment.kt       # 本地附件模型
│   ├── remote/
│   │   ├── MimoApi.kt           # Retrofit API 接口
│   │   └── Dtos.kt              # 数据传输对象
│   └── local/
│       ├── JobEntity.kt         # Room 实体
│       ├── JobDao.kt            # Room DAO
│       └── MimoDatabase.kt      # 数据库
├── share/                       # 分享接收
│   ├── ShareReceiverActivity.kt # ACTION_SEND 处理
│   └── ShareEnqueueWorker.kt    # WorkManager 任务
├── overlay/                     # 悬浮球 + 受控内容
│   ├── FloatingBallService.kt   # 悬浮球前台服务
│   ├── FloatingBallManager.kt   # 悬浮球管理
│   ├── ControlledContentContract.kt  # Context 2.2 协议
│   ├── ControlledContentReceiver.kt  # 广播接收器
│   ├── ControlledContentEnqueueWorker.kt # 唯一可靠提交任务
│   ├── VideoContextReceiver.kt  # 视频上下文接收
│   └── CurrentVideoContextStore.kt   # 上下文存储
├── notification/                # 通知系统
│   └── VerificationNotifier.kt  # 核验进度/结果通知
├── MainActivity.kt              # 主 Activity
├── MimoTrustApplication.kt      # Application 初始化
└── DeviceIdentity.kt            # 设备标识
```

## 核心流程

### 分享接入

```
用户分享链接 → ShareReceiverActivity → ShareEnqueueWorker
→ JobRepository.createSharedJob() → POST /v1/jobs → SSE 监听
```

### 多模态输入

```
用户拍照/选图片/选视频 → LocalAttachment
→ JobRepository.createUploadJob() → POST /v1/jobs/upload → SSE 监听
```

### 受控内容（悬浮球）

```
comment/share → 沙盒发送 deferred_grant 候选
→ ControlledContentReceiver 校验并使悬浮球提示，不提交后端
→ 用户点击悬浮球 → 发送 REQUEST_CONTENT_CONTEXT
→ 沙盒返回 guardian_request + 新鲜 grant
→ Receiver 关联 request_id 并调度唯一 WorkManager
→ POST /v1/content-contexts
→ 后端兑换 grant、校验完整 Manifest
→ 视频/音频/文章/图文/图集进入统一核验任务与 SSE
```

## 关键配置

| Gradle 属性 | 默认值 | 说明 |
|-------------|--------|------|
| `MIMO_API_BASE_URL` | `http://127.0.0.1:8000/` | 后端地址；真机开发使用 `adb reverse` |

## 权限

| 权限 | 用途 |
|------|------|
| `INTERNET` | 网络请求 |
| `POST_NOTIFICATIONS` | 核验进度通知 |
| `SYSTEM_ALERT_WINDOW` | 悬浮球 |
| `FOREGROUND_SERVICE` | 悬浮球前台服务 |
