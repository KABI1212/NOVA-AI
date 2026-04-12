from typing import Dict, List, Tuple

from services.provider_clients import ask_provider

EVALUATOR_CHAIN = [
    "openai",
    "anthropic",
    "google",
    "deepseek",
    "groq",
    "ollama",
]


async def _call_with_fallback(prompt: str, system_prompt: str) -> Tuple[str, str]:
    for provider in EVALUATOR_CHAIN:
        try:
            response = await ask_provider(provider, prompt, system_prompt)
            if response:
                return response, provider
        except Exception:
            continue
    return "", ""


def _format_answers(answers: List[Dict]) -> str:
    blocks = []
    for idx, item in enumerate(answers, start=1):
        label = chr(64 + idx) if idx <= 26 else str(idx)
        blocks.append(f"Answer {label}:\n{item.get('text', '')}")
    return "\n\n".join(blocks)


async def evaluate_answers(question: str, answers: List[Dict], system_prompt: str) -> Tuple[str, str]:
    prompt = (
        "Two or more AI systems answered the same question.\n\n"
        f"Question:\n{question}\n\n"
        f"{_format_answers(answers)}\n\n"
        "Compare the answers.\n"
        "1 Determine which answer is most accurate\n"
        "2 Combine useful information\n"
        "3 Remove incorrect details\n"
        "4 Produce the final answer\n\n"
        "Return only the final answer."
    )

    result, provider = await _call_with_fallback(prompt, system_prompt)
    return result.strip(), provider


async def verify_answer(question: str, answer: str, system_prompt: str) -> Tuple[str, str]:
    prompt = (
        "Verify this answer carefully.\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:\n{answer}\n\n"
        "If something might be outdated or incorrect, correct the answer and produce the improved version.\n"
        "Add a final 'Conclusion:' line that summarizes the answer in one sentence."
    )

    result, provider = await _call_with_fallback(prompt, system_prompt)
    return result.strip(), provider
