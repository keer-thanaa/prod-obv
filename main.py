import time
import uuid
import json
from collections import deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

START_TIME = time.time()

# ---- In-memory counter (Prometheus text format) ----
REQUEST_COUNT = 0

# ---- In-memory structured log buffer ----
LOG_BUFFER = deque(maxlen=1000)


def add_log(level: str, path: str, request_id: str, **extra):
    entry = {
        "level": level,
        "ts": time.time(),
        "path": path,
        "request_id": request_id,
    }
    entry.update(extra)
    LOG_BUFFER.append(entry)
    return entry


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    global REQUEST_COUNT
    request_id = str(uuid.uuid4())
    path = request.url.path

    REQUEST_COUNT += 1

    response = await call_next(request)

    add_log(
        "info",
        path,
        request_id,
        method=request.method,
        status_code=response.status_code,
    )

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
def work(n: int = 1):
    """Do K units of 'work' (simple CPU loop) and return a result."""
    total = 0
    for i in range(max(n, 0)):
        total += i * i  # trivial work
    return {"email": "learner@example.com", "done": n}


@app.get("/metrics")
def metrics():
    body = (
        "# HELP http_requests_total Total number of HTTP requests.\n"
        "# TYPE http_requests_total counter\n"
        f"http_requests_total {REQUEST_COUNT}\n"
    )
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


@app.get("/healthz")
def healthz():
    uptime = time.time() - START_TIME
    return {"status": "ok", "uptime_s": max(uptime, 0.0)}


@app.get("/logs/tail")
def logs_tail(limit: int = 50):
    limit = max(1, min(limit, len(LOG_BUFFER) or 1))
    entries = list(LOG_BUFFER)[-limit:]
    return JSONResponse(content=entries)


@app.get("/")
def root():
    return {"status": "ok", "endpoints": ["/work", "/metrics", "/healthz", "/logs/tail"]}
