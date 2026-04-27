import aiohttp
import logging
from typing import List, Dict
from config import Config

logger = logging.getLogger(__name__)

class LLMClient:
    @staticmethod
    async def generate_response(messages: List[Dict], temperature: float = None, top_p: float = None, max_tokens: int = None) -> str:
        payload = {
            "messages": messages,
            "temperature": temperature or Config.DEFAULT_TEMPERATURE,
            "top_p": top_p or Config.DEFAULT_TOP_P,
            "max_tokens": max_tokens or Config.DEFAULT_MAX_TOKENS,
            "stream": False
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(Config.LLM_API_URL, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'choices' in data and len(data['choices']) > 0:
                            return data['choices'][0]['message']['content']
                    
                    logger.error(f"LLM API error: {response.status}")
                    return "Извините, произошла ошибка при обращении к модели."
                    
        except Exception as e:
            logger.error(f"LLM Client error: {e}")
            return "Извините, сервис временно недоступен."
