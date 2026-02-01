import time
from typing import Any

from openai import AsyncOpenAI

from workers.ai.providers.base import AIProvider, AIResponse, AIMessage


class OpenRouterProvider(AIProvider):

    def __init__(
        self,
        api_key: str,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        super().__init__(api_key, model)
        self.base_url = base_url
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={
                "HTTP-Referer": "https://news-intelligence-api.local",
                "X-Title": "News Intelligence API",
            },
        )

    @property
    def provider_name(self) -> str:
        return "openrouter"

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

    async def list_models(self) -> list[dict]:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            data = response.json()
            return data.get("data", [])
