@echo off
REM Telegram Bot Windows 一键部署脚本

echo 🚀 开始部署 Telegram Bot...

REM 检查是否安装了 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装 Python
    pause
    exit /b 1
)

REM 检查是否安装了 Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Git，请先安装 Git
    pause
    exit /b 1
)

echo ✅ 环境检查通过

REM 克隆或更新代码
if exist "telegram-bot" (
    echo 🔄 更新现有代码...
    cd telegram-bot
    git pull
) else (
    echo 📥 克隆代码仓库...
    git clone https://github.com/CA35M96O/Telegram-Bot123.git telegram-bot
    cd telegram-bot
)

REM 创建虚拟环境
echo 🔧 创建虚拟环境...
python -m venv venv
call venv\Scripts\activate

REM 安装依赖
echo 📦 安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM 检查是否存在 .env 文件
if not exist ".env" (
    echo 📋 复制配置模板...
    copy .env.example .env
    echo ⚠️  请编辑 .env 文件，填入实际配置参数
    echo    编辑完成后重新运行此脚本
    pause
    exit /b 0
)

echo ✅ 部署完成！
echo.
echo 启动机器人命令：
echo   cd telegram-bot && call venv\Scripts\activate && python main.py
echo.
pause