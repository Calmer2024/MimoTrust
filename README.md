# 信源守护者 — MiMo Trust

> **面向短视频时代的多模态信源核验 Agent**
> 基于 Xiaomi MiMo-V2.5 · 2026 小米集团黑客马拉松·高校赛区
>
> 让证据在传播之前到达，让判断仍然属于用户。

---

## 项目简介

短视频、截图和片段化文字降低了信息传播门槛，也让来源丢失、旧闻新炒和情绪化暗示更难识别。**信源守护者**不是事后辟谣工具，而是一项**传播前的证据辅助能力**：用户无需离开当前页面，系统在后台完成内容理解、信源检索和证据比对，在评论或转发前提供可追溯、可复查的证据路径。

**核心原则**：不拦截、不说教、不替用户判断。

### 核心闭环

```
当前内容上下文 → 自动理解与检索 → 场景内轻提示 → 按需展开证据 → 用户自主判断
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户场景                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ 受控内容沙盒  │    │  小真 App     │    │  Web 前端     │   │
│  │ (Flutter)    │───→│  (Kotlin)    │    │  (HTML/JS)   │   │
│  │ 视频浏览/互动 │    │  分享/悬浮球  │    │  链接输入     │   │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘   │
│         │                   │                    │           │
│         └── 广播/分享 ──────┘                    │           │
└─────────────────────────────────────────────────┼───────────┘
                                                  │
                    ┌─────────────────────────────▼───────────┐
                    │            后端核验服务 (FastAPI)         │
                    │                                         │
                    │  ┌─────────────────────────────────┐    │
                    │  │     M1-M7 模块化核验流水线        │    │
                    │  │  M1 规范化 → M2 规划 → M3 检索   │    │
                    │  │  → M4 归一化 → M5 初筛           │    │
                    │  │  → M6 研判 → M7 报告             │    │
                    │  └────────────┬────────────────────┘    │
                    │               │                          │
                    │    ┌──────────┴──────────┐              │
                    │    │                     │              │
                    │    ▼                     ▼              │
                    │  MiMo-V2.5           Exa 搜索           │
                    │  (全模态理解)        (信源检索)           │
                    └─────────────────────────────────────────┘
```

---

## 三大组件

### 1. 受控内容沙盒 (`sandbox/`)

Flutter Android 应用，模拟短视频平台的浏览与互动场景，用于演示"浏览→评论/转发→自动核验"的完整闭环。

- 用户浏览视频时，沙盒维护当前内容状态
- 打开评论或转发面板时，通过广播通知小真 App
- 用户点击悬浮球后，沙盒签发一次性 grant，App 兑换获取视频 URL
- 完整协议：Context 2.2 + Manifest 1.0 + grant 兑换 + SHA-256 校验

### 2. 小真 Android App (`android/`)

Kotlin + Jetpack Compose 核验客户端。

- **对话式核验**：输入文字/图片/视频，发起后台核验
- **分享接入**：接收系统分享的链接和文件
- **悬浮球**：刷视频时悬浮常驻，点击即可核验当前内容
- **实时进度**：SSE 事件流驱动，9 阶段逐步展示
- **结构化报告**：综合判定、逐项核验、叙事分析、关键依据、待补证据
- **小真表情系统**：9 种角色表情随核验结果动态切换，增强情感反馈

### 3. 后端核验服务 (`app/`)

Python + FastAPI，承载 M1-M7 核验流水线。

- **M1 输入规范化**：严格校验，为主张分配稳定编号
- **M2 检索规划**：MiMo 为每条主张生成中性检索计划
- **M3 并发检索**：Exa 并发执行，单项超时不阻塞其他
- **M4 证据归一化**：纯程序清洗、去重，建立统一证据池
- **M5 证据初筛**：MiMo Pro 并发判断证据与主张的关系
- **M6 综合研判**：MiMo Pro 交叉核验，识别循环引用和证据缺口
- **M7 报告渲染**：程序验证并渲染完整 JSON/Markdown

---

## 支持的输入

| 输入类型 | 说明 |
|---------|------|
| 平台 URL | 抖音、B站、YouTube、快手、微博、小红书、视频号 |
| 分享口令 | 从分享文案中自动提取 URL 并展开短链 |
| 纯文字 | 直接交给 LLM 提取主张并核验 |
| 多模态上传 | 图片（OCR）+ 视频（ASR+画面）+ 音频（ASR）+ 文字 |
| 受控内容 | 沙盒广播 → grant 兑换 → 自动获取视频 URL |

---

## 快速启动

### 后端（本地开发）

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# 填写 MIMO_API_KEY 和 EXA_API_KEY
uvicorn app.main:app --reload
```

打开 http://127.0.0.1:8000 · API 文档 http://127.0.0.1:8000/api/docs

### 后端（云服务器）

```bash
ssh mimo "bash /srv/mimotrust/deploy.sh"
```

公网地址：http://47.94.58.72:8000

### Android App

```powershell
cd android
# 本地后端
.\gradlew.bat assembleDebug
# 云服务器
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://47.94.58.72:8000/
```

APK 位于 `android/app/build/outputs/apk/debug/app-debug.apk`

### 受控内容沙盒

```bash
cd sandbox/mimotrust_controlled_content
flutter run
```

内容网关（已部署在云服务器 8787 端口，本地也可启动）：

```bash
python -m sandbox.content_gateway.server --host 127.0.0.1 --port 8787
```

---

## API 接口

### Web 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 全链路核验（内容提取 + 信源核实） |
| POST | `/api/analyze/stream` | 全链路 SSE 版本 |
| POST | `/api/analyze/upload` | 多模态文件上传核验 |
| POST | `/api/verify` | 对已有主张 JSON 单独核验 |
| GET | `/api/health` | 健康检查 |

### 移动端 Job 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/jobs` | 创建核验任务（链接/文字） |
| POST | `/v1/jobs/upload` | 创建核验任务（多模态文件） |
| GET | `/v1/jobs/{id}/events` | SSE 阶段事件流 |
| GET | `/v1/jobs/{id}/result` | 读取核验结果 |
| POST | `/v1/jobs/{id}/cancel` | 取消任务 |

### 受控内容接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/controlled-content/exchange` | 沙盒 grant 兑换代理 |

---

## 核验报告结构

每次核验生成的报告包含：

- **综合判定**：属实 / 部分属实 / 误导 / 证据不足 / 无需核验
- **逐项核验**：每条主张的判定、依据、不确定性
- **叙事分析**：内容是否使用情绪引导、反问暗示等手法
- **关键依据**：可点击跳转的原始来源
- **待补证据**：系统未能找到但仍需要的信息
- **传播建议**：基于证据状态的中立建议

## 小真表情系统

App 内置 9 种角色表情，根据核验结果动态切换，增强情感反馈：

| 表情 | 触发条件 |
|------|---------|
| `happy` | 核验通过、内容可信 |
| `core_supported` | 核心主张有证据支持 |
| `confused` | 内容复杂、难以判断 |
| `speechless` | 无话可说、内容荒谬 |
| `disappointed` | 内容不实、令人失望 |
| `key_mismatch` | 关键信息存在矛盾 |
| `partial_mismatch` | 部分内容有差异 |
| `misleading_expression` | 表达存在误导 |
| `insufficient_evidence` | 证据不足无法判断 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 沙盒 App | Flutter + Dart |
| Android App | Kotlin + Jetpack Compose + Room + Retrofit + WorkManager |
| 后端 | Python 3.12 + FastAPI + Uvicorn |
| 核验引擎 | MiMo-V2.5 / MiMo-V2.5-Pro + Exa Search |
| 内容提取 | Playwright + yt-dlp + httpx + BeautifulSoup |
| 部署 | 阿里云 ECS + systemd + Nginx |

---

## 项目结构

```
MimoTrust/
├── app/                          # 后端核验服务
│   ├── main.py                   # FastAPI 入口
│   ├── pipeline.py               # 内容提取管线
│   ├── content.py                # 文章/上传内容解析
│   ├── mimo.py                   # MiMo API 调用
│   ├── config.py                 # 配置管理
│   ├── controlled_content.py     # 受控内容 grant 兑换代理
│   ├── jobs/                     # 异步 Job 系统
│   │   ├── api.py                # Job REST 接口
│   │   ├── worker.py             # Job 处理逻辑
│   │   ├── uploads.py            # 文件上传处理
│   │   └── models.py             # 数据模型
│   └── trust/                    # 核验流水线
│       ├── service.py            # 核验服务入口
│       └── pipeline_v2/          # M1-M7 模块化实现
│           ├── planning.py       # M2 检索规划
│           ├── retrieval.py      # M3 并发检索
│           ├── evidence.py       # M4 证据归一化
│           ├── evidence_triage.py# M5 证据初筛
│           ├── synthesis.py      # M6 综合研判
│           └── rendering.py      # M7 报告渲染
├── android/                      # 小真 Android App
│   └── app/src/main/java/com/mimotrust/xiaozhen/
│       ├── ui/                   # Compose UI
│       ├── data/                 # 数据层（Repository, API, Room）
│       ├── share/                # 分享接收
│       ├── overlay/              # 悬浮球 + 受控内容接收
│       └── notification/         # 通知系统
├── sandbox/                      # 受控内容沙盒
│   ├── mimotrust_controlled_content/  # Flutter App
│   ├── content_gateway/          # Python 内容网关
│   └── content_registry/         # 静态内容注册表
├── tests/                        # 测试用例
├── docs/                         # 详细文档
└── docker-compose.yml            # 生产部署配置
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [规划书](docs/规划书.md) | 完整作品规划：需求洞察、产品设计、技术方案、商业价值 |
| [模块化核验流水线升级说明](docs/模块化核验流水线升级说明.md) | M1-M7 数据协议、阶段输入输出、SSE 规范 |
| [小真 App 实现说明](docs/小真App实现说明.md) | Android 模块、接口示例、生产部署 |
| [受控内容沙盒实施合同](sandbox/IMPLEMENTATION_CONTRACT.md) | Context 2.2 协议、固定标识与行为 |
| [真机验收记录](sandbox/DEVICE_VERIFICATION.md) | 端到端真机验证结果 |
| [云服务器部署方案](docs/云服务器部署方案.md) | 阿里云 ECS 部署步骤与运维 |
| [受控内容沙盒接入指南](docs/假抖音平台接入指南.md) | 沙盒平台对接说明 |
| [路演 PPT 内容方案](docs/路演PPT内容方案.md) | 5 分钟路演结构、文案、答辩准备 |

---

## 边界与约束

- 仅处理公开且用户有权访问的内容，不绕过 DRM、登录或付费限制
- `隐含` 主张是内容实际形成的叙事引导，不是系统认可的事实，同样接受证据核验
- 证据不足时返回"暂无法确认"，不靠模型知识补全
- 所有报告固定展示能力边界声明

---

## 许可证

本项目为 2026 小米集团黑客马拉松参赛作品。
