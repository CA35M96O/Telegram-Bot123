# 使用官方 Python 运行时作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建日志和备份目录
RUN mkdir -p logs backups

# 暴露端口（如果机器人需要 webhook 模式）
EXPOSE 8443

# 设置环境变量
ENV PYTHONPATH=/app

# 启动机器人
CMD ["python", "main.py"]