from fastapi import FastAPI

app = FastAPI(title="cineclock")


@app.get("/health")
def health():
    return {"status": "ok"}
