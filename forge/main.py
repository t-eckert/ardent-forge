import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Ardent Forge")


@app.get("/health")
async def health():
    return {"status": "ok"}


def run():
    uvicorn.run("forge.main:app", host="0.0.0.0", port=7030, reload=True)
