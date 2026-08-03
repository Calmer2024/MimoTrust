# APK 交付目录

本目录用于集中放置可安装的 Android Debug APK：

| 文件 | 模块 | applicationId |
|---|---|---|
| `mimotrust-guardian-debug.apk` | 小真守护者 App | `com.mimotrust.guardian` |
| `mimotrust-sandbox-debug.apk` | 受控内容沙盒 | `com.mimotrust.controlledcontent` |

## 安装

```powershell
adb install -r artifacts\apk\mimotrust-guardian-debug.apk
adb install -r artifacts\apk\mimotrust-sandbox-debug.apk
adb reverse tcp:8000 tcp:8000
```

## 完整性校验

```powershell
Get-FileHash artifacts\apk\*.apk -Algorithm SHA256
```

构建完成后以本目录的 `SHA256SUMS` 为准。

## Git 策略

APK 是构建产物，其中沙盒 Debug APK 超过 GitHub 单文件 100MB 限制，因此 `*.apk` 默认不提交到 Git。README 和 SHA-256 清单会被版本控制；APK 保留在本地交付目录。如需远程分发，应使用 GitHub Release、对象存储或先显式配置 Git LFS。
