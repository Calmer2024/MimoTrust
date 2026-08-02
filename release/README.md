# Release 目录

本目录存放构建产物。

## 文件

| 文件 | 说明 |
|------|------|
| `mimotrust-api.tar` | 后端核验服务 Docker 镜像 |
| `xiaozhen-app.apk` | 小真核验 Android App（待补充） |
| `sandbox-app.apk` | 受控内容沙盒 Android App（待补充） |

## Docker 镜像使用

```bash
# 导入镜像
docker load -i mimotrust-api.tar

# 启动服务
docker run -d --name mimotrust -p 8000:8000 \
  -e MIMO_API_KEY=your_key \
  -e EXA_API_KEY=your_key \
  mimotrust-api:latest

# 验证
curl http://localhost:8000/api/health
```

## 云服务器

后端已部署在 `http://47.94.58.72:8000`，可直接访问。

```bash
# 一键更新部署
ssh mimo "bash /srv/mimotrust/deploy.sh"
```
