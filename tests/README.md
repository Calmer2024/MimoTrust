# 测试

## 运行

```powershell
cd D:\08Projects\2026\MimoTrust
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

## 测试文件

| 文件 | 覆盖范围 |
|------|---------|
| `test_content_inputs.py` | 内容提取、平台 URL 校验、文章解析 |
| `test_jobs.py` | Job 创建、状态流转、上传 |
| `test_job_uploads.py` | 多模态文件上传 |
| `test_trust_service.py` | 核验服务入口 |
| `test_pipeline_retry.py` | 流水线重试逻辑 |
| `test_pipeline_timings.py` | 耗时指标 |
| `test_retrieval_streaming.py` | 检索流式输出 |
| `test_transcript.py` | 字幕/ASR 处理 |
| `test_thumbnails.py` | 封面处理 |
| `test_douyin_session.py` | 抖音浏览器适配器 |
| `test_kuaishou_channels.py` | 快手/视频号解析 |
| `test_weibo.py` | 微博解析 |
| `test_xiaohongshu.py` | 小红书解析 |
| `test_controlled_content_bridge.py` | 受控内容跨 App 协议 |
| `test_controlled_content_exchange.py` | grant 兑换 |
| `test_web_shell.py` | Web 接口集成 |
