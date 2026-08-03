# MiMoTrust 最小平台内容网关

Python 3.12 标准库实现，无服务端第三方依赖。首轮只加载固定的
`content_registry/registry.json`，不提供上传或内容修改接口。

## 启动

```powershell
python -m sandbox.content_gateway.server --host 127.0.0.1 --port 8787
```

接口：

```text
GET  /health
GET  /v1/feed                    # App 公开只读内容目录，不签发 grant
POST /v1/context-grants
POST /v1/grants/exchange
GET  /assets/...                 # 本地演示资产读取
```

`/v1/feed` 只返回活动内容，按 `display_order` 排序，并携带 Manifest 1.0 和界面计数。
响应时会把 Manifest 中指向 `127.0.0.1` 的本地演示资源 URL 外化为网关公网基址；磁盘上的
Manifest 不会被修改。grant 兑换响应使用同样的 URL 外化规则。

申请 grant：

```json
{
  "content_id": "video-001",
  "content_version": "v1",
  "audience": "mimotrust_guardian_backend",
  "scopes": ["manifest:read", "asset:read"]
}
```

兑换时提交 `grant_code`、`audience`、`content_id` 和 `content_version`。成功响应使用
`{"grant_id": "...", "manifest": {...}}` 信封，信封内 `manifest` 严格遵循 Manifest 1.0。

grant 默认 180 秒过期且只能成功兑换一次。错误码包括
`GRANT_EXPIRED`、`GRANT_REPLAYED`、`AUDIENCE_MISMATCH`、
`CONTENT_MISMATCH` 和 `CONTENT_UNAVAILABLE`。日志只记录 `grant_id`，不记录完整
`grant_code`。

## 验证

```powershell
python sandbox\tools\validate_contracts.py
python -m unittest discover -s sandbox\content_gateway\tests -v
python sandbox\tools\verify_first_round.py --gateway http://127.0.0.1:8787
```

最后一个命令会实际下载 `video-001`，流式检查 MIME、字节数和 SHA-256，并确认同一
grant 的第二次兑换返回 `GRANT_REPLAYED`。

## 当前云端 Debug 环境

2026-08-02 已在阿里云 ECS 单实例部署：

```text
公网网关：http://47.94.58.72
Python 服务：127.0.0.1:8787
公网入口：Nginx :80
```

公网验证已通过健康检查、grant 签发、一次兑换、视频下载、SHA-256 校验和重放拒绝。
当前运行时 registry 为 7 条内容：4 个视频、1 篇文章、1 篇图文和 1 个图集；音频尚无
真实素材。`8787` 不对公网开放，grant 仍为进程内存状态，因此不得
扩展为多实例。正式演示前必须配置 HTTPS 域名，生产化前必须将 grant 迁移到支持原子
单次兑换的共享存储。
