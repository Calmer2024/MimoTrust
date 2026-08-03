# MiMoTrust 受控内容沙盒

当前已完成首轮最小纵向数据链路和 Android 发送端：

```text
video-001
  -> registry.json
  -> Content Manifest 1.0
  -> POST /v1/context-grants
  -> POST /v1/grants/exchange
  -> 下载 OSS 视频并校验 SHA-256
  -> 拒绝重复兑换
  -> Flutter 播放和本地互动
  -> comment/share 生成 Context 2.2 deferred_grant 候选
  -> Kotlin 显式广播到 com.mimotrust.guardian，使悬浮球提示
  -> 悬浮球发送 REQUEST_CONTENT_CONTEXT(request_id)
  -> 前台沙盒快照当前状态并申请新鲜 grant
  -> 返回 guardian_request Context 2.2
```

Android App 还会通过公开只读 `GET /v1/feed` 获取 ECS 运行时 registry，支持
`video`、`audio`、`article`、`rich_article` 和 `image_gallery` 五类 Manifest 1.0。
启动、从后台恢复或用户点击刷新按钮时重新获取；网关或远程目录不可用时回退到 APK
内置的三视频种子。Feed 同步不申请 grant，也不发送 Context。

文章、图文和画廊在 Feed 中使用不可滚动的预览页，点击后进入独立详情。阅读页保存滚动
位置和实际可见图文块；画廊保存图片下标，缩放时锁定切图，图文图片可进入全屏查看。
进入详情、阅读、切图和缩放均不主动发送 Context。评论和转发面板只发送候选；用户点击
Guardian 悬浮球后，沙盒才响应当前内容并申请一次性 grant。

目录：

- `content_registry/`：首轮静态发布索引、Manifest 和本地封面；
- `content_gateway/`：Python 标准库 Mock 网关；
- `mimotrust_controlled_content/`：Flutter Android 受控内容 App；
- `tools/`：MP4 元数据、合同校验和真实链路验证工具；
- `IMPLEMENTATION_CONTRACT.md`：已冻结的跨系统技术标识与行为。
- `DEVICE_VERIFICATION.md`：最新真机发送端验收记录。

开发者专用的 `content_admin/` 提供五类内容的规范化上传、Manifest 预览和运行时
registry 发布；普通用户和 Android App 不具备上传能力。APK 内置数据仅作为远程故障
回退；管理服务不修改 App。新发布内容由 App 的只读 Feed 自动发现；自动上架保持 Manifest 1.0
和 grant 兑换合同不变。
