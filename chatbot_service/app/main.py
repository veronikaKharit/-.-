from abc import ABC, abstractmethod
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Chatbot Service")


class ChatRequest(BaseModel):
    question: str


class ExternalLLMApi:
    def send_prompt(self, payload: dict) -> dict:
        question = payload.get("prompt", "")
        return {"text": f"LLM-ответ на вопрос: {question}"}


class LLMClient(ABC):
    @abstractmethod
    def ask(self, question: str) -> str:
        raise NotImplementedError


class LLMAdapter(LLMClient):
    def __init__(self, external_api: ExternalLLMApi):
        self._external_api = external_api

    def ask(self, question: str) -> str:
        result = self._external_api.send_prompt({"prompt": question})
        return result["text"]


class AnalyticsProxy:
    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def send(self, event_name: str, payload: dict):
        if self._enabled:
            print(f"[CHAT-ANALYTICS] {event_name}: {payload}")


class KnowledgeRetriever:
    def find_context(self, question: str) -> str:
        if "скид" in question.lower():
            return "В базе знаний найден раздел про скидки и спецпредложения."
        return "В базе знаний найден общий раздел по работе с клиентом."


class BaseChatHandler(ABC):
    def handle(self, question: str) -> dict:
        context = self.retrieve_context(question)
        answer = self.generate_answer(question, context)
        self.after_answer(question, answer)
        return {"question": question, "context": context, "answer": answer}

    @abstractmethod
    def retrieve_context(self, question: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_answer(self, question: str, context: str) -> str:
        raise NotImplementedError

    def after_answer(self, question: str, answer: str):
        pass


class RetrievalAugmentedChatHandler(BaseChatHandler):
    def __init__(self, retriever: KnowledgeRetriever, llm_client: LLMClient, analytics: AnalyticsProxy):
        self._retriever = retriever
        self._llm_client = llm_client
        self._analytics = analytics

    def retrieve_context(self, question: str) -> str:
        return self._retriever.find_context(question)

    def generate_answer(self, question: str, context: str) -> str:
        return self._llm_client.ask(f"Контекст: {context}. Вопрос: {question}")

    def after_answer(self, question: str, answer: str):
        self._analytics.send("chat_answered", {"question": question, "answer": answer})


handler = RetrievalAugmentedChatHandler(
    retriever=KnowledgeRetriever(),
    llm_client=LLMAdapter(ExternalLLMApi()),
    analytics=AnalyticsProxy(enabled=True),
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "chatbot-service"}


@app.post("/chat/ask")
def ask_chatbot(data: ChatRequest):
    return handler.handle(data.question)
