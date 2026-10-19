from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agent import analyze
from app.data import initialize_database, inspect_dataset, preview_rows


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="DataPilot Agent", description="A tool-using data analyst with a read-only SQL boundary and inspectable trace.", version="0.1.0", lifespan=lifespan)


class AnalyzeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/dataset")
def dataset_info() -> dict:
    return inspect_dataset()


@app.get("/dataset/preview")
def dataset_preview(limit: int = 5) -> dict:
    return preview_rows(limit)


@app.post("/analyze")
def analyze_question(request: AnalyzeRequest) -> dict:
    try:
        return analyze(request.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
