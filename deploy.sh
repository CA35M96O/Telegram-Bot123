#!/bin/bash

# Telegram Bot 一键部署脚本
# 支持 Linux 和 macOS 系统

set -e  # 遇到错误时停止执行

echo "🚀 开始部署 Telegram Bot..."

# 检查是否安装了 Python
if ! command -v python3 &> /dev/null
then
    echo "❌ 未找到 Python3，请先安装 Python3"
    exit 1
fi

# 检查是否安装了 Git
if ! command -v git &> /dev/null
then
    echo "❌ 未找到 Git，请先安装 Git"
    exit 1
fi

echo "✅ 环境检查通过"

# 克隆或更新代码
if [ -d "telegram-bot" ]; then
    echo "🔄 更新现有代码..."
    cd telegram-bot
    git pull
else
    echo "📥 克隆代码仓库..."
    git clone https://github.com/CA35M96O/Telegram-Bot123.git telegram-bot
    cd telegram-bot
fi

# 创建虚拟环境
echo "🔧 创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 检查是否存在 .env 文件
if [ ! -f ".env" ]; then
    echo "📋 复制配置模板..."
    cp .env.example .env
    echo "⚠️  请编辑 .env 文件，填入实际配置参数"
    echo "   编辑完成后重新运行此脚本"
    exit 0
fi

echo "✅ 部署完成！"
echo ""
echo "启动机器人命令："
echo "  cd telegram-bot && source venv/bin/activate && python main.py"
echo ""
echo "后台运行命令："
echo "  cd telegram-bot && source venv/bin/activate && nohup python main.py > bot.log 2>&1 &"