FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p instance uploads

EXPOSE 5000

# 单进程 + 多线程: SQLite 与 service_factory 内存缓存均不支持多进程共享,
# 并发安全由应用内按文件加锁保证
CMD ["gunicorn", "-w", "1", "--threads", "8", "-b", "0.0.0.0:5000", "--timeout", "300", "app:app"]
