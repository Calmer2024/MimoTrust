# 小真 Android App

Kotlin + Jetpack Compose 核验客户端。

## 构建

```powershell
cd android

# 本地后端（模拟器默认 10.0.2.2:8000）
.\gradlew.bat assembleDebug

# 指定后端地址
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://47.94.58.72:8000/

# 云服务器
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://47.94.58.72:8000/
```

APK 输出：`app/build/outputs/apk/debug/app-debug.apk`

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
沙盒广播 → ControlledContentReceiver → 解析 Context 2.2
→ 用户点击悬浮球 → 发送 REQUEST_CONTENT_CONTEXT
→ 沙盒返回 grant → 兑换获取视频 URL → 创建核验任务
```

## 关键配置

| Gradle 属性 | 默认值 | 说明 |
|-------------|--------|------|
| `MIMO_API_BASE_URL` | `http://10.0.2.2:8000/` | 后端地址 |

## 权限

| 权限 | 用途 |
|------|------|
| `INTERNET` | 网络请求 |
| `POST_NOTIFICATIONS` | 核验进度通知 |
| `SYSTEM_ALERT_WINDOW` | 悬浮球 |
| `FOREGROUND_SERVICE` | 悬浮球前台服务 |
