#!/bin/bash
#===============================================================================
# 视频派发网站 - PythonAnywhere 一键部署脚本
# 
# 使用方法：
#   1. 在 PythonAnywhere Bash 控制台运行：
#      bash <(curl -s https://raw.githubusercontent.com/pwy1230/video-dispatch/main/setup.sh)
#
#   或者手动一步步运行：
#      git clone https://github.com/pwy1230/video-dispatch.git
#      cd video-dispatch
#      bash setup.sh
#===============================================================================

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_step() {
    echo -e "\n${GREEN}==>${NC} $1"
}

echo_error() {
    echo -e "${RED}错误: $1${NC}"
    exit 1
}

echo_warning() {
    echo -e "${YELLOW}警告: $1${NC}"
}

# 检查是否在 PythonAnywhere 环境
if [[ ! "$PYTHONANYWHERE_DOMAIN" ]]; then
    echo_warning "检测到您可能不在 PythonAnywhere 环境中"
    echo "此脚本设计用于 PythonAnywhere Bash 控制台"
    read -p "是否继续？ (y/N): " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        exit 0
    fi
fi

echo_step "开始部署视频派发网站..."

# 1. 切换到项目目录
echo_step "1. 准备项目目录..."
PROJECT_DIR="$HOME/mysite"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
echo "项目目录: $PROJECT_DIR"

# 2. 检查 Git 状态
echo_step "2. 检查 Git 仓库..."
if [[ -d ".git" ]]; then
    echo "Git 仓库已存在，执行 pull 更新..."
    git pull origin main
else
    echo "正在克隆 GitHub 仓库..."
    read -p "请输入 GitHub 仓库URL（直接回车使用默认仓库）: " repo_url
    if [[ -z "$repo_url" ]]; then
        repo_url="https://github.com/pwy1230/video-dispatch.git"
    fi
    git clone "$repo_url" .
fi

# 3. 创建虚拟环境（如果需要）
echo_step "3. 设置 Python 虚拟环境..."
python3.11 -m venv venv
source venv/bin/activate

# 4. 安装依赖
echo_step "4. 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. 创建 .env 文件
echo_step "5. 配置环境变量..."
if [[ -f ".env" ]]; then
    echo_warning ".env 文件已存在，跳过创建"
else
    echo "请提供以下信息来创建 .env 文件："
    echo ""
    
    read -p "Cloudinary Cloud Name: " cloud_name
    read -p "Cloudinary API Key: " api_key
    read -s -p "Cloudinary API Secret: " api_secret
    echo ""
    
    # 生成随机密钥
    secret_key=$(python3 -c "import secrets; print(secrets.token_hex(24))")
    
    cat > .env << EOF
# Cloudinary 配置（必须）
CLOUDINARY_CLOUD_NAME=$cloud_name
CLOUDINARY_API_KEY=$api_key
CLOUDINARY_API_SECRET=$api_secret

# Flask 密钥（必须）
SECRET_KEY=$secret_key
EOF
    
    echo ".env 文件已创建"
fi

# 6. 初始化数据库
echo_step "6. 初始化 SQLite 数据库..."
python3 -c "from models import init_db; init_db()"
echo "数据库初始化完成"

# 7. 验证文件结构
echo_step "7. 验证部署..."
required_files=("app.py" "models.py" "wsgi.py" ".env" "video_dispatch.db")
for file in "${required_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "  ✓ $file"
    else
        echo_warning "  ⚠ $file 不存在"
    fi
done

# 8. 完成提示
echo ""
echo "============================================"
echo -e "${GREEN}✓ 部署完成！${NC}"
echo "============================================"
echo ""
echo "下一步操作："
echo ""
echo "1. 在 PythonAnywhere Web 面板配置 WSGI 文件："
echo "   - 进入 'Web' 标签页"
echo "   - 点击 'WSGI configuration file'"
echo "   - 删除原有内容，替换为："
echo ""
echo "   --- 复制以下内容 ---"
cat << 'EOF'
import os
import sys

project_home = os.path.expanduser('~/mysite')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.chdir(project_home)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, '.env'))

from app import app as application
EOF
echo "   --- 复制结束 ---"
echo ""
echo "2. 配置静态文件和路径："
echo "   - Static files: /static/ -> $HOME/mysite/static"
echo "   - Virtualenv: $HOME/mysite/venv"
echo ""
echo "3. 点击 'Reload Web App' 重启应用"
echo ""
echo "4. 访问你的网站：https://$PYTHONANYWHERE_USERNAME.pythonanywhere.com"
echo ""
echo "默认管理员账号：admin / admin123"
echo -e "${YELLOW}首次使用后请立即修改密码！${NC}"
echo ""
