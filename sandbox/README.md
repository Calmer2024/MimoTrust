# 受控内容沙盒

> 完整说明见 [docs/沙盒说明.md](../docs/沙盒说明.md)

## 目录

- `mimotrust_controlled_content/` — Flutter Android 受控内容 App
- `content_gateway/` — Python 内容网关（grant 签发与兑换）
- `content_registry/` — 静态视频索引、Manifest 和本地封面
- `tools/` — MP4 元数据、合同校验和链路验证工具
- `IMPLEMENTATION_CONTRACT.md` — Context 2.2 协议规范（已冻结）

## 快速启动

```bash
# 内容网关
python -m sandbox.content_gateway.server --host 127.0.0.1 --port 8787

# Flutter App
cd sandbox/mimotrust_controlled_content
flutter run
```
