"""
Gemini LLM Client for Intelligence Service

Uses the new google-genai SDK (replaces deprecated google-generativeai).
Documentation: https://googleapis.github.io/python-genai/
"""

import json
import re
from typing import Optional, Any
from functools import lru_cache

from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import get_settings


settings = get_settings()


class GeminiClient:
    """
    Async Gemini client using google-genai SDK.
    
    Provides:
    - Text completion (async)
    - Structured JSON extraction (async)
    - Retry logic with exponential backoff
    - Model selection (Pro for quality, Flash for speed)
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Gemini client.
        
        Args:
            model: Model name (default: gemini-3-flash-preview)
            api_key: Google API key (default: from settings)
        """
        self.api_key = api_key or settings.google_api_key
        self.model = model or settings.gemini_model_flash
        
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not configured")
        
        # Create client with aiohttp for faster async
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={"api_version": "v1beta"},
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_instruction: Optional[str] = None,
    ) -> str:
        """
        Generate text completion asynchronously.
        
        Args:
            prompt: The prompt to complete
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum response tokens
            system_instruction: Optional system prompt
            
        Returns:
            Generated text
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        if system_instruction:
            config.system_instruction = system_instruction
        
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        
        return response.text
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def extract_json(
        self,
        prompt: str,
        temperature: float = 0.3,
    ) -> dict:
        """
        Extract structured JSON from prompt response.
        
        Uses JSON response format for reliable parsing.
        
        Args:
            prompt: The prompt requesting JSON
            temperature: Lower for consistency
            
        Returns:
            Parsed JSON object
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        )
        
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        
        return json.loads(response.text)
    
    async def check_connection(self) -> bool:
        """
        Test the Gemini API connection.
        
        Returns:
            True if working
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents="Say 'OK' if you're working.",
            )
            return "ok" in response.text.lower()
        except Exception as e:
            raise Exception(f"Gemini connection failed: {e}")
    
    @classmethod
    def get_pro_client(cls) -> "GeminiClient":
        """Get client configured for Gemini 3 Pro (quality)."""
        return cls(model=settings.gemini_model_pro)
    
    @classmethod
    def get_flash_client(cls) -> "GeminiClient":
        """Get client configured for Gemini 3 Flash (speed)."""
        return cls(model=settings.gemini_model_flash)


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Get cached default Gemini client."""
    return GeminiClient()


async def quick_complete(prompt: str, temperature: float = 0.7) -> str:
    """
    Quick async completion using Flash model.
    
    Convenience function for simple completions.
    """
    client = get_gemini_client()
    return await client.complete(prompt, temperature)
