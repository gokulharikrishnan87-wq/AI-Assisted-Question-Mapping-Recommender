"""FastAPI application for interactive and batch mapping suggestions."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator

from mapper_copilot.core.suggester import Suggester
from mapper_copilot.models import Mapping
from mapper_copilot.providers.embeddings import HashingEmbedder
from mapper_copilot.providers.llm import MockLLM
from mapper_copilot.providers.vector_store import NumpyVectorStore

API_VERSION = "1.0.0"
API_DESCRIPTION = "RSC to SLCP question mapper"
DEFAULT_SOURCE_CANDIDATES = [
    "Operating license/registration is available and up to date",
    "Worker contracts are maintained and signed",
    "Emergency exits are clearly marked and unobstructed",
    "Workers are paid accurately and on time",
    "Workers have access to a grievance mechanism",
]

suggester: Optional[Suggester] = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize_suggester()
    yield


app = FastAPI(title="Mapper Copilot API", version=API_VERSION, lifespan=lifespan)


class SuggestRequest(BaseModel):
    """Request payload for a single mapping suggestion."""

    rsc_question: str

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("rsc_question")
    @classmethod
    def validate_rsc_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rsc_question must not be empty")
        return value.strip()


class SuggestResponse(BaseModel):
    """Response payload for a single mapping suggestion."""

    rsc_question: str
    mapped_to: str
    confidence: float
    rule: str
    source_candidates: List[str]


class BatchSuggestRequest(BaseModel):
    """Request payload for batch mapping suggestions."""

    rsc_questions: List[str]

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("rsc_questions")
    @classmethod
    def validate_rsc_questions(cls, values: List[str]) -> List[str]:
        if not values:
            raise ValueError("rsc_questions must contain at least one question")
        cleaned_values = []
        for index, value in enumerate(values):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"rsc_questions[{index}] must not be empty")
            cleaned_values.append(value.strip())
        return cleaned_values


class BatchSuggestResponse(BaseModel):
    """Response payload for batch mapping suggestions."""

    results: List[SuggestResponse]


def _build_suggester() -> Suggester:
    embedder = HashingEmbedder()
    vector_store = NumpyVectorStore()
    vector_store.index(
        vectors=embedder.batch_embed(DEFAULT_SOURCE_CANDIDATES),
        metadata=[{"question": candidate} for candidate in DEFAULT_SOURCE_CANDIDATES],
    )
    return Suggester(
        embedding_provider=embedder,
        llm_provider=MockLLM(),
        vector_store=vector_store,
    )


def initialize_suggester() -> None:
    """Create the global suggester with deterministic mock providers."""

    global suggester
    suggester = _build_suggester()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        message = error.get("msg", "Invalid request")
        details.append(f"{location}: {message}" if location else message)
    return JSONResponse(status_code=400, content={"detail": "; ".join(details)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {exc}"})


def get_suggester() -> Suggester:
    """Return the initialized suggester instance."""

    global suggester
    if suggester is None:
        suggester = _build_suggester()
    return suggester


def _to_response(mapping: Mapping) -> SuggestResponse:
    return SuggestResponse(**mapping.model_dump())


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@app.get("/info")
def info() -> dict[str, str]:
    """Return basic API metadata."""

    return {"version": API_VERSION, "description": API_DESCRIPTION}


@app.post("/suggest", response_model=SuggestResponse)
def suggest(request: SuggestRequest) -> SuggestResponse:
    """Return a single mapping suggestion."""

    try:
        return _to_response(get_suggester().suggest(request.rsc_question))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate suggestion: {exc}"
        ) from exc


@app.post("/suggest-batch", response_model=BatchSuggestResponse)
def suggest_batch(request: BatchSuggestRequest) -> BatchSuggestResponse:
    """Return mapping suggestions for multiple questions."""

    try:
        return BatchSuggestResponse(
            results=[
                _to_response(mapping)
                for mapping in get_suggester().suggest_batch(request.rsc_questions)
            ]
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate suggestions: {exc}"
        ) from exc


__all__ = [
    "app",
    "BatchSuggestRequest",
    "BatchSuggestResponse",
    "SuggestRequest",
    "SuggestResponse",
    "get_suggester",
    "initialize_suggester",
]
