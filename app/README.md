# 后端核验服务

Python + FastAPI，承载 M1-M7 模块化核验流水线。

> 完整说明见 [docs/后端说明.md](../docs/后端说明.md) · 接口文档见 [docs/接口文档.md](../docs/接口文档.md)

## 启动

```powershell
# 安装依赖
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

# 配置
Copy-Item .env.example .env
# 填写 MIMO_API_KEY 和 EXA_API_KEY

# 启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

打开 http://127.0.0.1:8000 · Swagger http://127.0.0.1:8000/api/docs

## 模块结构

```
app/
├── main.py                      # FastAPI 入口，路由注册
├── config.py                    # 环境变量配置
├── pipeline.py                  # 内容提取管线（平台解析、ASR、OCR）
├── content.py                   # 文章/上传内容解析
├── mimo.py                      # MiMo API 调用封装
├── security.py                  # URL 校验、SSRF 防护
├── cache.py                     # 结果缓存
├── thumbnails.py                # 封面处理
├── transcript.py                # 字幕/ASR 处理
├── douyin_cookies.py            # 抖音浏览器适配器
├── kuaishou.py                  # 快手解析器
├── weibo.py                     # 微博解析器
├── xiaohongshu.py               # 小红书解析器
├── channels.py                  # 视频号解析器
├── controlled_content.py        # 受控内容 grant 兑换代理
├── jobs/                        # 异步 Job 系统
│   ├── api.py                   # Job REST 接口
│   ├── models.py                # 数据模型
│   ├── worker.py                # Job 处理逻辑（M1-M7 调度）
│   ├── runtime.py               # Job 运行时管理
│   ├── store.py                 # 存储后端（memory / PostgreSQL）
│   ├── events.py                # SSE 事件管理
│   ├── uploads.py               # 文件上传处理
│   └── artifacts.py             # 报告产物存储
└── trust/                       # 核验流水线
    ├── service.py               # 核验服务入口
    └── pipeline_v2/             # M1-M7 模块化实现
        ├── config.py            # 流水线配置
        ├── normalization.py     # M1 输入规范化
        ├── planning.py          # M2 检索规划
        ├── retrieval.py         # M3 并发检索
        ├── search_providers.py  # Exa 搜索适配
        ├── evidence.py          # M4 证据归一化
        ├── evidence_triage.py   # M5 证据初筛
        ├── synthesis.py         # M6 综合研判
        ├── rendering.py         # M7 报告渲染
        ├── pipeline.py          # 流水线编排
        ├── workspace.py         # 运行目录管理
        └── pipeline_metrics.py  # 指标收集
```

## 关键设计

- **Job 系统**：`memory` 模式（开发）/ `distributed` 模式（PostgreSQL + Redis）
- **平台解析器**：各平台独立适配，不依赖统一 yt-dlp
- **安全**：URL 白名单 + SSRF 防护 + 外部内容清洗
- **审计**：每次核验生成独立目录 `data/trust/cases/<case_id>/runs/<run_id>/`
