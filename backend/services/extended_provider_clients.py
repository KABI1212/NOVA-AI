"""
Extended Provider Clients - Additional AI provider support.

This module adds support for new AI providers while maintaining backward compatibility:
- Mistral AI
- Grok (xAI)
- Together AI  
- Ollama (extended support)
- Future providers

Each provider integrates with the existing NOVA architecture without modifying
existing code or breaking compatibility.
"""

import os
import logging
from typing import Optional, List, Dict, Any

import httpx

from config.settings import settings
from services.ai_service import direct_completion

logger = logging.getLogger(__name__)

# Extended model defaults
EXTENDED_PROVIDER_MODELS = {
    "mistral": "mistral-large-latest",
    "grok": "grok-2-1212",
    "together": "meta-llama/Llama-3-70b-chat-hf",
    "ollama_extended": "neural-chat",
}

# Provider endpoints
PROVIDER_ENDPOINTS = {
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "grok": "https://api.x.ai/v1/chat/completions",
    "together": "https://api.together.xyz/v1/chat/completions",
}


def _build_messages(system_prompt: str, prompt: str) -> List[Dict[str, str]]:
    """Build message list for provider."""
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]


async def ask_mistral(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Query Mistral AI for a response.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt
        model: Optional model override
        
    Returns:
        Response text
    """
    try:
        messages = _build_messages(system_prompt, prompt)
        model_name = model or getattr(settings, "MISTRAL_MODEL", "") or EXTENDED_PROVIDER_MODELS["mistral"]
        
        api_key = os.getenv("MISTRAL_API_KEY") or getattr(settings, "MISTRAL_API_KEY", "")
        if not api_key:
            logger.error("Missing MISTRAL_API_KEY")
            return ""
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
            "top_p": 1.0,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                PROVIDER_ENDPOINTS["mistral"],
                headers=headers,
                json=payload,
            )
        
        if response.status_code >= 400:
            logger.error(f"Mistral API error: {response.status_code} - {response.text}")
            return ""
        
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        
        message = choices[0].get("message", {})
        return message.get("content", "").strip()
    
    except Exception as e:
        logger.error(f"Mistral request error: {e}")
        return ""


async def ask_grok(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Query Grok (xAI) for a response.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt
        model: Optional model override
        
    Returns:
        Response text
    """
    try:
        messages = _build_messages(system_prompt, prompt)
        model_name = model or getattr(settings, "GROK_MODEL", "") or EXTENDED_PROVIDER_MODELS["grok"]
        
        api_key = os.getenv("GROK_API_KEY") or getattr(settings, "GROK_API_KEY", "")
        if not api_key:
            logger.error("Missing GROK_API_KEY")
            return ""
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                PROVIDER_ENDPOINTS["grok"],
                headers=headers,
                json=payload,
            )
        
        if response.status_code >= 400:
            logger.error(f"Grok API error: {response.status_code} - {response.text}")
            return ""
        
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        
        message = choices[0].get("message", {})
        return message.get("content", "").strip()
    
    except Exception as e:
        logger.error(f"Grok request error: {e}")
        return ""


async def ask_together(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Query Together AI for a response.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt
        model: Optional model override
        
    Returns:
        Response text
    """
    try:
        messages = _build_messages(system_prompt, prompt)
        model_name = model or getattr(settings, "TOGETHER_MODEL", "") or EXTENDED_PROVIDER_MODELS["together"]
        
        api_key = os.getenv("TOGETHER_API_KEY") or getattr(settings, "TOGETHER_API_KEY", "")
        if not api_key:
            logger.error("Missing TOGETHER_API_KEY")
            return ""
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
            "top_p": 1.0,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                PROVIDER_ENDPOINTS["together"],
                headers=headers,
                json=payload,
            )
        
        if response.status_code >= 400:
            logger.error(f"Together API error: {response.status_code} - {response.text}")
            return ""
        
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        
        message = choices[0].get("message", {})
        return message.get("content", "").strip()
    
    except Exception as e:
        logger.error(f"Together request error: {e}")
        return ""


async def ask_openrouter(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None
) -> str:
    """
    Query OpenRouter for a response (meta-router to many models).
    
    Args:
        prompt: User prompt
        system_prompt: System prompt
        model: Optional model override
        
    Returns:
        Response text
    """
    try:
        messages = _build_messages(system_prompt, prompt)
        model_name = model or getattr(settings, "OPENROUTER_MODEL", "") or "gpt-4o-mini"
        
        api_key = os.getenv("OPENROUTER_API_KEY") or getattr(settings, "OPENROUTER_API_KEY", "")
        if not api_key:
            logger.error("Missing OPENROUTER_API_KEY")
            return ""
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": getattr(settings, "OPENROUTER_REFERER", "http://localhost:3000"),
            "X-Title": getattr(settings, "OPENROUTER_APP_NAME", "NOVA AI"),
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
        
        if response.status_code >= 400:
            logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
            return ""
        
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            return ""
        
        message = choices[0].get("message", {})
        return message.get("content", "").strip()
    
    except Exception as e:
        logger.error(f"OpenRouter request error: {e}")
        return ""


async def ask_ollama_extended(
    prompt: str,
    system_prompt: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None
) -> str:
    """
    Query local Ollama instance with extended support.
    
    Args:
        prompt: User prompt
        system_prompt: System prompt
        model: Optional model override
        base_url: Optional Ollama base URL
        
    Returns:
        Response text
    """
    try:
        messages = _build_messages(system_prompt, prompt)
        model_name = model or getattr(settings, "OLLAMA_MODEL", "") or EXTENDED_PROVIDER_MODELS["ollama_extended"]
        
        ollama_url = base_url or getattr(settings, "OLLAMA_BASE_URL", "") or "http://localhost:11434"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "temperature": 0.3,
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{ollama_url}/api/chat",
                headers=headers,
                json=payload,
            )
        
        if response.status_code >= 400:
            logger.error(f"Ollama error: {response.status_code} - {response.text}")
            return ""
        
        data = response.json()
        return data.get("message", {}).get("content", "").strip()
    
    except Exception as e:
        logger.error(f"Ollama request error: {e}")
        return ""


async def get_provider_status(provider: str) -> Dict[str, Any]:
    """
    Get the availability and status of a provider.
    
    Args:
        provider: Provider name
        
    Returns:
        Status dictionary
    """
    status = {
        "provider": provider,
        "available": False,
        "reason": "Unknown",
    }
    
    try:
        if provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY") or getattr(settings, "MISTRAL_API_KEY", "")
            status["available"] = bool(api_key)
            if not api_key:
                status["reason"] = "Missing MISTRAL_API_KEY"
        
        elif provider == "grok":
            api_key = os.getenv("GROK_API_KEY") or getattr(settings, "GROK_API_KEY", "")
            status["available"] = bool(api_key)
            if not api_key:
                status["reason"] = "Missing GROK_API_KEY"
        
        elif provider == "together":
            api_key = os.getenv("TOGETHER_API_KEY") or getattr(settings, "TOGETHER_API_KEY", "")
            status["available"] = bool(api_key)
            if not api_key:
                status["reason"] = "Missing TOGETHER_API_KEY"
        
        elif provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY") or getattr(settings, "OPENROUTER_API_KEY", "")
            status["available"] = bool(api_key)
            if not api_key:
                status["reason"] = "Missing OPENROUTER_API_KEY"
        
        elif provider == "ollama":
            ollama_url = getattr(settings, "OLLAMA_BASE_URL", "") or "http://localhost:11434"
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get(f"{ollama_url}/api/tags")
                    status["available"] = response.status_code == 200
                    if not status["available"]:
                        status["reason"] = f"Ollama unreachable at {ollama_url}"
            except:
                status["available"] = False
                status["reason"] = f"Cannot reach Ollama at {ollama_url}"
    
    except Exception as e:
        status["reason"] = str(e)
    
    return status


async def get_all_extended_providers_status() -> Dict[str, Dict[str, Any]]:
    """
    Get status of all extended providers.
    
    Returns:
        Dictionary with provider statuses
    """
    providers = ["mistral", "grok", "together", "openrouter", "ollama"]
    results = {}
    
    for provider in providers:
        results[provider] = await get_provider_status(provider)
    
    return results
