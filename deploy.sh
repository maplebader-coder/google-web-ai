#!/bin/bash
# ============================================================
# Google AI Proxy - Linux 一键部署脚本
# 支持: Ubuntu 20.04+, Debian 11+, CentOS 8+
# ============================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC} $1"; }

APP_NAME="google-ai-proxy"
APP_DIR="/opt/${APP_NAME}"
SERVICE_NAME="${APP_NAME}"
PYTHON_MIN="3.10"
DEFAULT_PORT=8787

echo ""
echo "============================================"
echo "   Google AI Proxy 一键部署脚本"
echo "============================================"
echo ""

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    log_error "请使用 root 用户运行此脚本"
    log_info "使用: sudo bash deploy.sh"
    exit 1
fi

# ========== 0. 交互配置 ==========
read -p "请输入服务运行端口 [默认: ${DEFAULT_PORT}]: " INPUT_PORT
INPUT_PORT=${INPUT_PORT:-$DEFAULT_PORT}

# 验证端口号
if ! [[ "$INPUT_PORT" =~ ^[0-9]+$ ]] || [ "$INPUT_PORT" -lt 1 ] || [ "$INPUT_PORT" -gt 65535 ]; then
    log_error "无效的端口号: ${INPUT_PORT}"
    exit 1
fi
DEFAULT_PORT=$INPUT_PORT
log_info "服务端口: ${DEFAULT_PORT}"

# ========== 1. 安装系统依赖 ==========
log_step "1/6 安装系统依赖..."

if command -v apt-get &> /dev/null; then
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-venv git curl wget > /dev/null 2>&1
    log_info "APT 依赖安装完成"
elif command -v yum &> /dev/null; then
    yum install -y -q python3 python3-pip git curl wget > /dev/null 2>&1
    log_info "YUM 依赖安装完成"
elif command -v dnf &> /dev/null; then
    dnf install -y -q python3 python3-pip git curl wget > /dev/null 2>&1
    log_info "DNF 依赖安装完成"
else
    log_warn "未识别的包管理器，请手动安装 python3, pip, git"
fi

# 检查 Python 版本
PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0")
log_info "Python 版本: ${PYTHON_VER}"

# ========== 2. 创建应用目录 ==========
log_step "2/6 部署应用文件..."

mkdir -p ${APP_DIR}

# 获取当前脚本所在目录（部署源）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 如果从项目目录运行，直接复制文件
if [ -f "${SCRIPT_DIR}/main.py" ]; then
    cp -r ${SCRIPT_DIR}/* ${APP_DIR}/
    cp -r ${SCRIPT_DIR}/.env.example ${APP_DIR}/ 2>/dev/null || true
    log_info "文件已复制到 ${APP_DIR}"
else
    log_error "请在项目根目录中运行此脚本"
    exit 1
fi

# ========== 3. Python 虚拟环境和依赖 ==========
log_step "3/6 创建虚拟环境并安装依赖..."

cd ${APP_DIR}

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q

log_info "Python 依赖安装完成"

# ========== 4. 配置 ==========
log_step "4/6 初始化配置..."

if [ ! -f "${APP_DIR}/.env" ]; then
    cp ${APP_DIR}/.env.example ${APP_DIR}/.env
    
    # 生成随机管理员密码
    RANDOM_PASS=$(openssl rand -hex 8 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(8))")
    sed -i "s/ADMIN_PASSWORD=changeme123/ADMIN_PASSWORD=${RANDOM_PASS}/" ${APP_DIR}/.env
    
    # 写入自定义端口
    sed -i "s/PORT=8787/PORT=${DEFAULT_PORT}/" ${APP_DIR}/.env
    
    log_info "配置文件已创建: ${APP_DIR}/.env"
else
    log_info "配置文件已存在，跳过"
fi

mkdir -p ${APP_DIR}/data/logs

# ========== 5. 创建 Systemd 服务 ==========
log_step "5/6 创建系统服务..."

cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Google AI Proxy Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment=PATH=${APP_DIR}/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
ExecStart=${APP_DIR}/venv/bin/python main.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}

log_info "服务已启动"

# ========== 6. 检查服务状态 ==========
log_step "6/6 验证服务..."

sleep 3

if systemctl is-active --quiet ${SERVICE_NAME}; then
    PORT=$(grep -oP 'PORT=\K\d+' ${APP_DIR}/.env 2>/dev/null || echo ${DEFAULT_PORT})
    
    echo ""
    echo "============================================"
    echo -e "   ${GREEN}部署成功！${NC}"
    echo "============================================"
    echo ""
    ADMIN_USER=$(grep -oP 'ADMIN_USERNAME=\K.*' ${APP_DIR}/.env 2>/dev/null || echo "admin")
    ADMIN_PASS=$(grep -oP 'ADMIN_PASSWORD=\K.*' ${APP_DIR}/.env 2>/dev/null || echo "${RANDOM_PASS}")
    SERVER_IP=$(hostname -I | awk '{print $1}')
    
    echo -e "  服务状态:  ${GREEN}运行中${NC}"
    echo -e "  管理后台:  ${BLUE}http://${SERVER_IP}:${PORT}/admin/${NC}"
    echo -e "  API 地址:  ${BLUE}http://${SERVER_IP}:${PORT}/v1/${NC}"
    echo -e "  健康检查:  ${BLUE}http://${SERVER_IP}:${PORT}/health${NC}"
    echo ""
    echo -e "  ${YELLOW}管理员账号:  ${ADMIN_USER}${NC}"
    echo -e "  ${YELLOW}管理员密码:  ${ADMIN_PASS}${NC}"
    echo ""
    echo "  常用命令:"
    echo "    查看状态:  systemctl status ${SERVICE_NAME}"
    echo "    查看日志:  journalctl -u ${SERVICE_NAME} -f"
    echo "    重启服务:  systemctl restart ${SERVICE_NAME}"
    echo "    停止服务:  systemctl stop ${SERVICE_NAME}"
    echo "    编辑配置:  nano ${APP_DIR}/.env"
    echo ""
    echo "  下一步:"
    echo "    1. 访问管理后台添加 Google 账户"
    echo "    2. 创建 API Key"
    echo "    3. 在客户端配置 API 地址和 Key"
    echo ""
else
    log_error "服务启动失败！"
    echo "查看错误日志: journalctl -u ${SERVICE_NAME} -n 50"
    systemctl status ${SERVICE_NAME} --no-pager || true
    exit 1
fi
