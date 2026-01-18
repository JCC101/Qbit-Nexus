# Qbit-Nexus 📡

**Centralized Distribution Node for qBittorrent Clusters.**

Qbit-Nexus 是一个专为 PT 玩家和多服务器用户设计的高性能分发中枢。它允许您通过单一的 Web 界面，将种子文件或磁力链接同时推送到多个 qBittorrent 实例中，实现“一次上传，全网分发”。

## ✨ 核心特性 (Features)

* 🚀 **多端广播 (Broadcast)**
    通过多线程并发技术，一键将任务分发到所有已连接的节点，互不阻塞。

* 🎛️ **精细控制 (Granular Control)**
    * 支持自定义 **保存路径 (Save Path)**
    * 支持设置 **分类 (Category)** 和 **标签 (Tags)**
    * 可选 **自动管理模式 (Auto TMM)**、暂停添加、跳过校验等。

* 🛡️ **隐私优先 (Privacy First)**
    所有服务器配置（地址/账号/密码）仅加密存储在本地容器中，绝不上传云端。

* 🐳 **原生 Docker (Docker Native)**
    极简部署，支持环境变量配置，开箱即用。

---

## 🛠️ 快速部署 (Deployment)

### 1. 使用 Docker Compose (推荐)

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'
services:
  nexus:
    # 镜像地址 (自动构建)
    image: ghcr.io/agonie0v0/qbit-nexus:latest
    container_name: qbit-nexus
    restart: unless-stopped
    ports:
      - "6688:5000"
    volumes:
      - ./data:/data
    environment:
      - DATA_DIR=/data
      - TZ=Asia/Shanghai
```

启动服务：

```bash
docker compose up -d
```

### 2. 访问控制台

打开浏览器访问：`http://服务器IP:6688`

---

## ⚙️ 配置指南 (Configuration)

### 数据持久化

项目会在当前目录下生成 `data/` 文件夹：

* `nexus_config.json`: 存储您的节点列表。
* **备份建议**：迁移服务器时，只需备份 `data/` 目录即可恢复所有节点配置。

### 端口修改

如果需要修改默认的 `6688` 端口，请修改 compose 文件中的 `ports` 部分，例如 `"8080:5000"`。

---

## 📜 许可证

本项目基于 MIT License 开源。
