# MiMo Trust 全链路信源核实 Demo

> 当前仓库同时包含“小真核验”Android MVP：Kotlin + Jetpack Compose + Room + Retrofit/OkHttp，入口位于 [`android/`](android/)。移动端通过异步 Job API 发起后台核验，前台用 SSE 接收阶段更新，通知层为小米超级岛/焦点通知保留经审批后的适配边界，并始终提供普通 Android 通知兜底。

输入文章 URL，或快手、微博、小红书、视频号、抖音、哔哩哔哩、YouTube 的公开内容链接/手机分享文案；没有有效链接时，系统会自动将文字、图片、音频与视频作为一个多模态案例处理，无需选择“手动组合”模式。系统先合并可回溯原文并原生生成紧凑主张 JSON，再执行 M1–M7：检索规划、Exa 并发检索、证据归一化、LLM 并发初筛、综合研判和完整报告渲染。

本次模块化升级的数据协议、阶段输入输出、SSE、Web/Android 接入、兼容迁移和维护约束详见 [`docs/模块化核验流水线升级说明.md`](docs/模块化核验流水线升级说明.md)。

小红书上游已区分图文、视频、长文和实况照片笔记；商品、地点、话题与合作卡片作为发布上下文合并。完整调查和适配说明见 [`docs/小红书帖子类型与解析适配报告.md`](docs/小红书帖子类型与解析适配报告.md)。

## 全链路流程

1. **内容提取**：解析公开内容，获取字幕、ASR、图文 OCR 或必要的画面观察；一次 LLM 调用直接输出 `{主题, 主张[]}`，不再经过旧协议转换。
2. **M1 输入规范化**：严格校验上游 JSON，为主张分配稳定的 `C1`、`C2` 编号。
3. **M2 检索规划**：LLM 为每条主张定义核验需求、证据门槛和查询，保存模型原始输入、输出、指标及验证后的计划。
4. **M3 并发检索**：把全部查询同时发送给 Exa；每项任务独立限时，单项超时或失败不会阻塞其他查询。
5. **M4 证据归一化**：纯程序解析、清洗、去重并建立统一证据池，不机械判定来源可信或事实真假。
6. **M5 证据初筛**：将证据池分块并发交给 MiMo Pro，紧凑输出每条证据与各主张的关系、直接性和可用性，不静默丢弃候选。
7. **M6 综合研判**：MiMo Pro 结合全部初筛账本，逐主张交叉核验，并识别循环引用、证据缺口、限定词差异和叙事引导；非法或不完整 JSON 会复用现有证据自动重试。
8. **M7 报告渲染**：纯程序验证并渲染完整 JSON/Markdown，网页与 App 展示综合结论、逐项依据、叙事分析、待补证据、关键来源、耗时与用量。

Web 的 `POST /api/analyze/stream` 和 App 的 Job SSE 都会在阶段切换时立即发送进度；这不是模型逐 token 流式输出，因此不会牺牲结构化结果的完整性。

## 当前输出协议

完整字幕/ASR、逐图 OCR、画面观察和发布上下文保存在 `full_source_text`、`transcript` 与 `keyframes`。面向阅读的 `cleaned_article` 会移除时间码、传输标签、重复 OCR 和截断碎片，再按发布内容、口播字幕与画面信息重组。服务端计算 `text_retention_percent`；低于 99% 时结果自动标记为 `partial`。下游标准数据位于 `structured_data`：

```json
{
  "主题": "无籽西瓜食品安全说法核验",
  "主张": [
    {
      "文本": "使用激素喷洒雌花培育的西瓜，其种子会变白并失去繁殖能力。",
      "表达": "直接"
    },
    {
      "文本": "人工干预培育出的无籽西瓜可能不安全。",
      "表达": "隐含"
    }
  ]
}
```

`表达` 仅允许 `直接`、`转述`、`隐含`。上游必须保持“可能、涉嫌、全部、唯一”等原始强度，拆开可分别为真假的复合命题，并识别由反讽、反问、剪辑或标题形成的事实性引导。纯娱乐、虚构角色剧情、游戏解说等没有现实世界可核验主张的内容输出空 `主张`，下游直接返回 `skipped`。MiMo 请求使用严格 JSON Schema，服务端再用 Pydantic 校验字段、类型、长度和去重；不存在“先生成旧原子主张，再转成新协议”的额外调用。

## 核验档位

- `speed`：M2 使用 MiMo 2.5，M5/M6 使用 MiMo 2.5 Pro，M6 关闭思考；适合短视频场景的快速风险粗筛。
- `quality`：流程、查询数和证据池完全相同，只为 M6 开启思考；适合更复杂、歧义更高的案例。

两档都遵循同一风险取向：证据不足时宁可标为待核实，也不把营销号循环引用或缺少可核对身份细节的消息直接判为属实。该取向由报告模型结合案例执行，不以主题、人物、学校或领域硬编码结论。

## 自适应处理

1. 从手机分享文案抽取 URL，逐跳安全展开 `b23.tv` / `v.douyin.com`；
2. 区分视频和抖音 `awemeType=68` 图文轮播；
3. 优先使用完整平台字幕；无字幕时先对完整音频执行分段 ASR；
4. 字幕或 ASR 获得有效口播文本后立即短路，不下载视觉轨、不抽帧；
5. 只有无有效口播文本时，视频才提取场景变化/周期关键帧并执行 OCR；图文始终下载全部图片；
6. 合并发布上下文、完整语音、OCR 和画面信息；
7. 通过严格 JSON Schema 转换为下游标准数据；
8. 持久化完整原文、结构化数据、覆盖率和成本轨迹。

## 启动

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
# 至少填写 MIMO_API_KEY；推荐同时填写 EXA_API_KEY
uvicorn app.main:app --reload
```

打开 <http://127.0.0.1:8000>。接口文档位于 <http://127.0.0.1:8000/api/docs>。

开发环境通过独立、持久化的 Edge Profile 维护抖音会话，不读取个人浏览器 Cookie。Cookie 文件年龄只用于减少刷新次数；真正的健康检查是一次实际作品解析。遇到 Cookie/验证类错误时，各解析和下载阶段只强制刷新一次，并通过进程锁避免并发覆盖。

抖音视频优先监听抖音页面自身签名后的 `aweme/detail` 响应，直接选择包含完整 H.264 视频与 AAC 音频的低码率 MP4；yt-dlp 是兼容备用路径。`awemeType=68` 图文仍走页面作品数据解析并下载全部图片。两条路径均不访问私密、付费、登录限定或 DRM 内容。

若无头会话被抖音要求验证，先停止服务，在 `.env` 临时设置 `DOUYIN_BROWSER_HEADLESS=false`，启动并请求一次抖音作品，在弹出的专用 Edge 窗口中完成验证；随后恢复 `true`。该 Profile 只能用于低权限服务会话，不能指向个人浏览器目录。

生产环境建议将该浏览器适配器独立部署为低权限会话服务，保持稳定出口 IP，并监控真实作品探测成功率。若使用外部 Netscape Cookie 作为 yt-dlp 备用会话，应配置 `YTDLP_COOKIES_FILE`，并将导出浏览器当时的完整 UA 写入 `YTDLP_USER_AGENT`；一旦真实探测失败即轮换会话，而不是仅按固定 TTL 判断。

快手和视频号已走各自的页面适配器，不再交给不支持它们的 yt-dlp。快手可配置 `KUAISHOU_COOKIES_FILE` / `KUAISHOU_USER_AGENT`，视频号可配置 `WECHAT_CHANNELS_COOKIES_FILE` / `WECHAT_CHANNELS_USER_AGENT`；Cookie 使用 Netscape 格式，并必须与导出时的 UA、出口 IP 和设备会话匹配。遇到验证码或过期 `exportkey` 时系统会返回可操作错误，不会绕过平台验证。真实测试结论见 [`docs/快手微博视频号与自动多模态链路测试报告.md`](docs/快手微博视频号与自动多模态链路测试报告.md)。

## 接口

- `POST /api/analyze`：默认执行内容提取与信源核实全链路；传 `verify=false` 可仅提取
- `POST /api/analyze/stream`：同一全链路的 SSE 版本，依次发送 `progress` 与最终 `result`/`error`
- `POST /api/analyze/upload`：以 multipart 同时提交 `text` 与多个 `files`，合并为一个多模态核验案例
- `POST /api/analyze/upload/stream`：上传/纯文字全链路的 SSE 版本
- `POST /api/verify`：对已有紧凑主张 JSON 单独执行或重试信源核实
- `GET /api/videos`：列出持久化结果
- `DELETE /api/videos/{cache_key}`：删除单条
- `DELETE /api/videos`：清空全部
- `POST /v1/jobs`：创建可恢复、幂等的后台核验任务，立即返回 `202`
- `GET /v1/jobs/{job_id}`：查询任务状态与当前阶段
- `GET /v1/jobs/{job_id}/events`：SSE 阶段事件，支持 `Last-Event-ID`
- `GET /v1/jobs/{job_id}/result`：读取移动端结论卡片与完整分析
- `POST /v1/jobs/{job_id}/cancel`：尽力取消任务
- `DELETE /v1/jobs/{job_id}/source`：删除任务的原始分享输入

## 小真 Android MVP

本地后端无需 Redis/PostgreSQL 即可调试：保持 `MIMO_JOB_MODE=memory` 并启动 Uvicorn。Android 模拟器默认访问 `http://10.0.2.2:8000/`；真机通过 Gradle 参数设置同一局域网或 HTTPS 地址：

```powershell
cd android
.\gradlew.bat assembleDebug -PMIMO_API_BASE_URL=http://192.168.1.20:8000/
```

在短视频 App 的分享面板选择“小真核验”后，透明 Activity 只投递 WorkManager 请求便立即关闭；任务进度存入 Room，并通过同一个通知 ID 更新。完整模块、接口示例、生产部署和小米待接事项见 [`docs/小真App实现说明.md`](docs/小真App实现说明.md)。

生产式本地栈使用 PostgreSQL、Redis Streams、ARQ 和 MinIO：

```powershell
Copy-Item .env.example .env
# 填写 MIMO_API_KEY / EXA_API_KEY
docker compose up --build
```

`mode=auto` 使用 L0–L3 成本阶梯自适应提取；`mode=visual` 强制执行 L3 全视频多模态补充。`verification_mode=speed|quality` 独立控制下游报告档位。

下游模型、超时、token、查询数、Exa 结果数和批次大小都可在 `.env` 配置，完整清单及注释见 `.env.example`。新 M3 统一使用 Exa：学术、官方、法规、媒体等是检索计划的“渠道意图”，由 Exa 查询覆盖，不再依赖 OpenWebSearch 或多个返回结构不一致的搜索适配器。

## 审计产物

每次核验都会生成独立目录 `data/trust/cases/<case_id>/runs/<run_id>/`。案例目录的 `input.json` 保存上游紧凑主张；运行目录保留 `00_input.json`、`01_claims.json`、M2 的模型输入/原始输出/指标/验证计划、M3 原始检索结果、M4 证据池、M5 证据账本、M6 报告草稿、M7 完整 JSON/Markdown，以及 `07_pipeline_metrics.json`。后者汇总各模块墙钟耗时、LLM 输入/输出/思考 token、调用次数、Exa 结果数和 API 返回费用（若 Exa 提供）。失败阶段同样写入 `run.json`，便于只检查出错模块。

## 边界

- `隐含` 是内容实际形成的事实性指控或叙事引导，不是系统认可的事实；它必须和直接、转述主张一样接受证据核验。
- 仅处理公开且用户有权访问的内容，不绕过 DRM、登录、付费、私密或地区限制。
- 视觉或结构化模型失败时保留完整原文，覆盖状态会标记为 `partial` 或 `needs_review`。
- 非当前协议版本的历史缓存会在启动时删除，避免旧结构继续流向下游。
