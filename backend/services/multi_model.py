import asyncio
from typing import Dict, List, Optional

from services.ai_service import direct_completion

PRIMARY_PROVIDER = "google"
SECONDARY_PROVIDER = "anthropic"
BACKUP_PROVIDER = "deepseek"

FAILOVER_CHAIN = [
    "google",
    "anthropic",
    "deepseek",
    "groq",
    "ollama",
    "openai",
]


async def _call_provider(
    prompt: str,
    system_prompt: str,
    provider: str,
    model: Optional[str] = None,
) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    return await direct_completion(messages, provider=provider, model=model)


async def _call_with_fallback(
    prompt: str,
    system_prompt: str,
    chain: List[str],
) -> str:
    last_error = None
    for provider in chain:
        try:
            return await _call_provider(prompt, system_prompt, provider)
        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        return "Hmm, something interrupted my response. Want me to try that again?"
    return "I didn't finish that properly. Give me another shot."


async def multi_model_reasoning(
    prompt: str,
    system_prompt: str,
    primary: str = PRIMARY_PROVIDER,
    secondary: str = SECONDARY_PROVIDER,
    backup: str = BACKUP_PROVIDER,
) -> Dict[str, str]:
    tasks = [
        _call_provider(prompt, system_prompt, primary),
        _call_provider(prompt, system_prompt, secondary),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    answer_a = results[0] if isinstance(results[0], str) else ""
    answer_b = results[1] if isinstance(results[1], str) else ""

    if not answer_a:
        answer_a = await _call_with_fallback(prompt, system_prompt, FAILOVER_CHAIN)
    if not answer_b:
        answer_b = await _call_with_fallback(prompt, system_prompt, FAILOVER_CHAIN)

    combined_prompt = (
        "Two AI systems produced answers.\n\n"
        f"Answer A:\n{answer_a}\n\n"
        f"Answer B:\n{answer_b}\n\n"
        "Combine them into the most accurate response."
    )

    combined_chain = [backup] + [p for p in FAILOVER_CHAIN if p != backup]
    final_answer = await _call_with_fallback(combined_prompt, system_prompt, combined_chain)

    return {"answer": final_answer}


async def verify_answer(answer: str, context: str, system_prompt: str) -> str:
    verification_prompt = (
        "Verify the factual correctness of this answer using the web sources.\n\n"
        f"Answer:\n{answer}\n\n"
        f"Sources:\n{context}\n\n"
        "If something is incorrect, correct it and produce the final version."
    )

    return await _call_with_fallback(verification_prompt, system_prompt, FAILOVER_CHAIN)
