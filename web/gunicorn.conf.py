import os, multiprocessing

def cpu():
    return max(1, (os.cpu_count() or 1))

# Procesos (workers)
workers = min(max(2, cpu() * 2), 8)

# Threads por worker (para IO bloqueante)
worker_class = "gthread"
threads = int(os.getenv("GTHREADS", "4"))  # ajustable por env

# Timeouts
timeout = int(os.getenv("GUNI_TIMEOUT", "60"))
graceful_timeout = int(os.getenv("GUNI_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNI_KEEPALIVE", "5"))

# Robustez
preload_app = True
max_requests = int(os.getenv("GUNI_MAX_REQUESTS", "2000"))
max_requests_jitter = int(os.getenv("GUNI_MAX_REQUESTS_JITTER", "200"))

# Logging básico (puedes integrar JSON logger si quieres)
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNI_LOGLEVEL", "info")
