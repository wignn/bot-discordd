import time
from typing import Any

import google.generativeai as genai

from workers.ai.providers.base import AIProvider, AIResponse, AIMessage


class GeminiProvider(AIProvider):
    """
    Gemini AI Provider with lazy initialization.
    
    The gRPC client is initialized lazily to avoid issues with Celery's
    fork-based multiprocessing. gRPC connections don't survive fork().
    """

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        super().__init__(api_key, model)
        self._api_key = api_key
        self._client = None
        self._configured = False
    
    def _ensure_client(self):
        """Lazy initialization of the Gemini client."""
        if self._client is None or not self._configured:
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self.model)
            self._configured = True
        return self._client

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AIResponse:
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        start_time = time.perf_counter()

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        client = self._ensure_client()
        response = await client.generate_content_async(
            full_prompt,
            generation_config=generation_config,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        usage = {}
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(response.usage_metadata, 'total_token_count', 0),
            }

        return AIResponse(
            content=response.text if response.text else "",
            model=self.model,
            provider=self.provider_name,
            usage=usage,
            raw_response=response,
            latency_ms=latency_ms,
        )

    async def chat(
        self,
        messages: list[AIMessage],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AIResponse:
        client = self._ensure_client()
        chat = client.start_chat(history=[])
        
        start_time = time.perf_counter()

        system_content = ""
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
                break

        last_response = None
        for msg in messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                content = msg.content
                if system_content and msg == messages[-1]:
                    content = f"{system_content}\n\n{content}"
                last_response = await chat.send_message_async(content)

        latency_ms = (time.perf_counter() - start_time) * 1000

        if last_response is None:
            raise ValueError("No user messages provided")

        usage = {}
        if hasattr(last_response, 'usage_metadata') and last_response.usage_metadata:
            usage = {
                "prompt_tokens": getattr(last_response.usage_metadata, 'prompt_token_count', 0),
                "completion_tokens": getattr(last_response.usage_metadata, 'candidates_token_count', 0),
                "total_tokens": getattr(last_response.usage_metadata, 'total_token_count', 0),
            }

        return AIResponse(
            content=last_response.text if last_response.text else "",
            model=self.model,
            provider=self.provider_name,
            usage=usage,
            raw_response=last_response,
            latency_ms=latency_ms,
        )
