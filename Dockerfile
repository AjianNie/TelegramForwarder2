# ---- 阶段 1: 构建器 (Builder) ----
# 使用与最终阶段相同的基础镜像，以确保兼容性
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装构建时所需的系统依赖
# gcc 和 python3-dev 用于编译一些Python库
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装到一个独立的虚拟环境中
# 这样做可以轻松地将整个环境复制到下一阶段
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# ---- 阶段 2: 最终镜像 (Final Image) ----
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装运行时所需的最小系统依赖
# tzdata 用于时区设置
RUN apt-get update && apt-get install -y \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 从构建器阶段复制已安装的Python虚拟环境
# 这样就无需在最终镜像中保留gcc等构建工具
COPY --from=builder /opt/venv /opt/venv

# 复制应用代码
COPY . .

# 创建临时文件目录
RUN mkdir -p /app/temp

# 设置环境变量，确保Python使用虚拟环境中的解释器
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["python", "main.py"]
