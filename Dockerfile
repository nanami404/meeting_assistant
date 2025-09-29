# 使用官方 Python 3.12-slim 镜像作为基础镜像（更小体积）
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 设置系统时区为 Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

# 替换 APT 软件源为清华大学开源镜像站
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# 安装系统级依赖和音频处理库
RUN apt-get update && apt-get install -y \
    # PyAudio 和音频处理依赖
    portaudio19-dev \
    alsa-utils \
    libasound2-dev \
    # Python 编译依赖
    python3-dev \
    gcc \
    g++ \
    # 其他必要工具
    pkg-config \
    libffi-dev \
    # 图像处理依赖（Pillow）
    libjpeg-dev \
    libpng-dev \
    # FFmpeg 依赖（音频转换）
    ffmpeg \
    # 清理缓存
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 创建必要的目录
RUN mkdir -p /app/static /app/temp /app/temp_audio /app/uploads /app/logs

# 先复制依赖文件（利用Docker构建缓存）
COPY requirements.txt .
COPY logging.yml .

# 安装Python依赖（使用清华源加速）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目源代码
COPY . .

# 创建非root用户运行应用
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/docs', timeout=5)" || exit 1

# 启动应用
CMD ["python", "main.py"]