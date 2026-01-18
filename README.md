# Qbit-Nexus 📡

**Advanced Batch Task Manager for qBittorrent Clusters.**

Qbit-Nexus 是一个专为 PT 玩家和多服务器用户设计的现代化分发中枢。它允许您通过单一的 Web 界面，将种子文件或磁力链接同时推送到多个 qBittorrent 实例中，支持所有原生高级参数配置。

![UI Preview](https://via.placeholder.com/1200x600.png?text=Qbit-Nexus+Dashboard+Preview)
*(建议替换为您自己的项目截图)*

## ✨ 核心特性 (Features)

* 🚀 **批量分发 (Batch Add)**
    一键将任务分发到选定的多台服务器，支持多线程并发推送，互不阻塞。

* 🎛️ **原生全参支持 (Native Options)**
    完美复刻 qBittorrent 添加任务时的所有选项：
    * **基础**: 保存路径、分类、标签、重命名。
    * **布局**: 内容布局 (创建子目录/不创建)、自动管理模式 (Auto TMM)。
    * **高级**: 跳过哈希校验、按顺序下载、先下载首尾块、添加到队列顶部。

* 📉 **限速与停止 (Limits & Conditions)**
    * 支持设置任务级别的 **下载/上传限速**。
    * 支持设置 **最大分享率** 和 **最大做种时间** 停止条件。
    * 支持 **全局预设**，一键应用常用限速配置，无需重复输入。

* 📱 **响应式设计 (Responsive UI)**
    * 采用 "Morning Mist" 清爽明亮风格。
    * **自适应布局**：完美适配 4K/2K 超宽屏显示，同时兼容移动端手机操作。

* 🛡️ **安全增强 (Security)**
    * 支持 **Web 访问密码** 保护（通过环境变量配置）。
    * 界面 **IP 脱敏显示**，保护服务器隐私。
    * 所有节点配置仅本地加密存储，绝不上传云端。

---

## 🛠️ 快速部署 (Deployment)

### 1. 使用 Docker Compose (推荐)

创建 `docker-compose.yml` 文件：

```yaml
version: '3.8'

services:
  nexus:
    # 镜像地址 (GitHub Container Registry)
    image: ghcr.io/agonie0v0/qbit-nexus:latest
    container_name: qbit-nexus
    restart: unless-stopped
    ports:
      # 格式: "宿主机端口:5000"
      - "6688:5000"
    volumes:
      # 数据持久化 (存储节点配置)
      - ./data:/data
    environment:
      - DATA_DIR=/data
      - TZ=Asia/Shanghai
      # --- 安全配置 (可选) ---
      # 设置此变量后，访问网页将需要登录
      # 留空则为无密码模式
      - WEB_PASSWORD=your_secure_password
```

### 2. 启动服务

```bash
docker compose up -d
```

### 3. 访问控制台

打开浏览器访问：`http://服务器IP:6688`

* 如果设置了 `WEB_PASSWORD`，请使用该密码登录。
* 默认无节点，请在左侧（或移动端菜单）点击 **"添加下载器"** 进行配置。

---

## ⚙️ 配置指南 (Configuration)

### 数据持久化
项目会在当前目录下生成 `data/` 文件夹，其中 `nexus_config.json` 存储了您的节点列表和全局预设。
> **备份建议**：迁移服务器时，只需备份 `data/` 目录即可恢复所有配置。

### 环境变量详解

| 变量名 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `DATA_DIR` | 数据存储路径 (容器内) | `/data` |
| `TZ` | 时区设置 | `Asia/Shanghai` |
| `WEB_PASSWORD` | **(新)** Web 界面访问密码 | 无 (空) |
| `SECRET_KEY` | Flask Session 密钥 (可选) | 随机生成 |

---

## 📜 许可证

本项目基于 MIT License 开源。
