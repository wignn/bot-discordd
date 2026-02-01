import time
from typing import Any

from groq import AsyncGroq

from workers.ai.providers.base import AIProvider, AIResponse, AIMessage


class GroqProvider(AIProvider):

    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        super().__init__(api_key, model)
        self._client = AsyncGroq(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "groq"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> AIResponse:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})

        start_time = time.perf_counter()
        
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content or "",
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
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
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        start_time = time.perf_counter()

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        return AIResponse(
            content=response.choices[0].message.content or "",
            model=self.model,
            provider=self.provider_name,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            raw_response=response,
            latency_ms=latency_ms,
        )
