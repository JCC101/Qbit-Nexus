Qbit-Nexus 📡

Centralized Distribution Node for qBittorrent Clusters.

Qbit-Nexus 是一个专为 PT 玩家和多服务器用户设计的高性能分发中枢。它允许您通过单一的 Web 界面，将种子文件或磁力链接同时推送到多个 qBittorrent 实例中，实现“一次上传，全网分发”。

✨ 核心特性 (Features)

🚀 多端广播 (Broadcast)：通过多线程并发技术，一键将任务分发到所有已连接的节点，互不阻塞。

🎛️ 精细控制 (Granular Control)：

支持自定义 保存路径 (Save Path)

支持设置 分类 (Category) 和 标签 (Tags)

可选 自动管理模式 (Auto TMM)、暂停添加、跳过校验等。

🛡️ 隐私优先 (Privacy First)：所有服务器配置（地址/账号/密码）仅加密存储在本地容器中，绝不上传云端。

🐳 原生 Docker (Docker Native)：极简部署，支持环境变量配置，开箱即用。

🛠️ 快速部署 (Deployment)

1. 克隆仓库

首先将代码下载到您的服务器：

git clone [https://github.com/您的用户名/Qbit-Nexus.git](https://github.com/您的用户名/Qbit-Nexus.git)
cd Qbit-Nexus


2. 启动服务

项目默认运行在 6688 端口（可在配置中修改）。

docker compose up -d


3. 访问控制台

打开浏览器访问：http://服务器IP:6688

⚙️ 配置指南 (Configuration)

修改运行端口

如果您不想使用默认的 6688 端口，可以通过以下两种方式修改：

方法 A：通过环境变量（临时）

NEXUS_PORT=18080 docker compose up -d


方法 B：修改配置文件（永久）
编辑 docker-compose.yml 文件：

ports:
  - "18080:5000"  # 将 6688 修改为您想要的端口


数据持久化

项目会在当前目录下生成 data/ 文件夹，其中：

nexus_config.json: 存储您的节点列表。

备份建议：迁移服务器时，只需备份 data/ 目录即可恢复所有节点配置。

🖥️ 使用说明

添加节点：在左侧面板输入 qBittorrent 的 WebUI 地址（如 http://192.168.1.5:8080）、用户名和密码。

连通性测试：点击节点旁边的插头图标 🔌，系统会尝试连接并返回 qBittorrent 的版本号。

分发任务：

上传 .torrent 文件或粘贴 Magnet 链接。

填写分类（如 Movies）或标签（如 PT,4K）。

点击 Initiate Broadcast 开始分发。

右下角的日志终端会实时显示每个节点的推送结果。

❓ 常见问题 (FAQ)

Q: 支持 HTTPS (SSL) 的 qBittorrent 吗？
A: 支持。程序已默认忽略自签名证书错误，确保能连接到内网 HTTPS 节点。

Q: 为什么某些节点提示 "Unreachable"？
A: 请检查：

Docker 容器是否能访问目标 IP（如果在同一台机器，请使用宿主机内网 IP，不要用 127.0.0.1）。

目标 qBittorrent 的 "验证来源 IP" 选项是否已关闭（通常不需要关闭，但如果遇到 401 错误可尝试）。

📜 许可证

本项目基于 MIT License 开源。