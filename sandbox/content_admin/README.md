# sandbox 开发者内容管理

该服务为开发者提供五类受控内容的草稿上传、规范化校验、Manifest 预览和发布能力。
它不是普通用户功能，不修改 Android App，也不改变 Context、grant 或 Manifest 版本。

## 运行边界

- 管理服务固定监听 `127.0.0.1:8788`，通过 SSH 隧道访问；
- 文件由管理服务流式接收，再上传至阿里云 OSS；
- OSS 凭据只从 ECS 环境变量读取，不发送给浏览器；
- 草稿存储和运行时 registry 建议放在 `/var/lib/mimotrust/`，不写入 Git 工作树；
- 只有全部资源上传并通过 Manifest 1.0 校验后，才会原子更新 registry；
- 当前 Android App 仍读取 APK 内置的三视频数据，不会自动显示新发布内容。

## 支持类型

| 类型 | 必需资源 | 可选资源 |
|---|---|---|
| `video` | 一个 `video/mp4` 分析资源 | 封面、WebVTT 字幕 |
| `audio` | 一个 MP3/M4A 分析资源 | 封面、WebVTT 字幕 |
| `article` | 一个 UTF-8 纯文本资源 | 封面 |
| `rich_article` | 有序文字块、至少一张图片 | 无 |
| `image_gallery` | 一张或多张有序图片 | 无 |

文本上传会统一为 UTF-8 和 LF 换行。图片自动读取尺寸；服务器存在 `ffprobe` 时自动读取
音视频时长、尺寸和编码。每个资源的字节数和 SHA-256 均由服务端计算。

`video`、`audio` 和 `article` 的 `content_hash` 等于主分析资源 SHA-256。`rich_article`
和 `image_gallery` 当前使用 `mimotrust-composite-v1`：对内容类型、有序分析资源
`asset_id/sha256` 以及图文 blocks 执行 UTF-8、键排序、无空白 JSON 序列化后计算
SHA-256。该组合算法仍需守护者后端确认，正式确认前只用于 Debug 数据。

## API

```text
GET  /health
GET  /admin
GET  /admin/v1/config
GET  /admin/v1/contents
POST /admin/v1/drafts
GET  /admin/v1/drafts/{draft_id}
PUT  /admin/v1/drafts/{draft_id}/assets/{asset_id}
POST /admin/v1/drafts/{draft_id}/preview
POST /admin/v1/drafts/{draft_id}/publish
```

除静态页面和健康检查外，所有接口要求：

```http
Authorization: Bearer <MIMOTRUST_ADMIN_TOKEN>
```

资源上传使用原始请求体和准确的 `Content-Length`，不使用 Base64 或 multipart，避免大文件
在浏览器和 ECS 内存中复制。

## 本地测试

```powershell
python -m unittest discover -s sandbox\content_admin\tests -v
python -m unittest discover -s sandbox\content_gateway\tests -v
python sandbox\tools\validate_contracts.py
```

## ECS 配置

当前确认配置：

```text
Bucket:          sourcecheckcheck
Endpoint:        https://oss-cn-beijing.aliyuncs.com
Public base URL: https://sourcecheckcheck.oss-cn-beijing.aliyuncs.com
Object prefix:   sandbox-content
Read policy:     public-read (Debug only)
```

2026-08-02 ECS 部署状态：`mimotrust-content-admin.service` 已启用并监听
`127.0.0.1:8788`；现有网关读取 `/var/lib/mimotrust/content_registry/registry.json`。
首条真实发布内容为 `article-001/v1`：

```text
source_url:  https://sourcecheckcheck.oss-cn-beijing.aliyuncs.com/sandbox-content/article/article-001/v1/article-body.txt
size_bytes:  3411
sha256:      7e254d0de54d4a40167ad88020de49e53b98e532c47c0e6aa0ce096d3870a06a
```

该正文由原始 Windows CRLF 文件规范化为 UTF-8/LF，因此哈希与原文件不同。公网已通过
grant 签发、一次兑换、Manifest 读取、OSS 下载、MIME/大小/SHA-256 和重放拒绝验证。

部署文件位于 `deploy/`。AccessKey 和 Secret 不得提交到仓库，也不得通过聊天、命令行参数
或日志传递。管理员使用 RAM 子账号，仅授予目标 Bucket 前缀的上传和读取元数据权限。

`mimotrust-gateway-runtime-registry.conf` 是现有网关的 systemd drop-in，使网关读取
`/var/lib/mimotrust/content_registry/registry.json`。初次部署时先从 Git 中的固定注册表复制
完整种子目录，后续管理服务只修改运行时副本。

公网安全组不需要开放 8788。访问方式：

```powershell
ssh -L 8788:127.0.0.1:8788 mimoecs
```

然后打开 `http://127.0.0.1:8788/admin`。SSH 隧道提供传输保护，管理令牌提供第二层访问
控制。若以后要求直接公网访问，必须先增加 HTTPS 域名、认证、限流和审计。
