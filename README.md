# 🤖 Google AI Proxy

将 Google AI Mode（搜索中的 AI 对话功能）封装为 **OpenAI 兼容 API**，支持多账户轮询、Cookie 自动轮换、流式输出，可直接接入 ChatBox、NextChat 等支持自定义 API 的客户端。

## ✨ 功能特性

- **OpenAI 兼容 API** - 完整实现 `/v1/chat/completions` 和 `/v1/models` 接口
- **流式输出 (SSE)** - 支持 `stream: true` 实时流式响应
- **多账户管理** - 支持添加多个 Google 账户，自动轮询分配
- **Cookie 自动轮换** - 定时调用 Google RotateCookies 保持会话有效
- **Web 管理后台** - 可视化管理账户、查看日志、生成 API Key
- **API Key 鉴权** - 支持配置文件或数据库管理 API Key
- **请求日志** - 记录所有请求的详细信息和统计
- **一键部署** - 提供 Linux 一键部署脚本

## 📦 项目结构

```
google-ai-proxy/
├── main.py                 # 应用入口
├── requirements.txt        # Python 依赖
├── .env.example           # 配置模板
├── deploy.sh              # Linux 一键部署脚本
├── app/
│   ├── config.py          # 配置管理
│   ├── core/
│   │   └── google_client.py   # Google AI Mode 客户端
│   ├── models/
│   │   ├── database.py    # 数据库连接
│   │   └── account.py     # 数据模型
│   ├── services/
│   │   └── account_manager.py # 账户管理服务
│   ├── api/
│   │   └── openai_routes.py   # OpenAI 兼容 API
│   └── admin/
│       ├── routes.py      # 管理后台 API
│       └── templates/     # 前端页面
│           ├── index.html # 管理主页
│           └── login.html # 登录页
└── data/                  # 运行时数据
    ├── proxy.db           # SQLite 数据库
    └── logs/              # 日志文件
```

## 🚀 快速开始

### 方式一：Linux 一键部署（推荐）

```bash
# 下载项目
git clone <repo-url> google-ai-proxy
cd google-ai-proxy

# 一键部署
sudo bash deploy.sh
```

部署完成后会自动：
- 安装 Python 依赖
- 创建虚拟环境
- 生成配置文件（随机管理员密码）
- 创建 Systemd 服务并启动

### 方式二：手动部署

```bash
# 1. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置
cp .env.example .env
nano .env  # 编辑配置

# 4. 启动
python main.py
```

## ⚙️ 配置说明

编辑 `.env` 文件：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `PORT` | 8787 | 服务端口 |
| `ADMIN_USERNAME` | admin | 管理后台用户名 |
| `ADMIN_PASSWORD` | changeme123 | 管理后台密码 |
| `DATABASE_URL` | sqlite+aiosqlite:///data/proxy.db | 数据库连接 |
| `ACCOUNT_ROTATION_STRATEGY` | round_robin | 轮询策略: round_robin/random/least_used |
| `COOKIE_ROTATE_INTERVAL` | 600 | Cookie 轮换间隔（秒） |
| `REQUEST_TIMEOUT` | 60 | 请求超时（秒） |
| `HTTP_PROXY` | - | HTTP代理（用于访问Google） |
| `API_KEYS` | - | API Key 列表（逗号分隔） |

## 📖 使用方法

### 1. 添加 Google 账户

1. 访问管理后台 `http://your-server:8787/admin/`
2. 登录后点击「账户管理」→「添加账户」
3. 填写 Google 邮箱
4. 粘贴从浏览器导出的 Cookie JSON

**导出 Cookie 方法：**
1. 登录 Google 账户，访问 `https://www.google.com/search?udm=50`
2. 使用 [Cookie-Editor](https://cookie-editor.cgagnier.ca/) 或 [EditThisCookie](https://www.editthiscookie.com/) 浏览器插件
3. 导出所有 google.com 的 Cookie 为 JSON 格式

### 2. 创建 API Key

在管理后台的「API Key」页面创建 Key，用于客户端鉴权。

### 3. 接入客户端

以 ChatBox 为例：

- **API Provider**: OpenAI API Compatible
- **API Base URL**: `http://your-server:8787/v1`
- **API Key**: 管理后台创建的 Key
- **Model**: `google-ai-mode`

### 4. 直接调用 API

```bash
# 非流式
curl http://localhost:8787/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google-ai-mode",
    "messages": [{"role": "user", "content": "你好，请介绍一下自己"}]
  }'

# 流式
curl http://localhost:8787/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google-ai-mode",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'

# 列出模型
curl http://localhost:8787/v1/models \
  -H "Authorization: Bearer sk-your-api-key"
```

## 🔧 运维命令

```bash
# 查看服务状态
systemctl status google-ai-proxy

# 查看实时日志
journalctl -u google-ai-proxy -f

# 重启服务
systemctl restart google-ai-proxy

# 停止服务
systemctl stop google-ai-proxy

# 编辑配置（修改后需重启）
nano /opt/google-ai-proxy/.env
```

## 🛡️ 安全建议

1. **修改默认密码** - 首次部署后立即修改管理后台密码
2. **配置 API Key** - 生产环境务必配置 API Key 鉴权
3. **使用反向代理** - 建议通过 Nginx 反向代理并配置 HTTPS
4. **限制访问** - 通过防火墙限制管理后台的访问 IP

## 📝 技术栈

- **后端**: Python 3.10+ / FastAPI / SQLAlchemy / httpx
- **前端**: 原生 HTML/CSS/JS（无框架依赖）
- **数据库**: SQLite（默认）/ PostgreSQL / MySQL
- **部署**: Systemd / Uvicorn

## ⚠️ 免责声明

本项目仅供学习和研究使用。使用者需遵守 Google 服务条款，对使用本项目产生的一切后果自行负责。
