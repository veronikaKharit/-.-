import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

TRAINING_SERVICE_URL = os.getenv("TRAINING_SERVICE_URL", "http://localhost:8001")
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL", "http://localhost:8002")

app = FastAPI(title="Backend API")


class ScenarioCreate(BaseModel):
    name: str
    difficulty: int


class SessionCreate(BaseModel):
    userId: str
    scenarioId: str


class AnswerRequest(BaseModel):
    answerText: str


class ChatRequest(BaseModel):
    question: str


async def forward(method: str, url: str, payload: dict | None = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.request(method, url, json=payload)
    if response.status_code >= 400:
        detail = response.json().get("detail", "Service error")
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "backend-api"}


@app.post("/api/v1/scenarios")
async def create_scenario(data: ScenarioCreate):
    return await forward("POST", f"{TRAINING_SERVICE_URL}/scenarios", data.model_dump())


@app.get("/api/v1/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    return await forward("GET", f"{TRAINING_SERVICE_URL}/scenarios/{scenario_id}")


@app.post("/api/v1/sessions")
async def create_session(data: SessionCreate):
    return await forward("POST", f"{TRAINING_SERVICE_URL}/sessions", data.model_dump())


@app.get("/api/v1/sessions/{session_id}")
async def get_session(session_id: str):
    return await forward("GET", f"{TRAINING_SERVICE_URL}/sessions/{session_id}")


@app.post("/api/v1/sessions/{session_id}/answer")
async def send_answer(session_id: str, data: AnswerRequest):
    return await forward("POST", f"{TRAINING_SERVICE_URL}/sessions/{session_id}/answer", data.model_dump())


@app.put("/api/v1/sessions/{session_id}/finish")
async def finish_session(session_id: str):
    return await forward("PUT", f"{TRAINING_SERVICE_URL}/sessions/{session_id}/finish")


@app.post("/api/v1/chat/ask")
async def ask_chat(data: ChatRequest):
    return await forward("POST", f"{CHATBOT_SERVICE_URL}/chat/ask", data.model_dump())
