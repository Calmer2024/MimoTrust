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
POST /v1/context-grants
POST /v1/grants/exchange
GET  /assets/...                 # 本地演示资产读取
```

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
当前仅用于三视频 Debug 联调；`8787` 不对公网开放，grant 仍为进程内存状态，因此不得
扩展为多实例。正式演示前必须配置 HTTPS 域名，生产化前必须将 grant 迁移到支持原子
单次兑换的共享存储。
