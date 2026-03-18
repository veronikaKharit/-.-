from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from uuid import uuid4

app = FastAPI(title="Training Service")

# =========================
# GoF patterns in code base
# =========================

class AppConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.service_name = "training-service"
            cls._instance.default_generation_mode = "training"
        return cls._instance


@dataclass
class EvaluationResult:
    completeness: int
    correctness: int
    comment: str


class AnswerEvaluator(ABC):
    @abstractmethod
    def evaluate(self, answer_text: str, expected_intent: str) -> EvaluationResult:
        raise NotImplementedError


class KeywordAnswerEvaluator(AnswerEvaluator):
    def evaluate(self, answer_text: str, expected_intent: str) -> EvaluationResult:
        completeness = 100 if answer_text.strip() else 0
        correctness = 100 if expected_intent.lower() in answer_text.lower() else 50
        comment = "Ответ соответствует ожидаемому намерению" if correctness == 100 else "Нужно точнее раскрыть потребность клиента"
        return EvaluationResult(completeness, correctness, comment)


class StrictAnswerEvaluator(AnswerEvaluator):
    def evaluate(self, answer_text: str, expected_intent: str) -> EvaluationResult:
        completeness = 100 if len(answer_text.strip()) > 20 else 40
        correctness = 100 if expected_intent.lower() in answer_text.lower() else 20
        comment = "Экзаменационная проверка пройдена" if correctness == 100 else "Ответ слишком слабый для экзаменационного режима"
        return EvaluationResult(completeness, correctness, comment)


class LoggingEvaluator(AnswerEvaluator):
    def __init__(self, wrapped: AnswerEvaluator):
        self._wrapped = wrapped

    def evaluate(self, answer_text: str, expected_intent: str) -> EvaluationResult:
        result = self._wrapped.evaluate(answer_text, expected_intent)
        print(f"[LOG] evaluated answer='{answer_text}' result={result}")
        return result


class EvaluatorFactory:
    def create(self, mode: str) -> AnswerEvaluator:
        if mode == "exam":
            return LoggingEvaluator(StrictAnswerEvaluator())
        return LoggingEvaluator(KeywordAnswerEvaluator())


class SessionState(ABC):
    name: str

    @abstractmethod
    def can_answer(self) -> bool:
        raise NotImplementedError


class ActiveState(SessionState):
    name = "ACTIVE"

    def can_answer(self) -> bool:
        return True


class CompletedState(SessionState):
    name = "COMPLETED"

    def can_answer(self) -> bool:
        return False


class Command(ABC):
    @abstractmethod
    def execute(self):
        raise NotImplementedError


class EventSubscriber(ABC):
    @abstractmethod
    def update(self, event_name: str, payload: dict):
        raise NotImplementedError


class AnalyticsSubscriber(EventSubscriber):
    def update(self, event_name: str, payload: dict):
        print(f"[ANALYTICS] {event_name}: {payload}")


class EventPublisher:
    def __init__(self):
        self._subscribers: List[EventSubscriber] = []

    def subscribe(self, subscriber: EventSubscriber):
        self._subscribers.append(subscriber)

    def publish(self, event_name: str, payload: dict):
        for subscriber in self._subscribers:
            subscriber.update(event_name, payload)


publisher = EventPublisher()
publisher.subscribe(AnalyticsSubscriber())

# =========================
# Storage / GRASP examples
# =========================

class ScenarioCreate(BaseModel):
    name: str
    difficulty: int


class SessionCreate(BaseModel):
    userId: str
    scenarioId: str
    mode: str = "training"


class AnswerRequest(BaseModel):
    answerText: str


class ScenarioRepository:
    def __init__(self):
        self._data: Dict[str, dict] = {}

    def create(self, name: str, difficulty: int) -> dict:
        scenario_id = f"scn-{uuid4().hex[:8]}"
        scenario = {
            "id": scenario_id,
            "name": name,
            "difficulty": difficulty,
            "expected_intent": "выявление потребностей",
        }
        self._data[scenario_id] = scenario
        return scenario

    def get(self, scenario_id: str) -> dict | None:
        return self._data.get(scenario_id)


class SessionRepository:
    def __init__(self):
        self._data: Dict[str, dict] = {}

    def create(self, user_id: str, scenario: dict, mode: str) -> dict:
        session_id = f"ses-{uuid4().hex[:8]}"
        session = {
            "id": session_id,
            "userId": user_id,
            "scenarioId": scenario["id"],
            "scenarioName": scenario["name"],
            "status": ActiveState().name,
            "mode": mode,
            "turns": [],
            "lastEvaluation": None,
        }
        self._data[session_id] = session
        return session

    def get(self, session_id: str) -> dict | None:
        return self._data.get(session_id)

    def save_answer(self, session_id: str, answer_text: str, result: EvaluationResult):
        session = self._data[session_id]
        session["turns"].append({"speaker": "trainee", "text": answer_text})
        session["lastEvaluation"] = {
            "completeness": result.completeness,
            "correctness": result.correctness,
            "comment": result.comment,
        }
        return session

    def finish(self, session_id: str):
        self._data[session_id]["status"] = CompletedState().name
        return self._data[session_id]


scenario_repository = ScenarioRepository()
session_repository = SessionRepository()


class TrainingSessionService:
    def __init__(self, scenario_repo: ScenarioRepository, session_repo: SessionRepository, factory: EvaluatorFactory):
        self._scenario_repo = scenario_repo
        self._session_repo = session_repo
        self._factory = factory

    def create_scenario(self, name: str, difficulty: int) -> dict:
        return self._scenario_repo.create(name, difficulty)

    def get_scenario(self, scenario_id: str) -> dict | None:
        return self._scenario_repo.get(scenario_id)

    def create_session(self, user_id: str, scenario_id: str, mode: str) -> dict:
        scenario = self._scenario_repo.get(scenario_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")
        session = self._session_repo.create(user_id, scenario, mode)
        publisher.publish("session_created", session)
        return session

    def get_session(self, session_id: str) -> dict:
        session = self._session_repo.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    def handle_answer(self, session_id: str, answer_text: str) -> dict:
        session = self.get_session(session_id)
        state = ActiveState() if session["status"] == "ACTIVE" else CompletedState()
        if not state.can_answer():
            raise HTTPException(status_code=400, detail="Session already completed")

        scenario = self._scenario_repo.get(session["scenarioId"])
        evaluator = self._factory.create(session["mode"])
        result = evaluator.evaluate(answer_text, scenario["expected_intent"])
        updated = self._session_repo.save_answer(session_id, answer_text, result)
        publisher.publish("answer_received", {"sessionId": session_id, "evaluation": updated["lastEvaluation"]})
        return updated

    def finish_session(self, session_id: str) -> dict:
        self.get_session(session_id)
        updated = self._session_repo.finish(session_id)
        publisher.publish("session_completed", updated)
        return updated


service = TrainingSessionService(scenario_repository, session_repository, EvaluatorFactory())


class StartSessionCommand(Command):
    def __init__(self, service: TrainingSessionService, user_id: str, scenario_id: str, mode: str):
        self._service = service
        self._user_id = user_id
        self._scenario_id = scenario_id
        self._mode = mode

    def execute(self):
        return self._service.create_session(self._user_id, self._scenario_id, self._mode)


class SendAnswerCommand(Command):
    def __init__(self, service: TrainingSessionService, session_id: str, answer_text: str):
        self._service = service
        self._session_id = session_id
        self._answer_text = answer_text

    def execute(self):
        return self._service.handle_answer(self._session_id, self._answer_text)


@app.get("/health")
def health():
    config = AppConfig()
    return {"status": "ok", "service": config.service_name}


@app.post("/scenarios")
def create_scenario(data: ScenarioCreate):
    return service.create_scenario(data.name, data.difficulty)


@app.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    scenario = service.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@app.post("/sessions")
def create_session(data: SessionCreate):
    command = StartSessionCommand(service, data.userId, data.scenarioId, data.mode)
    return command.execute()


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    return service.get_session(session_id)


@app.post("/sessions/{session_id}/answer")
def send_answer(session_id: str, data: AnswerRequest):
    command = SendAnswerCommand(service, session_id, data.answerText)
    return command.execute()


@app.put("/sessions/{session_id}/finish")
def finish_session(session_id: str):
    return service.finish_session(session_id)
