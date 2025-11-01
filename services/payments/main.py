from fastapi import FastAPI

app = FastAPI(title="Payments Service")

@app.get("/health")
def health():
    return {"ok": True}
