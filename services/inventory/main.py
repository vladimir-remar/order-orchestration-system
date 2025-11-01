from fastapi import FastAPI

app = FastAPI(title="Inventory Service")

@app.get("/health")
def health():
    return {"ok": True}
