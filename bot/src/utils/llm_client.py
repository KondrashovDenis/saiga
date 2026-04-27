import aiohttp
import logging
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)


class LLMClient:
    @staticmethod
    async def generate_response(
        messages: List[Dict],
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload = {
            "messages": messages,
            "temperature": temperature if temperature is not None else Config.DEFAULT_TEMPERATURE,
            "top_p": top_p if top_p is not None else Config.DEFAULT_TOP_P,
            "max_tokens": max_tokens if max_tokens is not None else Config.DEFAULT_MAX_TOKENS,
            "stream": False,
        }

        headers = {}
        if Config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {Config.LLM_API_KEY}"

        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(Config.LLM_API_URL, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'choices' in data and len(data['choices']) > 0:
                            return data['choices'][0]['message']['content']

                    body = await response.text()
                    logger.error("LLM API error: %s | body: %s", response.status, body[:300])
                    if response.status == 401:
                        return "Извините, не удаётся подключиться к модели (проблема авторизации)."
                    return "Извините, произошла ошибка при обращении к модели."

        except aiohttp.ClientError as e:
            logger.error("LLM Client network error: %s", e)
            return "Извините, сервис временно недоступен (сеть)."
        except Exception as e:
            logger.error("LLM Client error: %s", e)
            return "Извините, сервис временно недоступен."
