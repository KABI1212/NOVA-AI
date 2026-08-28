from __future__ import annotations

from dataclasses import dataclass
import datetime
import math
import re
from typing import Any, Awaitable, Callable

from services.agent_controller import run_agent
from services.ai_orchestrator import run_orchestrator
from services.search_service import search_web


ToolRunner = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    name: str
    description: str
    category: str
    input_schema: dict[str, Any]
    runner: ToolRunner

    def public_schema(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_schema": self.input_schema,
        }


def _normalize_question(payload: dict[str, Any]) -> str:
    question = " ".join(str(payload.get("question") or payload.get("query") or "").split()).strip()
    if not question:
        raise ValueError("Question or query is required.")
    if len(question) > 4000:
        raise ValueError("Question must be 4000 characters or fewer.")
    return question


def _validate_against_schema(payload: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be an object.")

    required = schema.get("required") or []
    properties = schema.get("properties") or {}
    validated: dict[str, Any] = {}

    if schema.get("additionalProperties") is False:
        unknown_fields = sorted(set(payload) - set(properties))
        if unknown_fields:
            raise ValueError(f"Unknown input field: {unknown_fields[0]}.")

    for field_name in required:
        if field_name not in payload:
            raise ValueError(f"{field_name} is required.")

    for field_name, field_schema in properties.items():
        if field_name not in payload:
            continue

        value = payload[field_name]
        expected_type = field_schema.get("type")
        if expected_type == "string":
            value = str(value or "").strip()
            min_length = int(field_schema.get("minLength") or 0)
            max_length = int(field_schema.get("maxLength") or 0)
            if min_length and len(value) < min_length:
                raise ValueError(f"{field_name} must be at least {min_length} characters.")
            if max_length and len(value) > max_length:
                raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
        validated[field_name] = value

    return validated


async def _run_compose(payload: dict[str, Any]) -> dict[str, Any]:
    return await run_orchestrator(_normalize_question(payload))


async def _run_agent(payload: dict[str, Any]) -> dict[str, Any]:
    return await run_agent(_normalize_question(payload))


async def _run_web_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = _normalize_question(payload)
    results = await search_web(query, num_results=5)
    return {
        "query": query,
        "results": results,
        "count": len(results),
        "source": "web_search",
    }


def _safe_eval_math(expression: str) -> float | int:
    # Only allow basic math characters and math functions
    clean = expression.strip()
    if not re.fullmatch(r"^[0-9\.\+\-\*\/\(\)\s\^\,\%eEpiPIsin|cos|tan|sqrt|log|exp]+$", clean):
        raise ValueError("Invalid mathematical characters in expression.")
    
    # Safe eval namespace
    safe_dict = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "abs": abs,
        "round": round,
    }
    # Replace ^ with ** for powers
    parsed_expr = clean.replace("^", "**")
    result = eval(parsed_expr, {"__builtins__": None}, safe_dict)
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result


async def _run_calculator(payload: dict[str, Any]) -> dict[str, Any]:
    expr = str(payload.get("expression") or "").strip()
    if not expr:
        raise ValueError("Expression is required.")
    try:
        val = _safe_eval_math(expr)
        return {"expression": expr, "result": val, "formatted": f"{expr} = {val}"}
    except Exception as exc:
        return {"expression": expr, "error": str(exc), "formatted": f"Error calculating {expr}: {exc}"}


async def _run_datetime_now(payload: dict[str, Any]) -> dict[str, Any]:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return {
        "iso": now_utc.isoformat(),
        "utc_date": now_utc.strftime("%Y-%m-%d"),
        "utc_time": now_utc.strftime("%H:%M:%S UTC"),
        "timestamp": now_utc.timestamp(),
    }


QUESTION_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["question"],
    "properties": {
        "question": {
            "type": "string",
            "title": "Question",
            "description": "The user question or task to run through this tool.",
            "minLength": 1,
            "maxLength": 4000,
        }
    },
    "additionalProperties": False,
}

CALCULATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["expression"],
    "properties": {
        "expression": {
            "type": "string",
            "title": "Expression",
            "description": "The mathematical expression to evaluate, e.g. '2^10 + sqrt(144)'.",
            "minLength": 1,
            "maxLength": 200,
        }
    },
    "additionalProperties": False,
}

DATETIME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


_TOOLS: dict[str, ToolDefinition] = {
    "multi_ai_compose": ToolDefinition(
        id="multi_ai_compose",
        name="Multi-AI Compose",
        description="Blend multiple model outputs into one final answer.",
        category="orchestration",
        input_schema=QUESTION_INPUT_SCHEMA,
        runner=_run_compose,
    ),
    "live_research_agent": ToolDefinition(
        id="live_research_agent",
        name="Live Research Agent",
        description="Use web and news sources for source-aware answers.",
        category="research",
        input_schema=QUESTION_INPUT_SCHEMA,
        runner=_run_agent,
    ),
    "web_search": ToolDefinition(
        id="web_search",
        name="Web Search",
        description="Search the web for real-time and factual information.",
        category="search",
        input_schema=QUESTION_INPUT_SCHEMA,
        runner=_run_web_search,
    ),
    "calculator": ToolDefinition(
        id="calculator",
        name="Calculator",
        description="Safely evaluate mathematical and scientific expressions.",
        category="math",
        input_schema=CALCULATOR_SCHEMA,
        runner=_run_calculator,
    ),
    "datetime_now": ToolDefinition(
        id="datetime_now",
        name="Current Date & Time",
        description="Get the current UTC date and time.",
        category="utility",
        input_schema=DATETIME_SCHEMA,
        runner=_run_datetime_now,
    ),
}


def list_tools() -> list[dict[str, Any]]:
    return [tool.public_schema() for tool in _TOOLS.values()]


def get_tool(tool_id: str) -> ToolDefinition | None:
    return _TOOLS.get(str(tool_id or "").strip())


async def run_tool(tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool = get_tool(tool_id)
    if tool is None:
        raise KeyError("Tool not found.")
    validated = _validate_against_schema(payload, tool.input_schema)
    result = await tool.runner(validated)
    return {
        **(result or {}),
        "tool": tool.public_schema(),
    }
