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
  -> comment/share 生成 deferred_grant 候选 Context 2.2
  -> MethodChannel
  -> Kotlin 显式广播到 com.mimotrust.guardian
  -> 用户点击 MimoTrust 悬浮球
  -> guardian 显式请求当前前台视频
  -> 沙盒签发一次性 grant 并返回 guardian_request Context 2.2
  -> guardian 兑换 Manifest、校验视频资产并创建核验任务
```

目录：

- `content_registry/`：首轮静态发布索引、Manifest 和本地封面；
- `content_gateway/`：Python 标准库 Mock 网关；
- `mimotrust_controlled_content/`：Flutter Android 受控内容 App；
- `tools/`：MP4 元数据、合同校验和真实链路验证工具；
- `IMPLEMENTATION_CONTRACT.md`：已冻结的跨系统技术标识与行为。
- `DEVICE_VERIFICATION.md`：最新真机发送端验收记录。

本阶段没有上传接口、自动上传脚本或核验逻辑。后期自动上架可以替换静态 registry
数据源，但应保持 Context 2.2、Manifest 1.0 和 grant 兑换合同不变。
