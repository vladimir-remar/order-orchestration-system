import os

host = "0.0.0.0"
port = int(os.getenv("PORT", "9001"))
workers = int(os.getenv("UVICORN_WORKERS", str(max(2, (os.cpu_count() or 1)))))
loop = "uvloop"  # requiere uvicorn[standard]
http = "h11"
log_level = os.getenv("LOG_LEVEL", "info")
