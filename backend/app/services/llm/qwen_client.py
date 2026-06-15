from pydantic import BaseModel


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""

    role: str
    content: str


class QwenClient:
    """Minimal Qwen/vLLM client facade."""

    def __init__(self, base_url: str, model_name: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key

    async def chat(self, messages: list[ChatMessage], enable_thinking: bool = False) -> str:
        """Return a placeholder response until vLLM integration is implemented."""

        _ = (messages, enable_thinking)
        return "[]"
