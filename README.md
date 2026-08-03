# MiMoTrust 小真核验

> 让证据在传播之前到达，让判断仍然属于用户。

MiMoTrust 是面向碎片化、多模态内容的信息可信辅助工具。系统在用户授权后获取当前内容，使用 MiMo 理解主张与叙事，通过检索和证据关系判断生成可追溯报告；证据不足时明确说明，不依靠模型自身知识替用户下结论。

## 已完成闭环

```text
受控内容沙盒
  -> Context 2.2 + 一次性 grant
  -> 小真守护者 App
  -> FastAPI 后端
  -> Manifest / 资源 / SHA-256 校验
  -> MiMo 多模态理解
  -> Exa 检索与证据处理
  -> App 展示核验结果
```

沙盒支持 `video`、`audio`、`article`、`rich_article`、`image_gallery`。普通浏览不发送上下文；打开评论或转发面板只触发非打断提示；用户点击悬浮球后，守护者主动请求当前内容并开始核验。

## 仓库结构

```text
mimotrust/
├── guardian/
│   └── android/                 # 小真守护者 Android App（Kotlin / Compose）
├── backend/
│   ├── app/                     # FastAPI 服务与 M1-M7 核验流水线
│   ├── tests/                   # 后端及跨模块契约测试
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── docker-compose.yml
├── sandbox/
│   ├── mimotrust_controlled_content/ # 受控内容 Flutter App
│   ├── content_gateway/         # 内容网关与 grant 兑换
│   ├── content_admin/           # 多类型内容管理平台
│   └── content_registry/        # Manifest、注册表与演示资源
├── artifacts/
│   └── apk/                     # APK 本地交付目录、哈希与安装说明
├── contracts/                   # Context 2.2 / Manifest 1.0 JSON Schema
├── docs/                        # 当前产品与工程文档
└── doc/                         # 沙盒冻结规格、协作文档和历史交付材料
```

各模块说明：[后端](backend/README.md) · [守护者 Android App](guardian/android/README.md) · [受控内容沙盒](sandbox/README.md) · [APK 交付](artifacts/apk/README.md)

## 环境要求

- Python 3.10+（建议 3.12）
- Android Studio / Android SDK / JDK 17
- Flutter SDK
- 已连接 Android 真机时需可用的 `adb`

## 快速启动

### 1. 后端

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
Copy-Item backend\.env.example backend\.env
# 在 backend/.env 中填写 MIMO_API_KEY、EXA_API_KEY 等配置
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：`http://127.0.0.1:8000/api/health`，API 文档：`http://127.0.0.1:8000/api/docs`。

### 2. 守护者 App

```powershell
Set-Location guardian\android
.\gradlew.bat assembleDebug
adb reverse tcp:8000 tcp:8000
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

如需直连远端后端：

```powershell
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://47.94.58.72:8000/
```

### 3. 受控内容沙盒

```powershell
Set-Location sandbox\mimotrust_controlled_content
flutter pub get
flutter run --dart-define-from-file=config/cloud-debug.json
```

当前云端内容网关为 `http://47.94.58.72:8787`，具体配置以 `config/cloud-debug.json` 为准。

## 验证

```powershell
# 后端及跨模块契约
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q

# 守护者
Set-Location ..\guardian\android
.\gradlew.bat testDebugUnitTest assembleDebug

# 沙盒
Set-Location ..\..\sandbox\mimotrust_controlled_content
flutter test
flutter build apk --debug --dart-define-from-file=config/cloud-debug.json

# JSON Schema 与样例
Set-Location ..\..
.\.venv\Scripts\python.exe sandbox\tools\validate_contracts.py
```

## 协议基线

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

## 安全边界

- 只处理公开且用户有权访问的内容，不绕过 DRM、登录或付费限制。
- 沙盒不调用 MiMo、不判断真假、不展示核验报告，只展示内容并在授权后传递上下文。
- comment/share 候选消息不携带 grant；grant 仅响应守护者主动请求，短时有效且只能兑换一次。
- 不传评论正文、联系人、Cookie、长期凭据或媒体二进制。
- 网关、媒体、守护者或后端不可用时，各端应可恢复且不得崩溃。
- `.env`、运行数据、构建缓存和 APK 二进制不进入 Git。

## 文档索引

- [规划书](docs/规划书.md)
- [后端说明](docs/后端说明.md)
- [接口文档](docs/接口文档.md)
- [小真 App 说明](docs/小真App说明.md)
- [沙盒说明](docs/沙盒说明.md)
- [跨系统协作基线](doc/MiMoTrust受控内容沙盒当前协作基线.md)
- [冻结规格](doc/MiMoTrust受控内容沙盒冻结规格.md)

本项目为 2026 小米集团黑客马拉松参赛作品。
