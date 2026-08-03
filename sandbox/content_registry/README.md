# 固定内容注册表

`registry.json` 是首轮 Mock 网关的临时发布索引，不是长期内容管理数据库。

- `status=active` 的条目必须引用存在且合法的 Manifest；
- `(content_id, content_version)` 在注册表中必须唯一；
- 网关只为 `active` 内容签发 grant；
- Manifest 是兑换后返回的权威内容快照；
- 当前登记 `video-001`、`video-002` 和 `video-003` 三条固定视频；
- registry 中的 `display_metrics` 只用于沙盒互动数量展示，不属于 Manifest 或 Context；
- 后期自动上架时可替换注册表加载器，但保持 Manifest 1.0 和 grant 合同不变。

开发者可以使用 `sandbox/content_admin/` 将资源上传 OSS，并在完整校验后原子更新部署环境
的运行时副本。Git 中的本目录仍作为初始种子和合同夹具，不直接承载 ECS 上的动态数据。
