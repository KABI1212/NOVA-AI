from time import perf_counter
from typing import Dict, List

from prompts import get_mode_prompt
from services.answer_evaluator import evaluate_answers, verify_answer
from services.multi_ai import query_models

SYSTEM_PROMPT = (
    f"{get_mode_prompt('chat')}\n\n"
    "Additional orchestration rules:\n"
    "- Combine useful signals from multiple models when available.\n"
    "- Return the most accurate final answer.\n"
    "- Do not mention internal model-selection mechanics."
)


def _unique(values: List[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _ensure_conclusion(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return cleaned
    cleaned = cleaned.replace("knowledge cutoff", "").replace("Knowledge cutoff", "")
    if "Conclusion:" in cleaned:
        return cleaned
    first_sentence = cleaned.split(".")[0].strip()
    summary = first_sentence if first_sentence else cleaned[:140].strip()
    return f"{cleaned}\n\nConclusion: {summary}."


async def run_orchestrator(question: str) -> Dict:
    query = (question or "").strip()
    if not query:
        return {
            "answer": "Please enter a message.",
            "models_used": [],
            "response_time": 0.0,
            "badge": "⚡ Multi-AI Answer",
        }

    start = perf_counter()
    responses = await query_models(query, SYSTEM_PROMPT)
    valid = [r for r in responses if r.get("ok") and r.get("text")]

    if not valid:
        elapsed = perf_counter() - start
        return {
            "answer": "NOVA AI could not reach any AI provider right now.",
            "models_used": [],
            "response_time": round(elapsed, 3),
            "badge": "⚡ Multi-AI Answer",
        }

    final_answer, evaluator_provider = await evaluate_answers(query, valid, SYSTEM_PROMPT)
    verified_answer, verifier_provider = await verify_answer(query, final_answer, SYSTEM_PROMPT)

    elapsed = perf_counter() - start

    models_used = _unique(
        [item.get("provider", "") for item in valid] + [evaluator_provider, verifier_provider]
    )

    final_text = verified_answer or final_answer

    return {
        "answer": _ensure_conclusion(final_text),
        "models_used": models_used,
        "response_time": round(elapsed, 3),
        "badge": "⚡ Multi-AI Answer",
    }
