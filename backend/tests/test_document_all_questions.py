import pytest
from prompts import MODE_PROMPTS, get_mode_prompt
from ai_engine import _multi_question_answer_instruction, _looks_like_multi_question_request
from services.ai_service import _document_answer_max_tokens, _DOCUMENT_MULTI_QUESTION_PATTERN
from routes.files import FILE_FIRST_SYSTEM_PROMPT, _file_response_max_tokens, EXPANDED_FILE_RESPONSE_MAX_TOKENS
from routes.chat import _DOCUMENT_GROUNDING_INSTRUCTION, _needs_full_document_context, _ALL_QUESTIONS_PATTERN


def test_mode_prompts_documents_contains_all_questions_directive():
    doc_prompt = MODE_PROMPTS["documents"]
    assert "Total questions detected: X" in doc_prompt
    assert "Question 1: [Original question]" in doc_prompt
    assert "Answer: [Answer]" in doc_prompt
    assert "Explanation: [Full, detailed, step-by-step explanation" in doc_prompt
    assert "full, in-depth explanation" in doc_prompt.lower()
    assert "answer all 10 questions" in doc_prompt.lower()
    assert "answer all 30 questions" in doc_prompt.lower()
    assert "answer all 100 questions" in doc_prompt.lower()
    assert "Part 1: Questions 1–20" in doc_prompt
    assert "Completeness Check" in doc_prompt
    assert "scan ALL pages/sheets" in doc_prompt
    assert "Excel files, check ALL relevant sheets" in doc_prompt


def test_file_first_system_prompt_contains_all_questions_directive():
    assert "Total questions detected: X" in FILE_FIRST_SYSTEM_PROMPT
    assert "Question 1: [Original question]" in FILE_FIRST_SYSTEM_PROMPT
    assert "Answer: [Answer]" in FILE_FIRST_SYSTEM_PROMPT
    assert "Explanation: [Full, detailed, step-by-step explanation" in FILE_FIRST_SYSTEM_PROMPT
    assert "full, in-depth explanation" in FILE_FIRST_SYSTEM_PROMPT.lower()
    assert "answer all 10 questions" in FILE_FIRST_SYSTEM_PROMPT.lower()
    assert "answer all 30 questions" in FILE_FIRST_SYSTEM_PROMPT.lower()
    assert "answer all 100 questions" in FILE_FIRST_SYSTEM_PROMPT.lower()
    assert "Part 1: Questions 1–20" in FILE_FIRST_SYSTEM_PROMPT
    assert "Completeness Check" in FILE_FIRST_SYSTEM_PROMPT


def test_chat_document_grounding_contains_all_questions_directive():
    assert "Total questions detected: X" in _DOCUMENT_GROUNDING_INSTRUCTION
    assert "Question 1: [Original question]" in _DOCUMENT_GROUNDING_INSTRUCTION
    assert "Answer: [Answer]" in _DOCUMENT_GROUNDING_INSTRUCTION
    assert "Explanation: [Full, detailed, step-by-step explanation" in _DOCUMENT_GROUNDING_INSTRUCTION
    assert "full, in-depth explanation" in _DOCUMENT_GROUNDING_INSTRUCTION.lower()
    assert "Part 1: Questions 1–20" in _DOCUMENT_GROUNDING_INSTRUCTION


def test_multi_question_answer_instruction_ai_engine():
    instruction = _multi_question_answer_instruction("Please answer all questions in this paper")
    assert instruction is not None
    assert "Total questions detected: X" in instruction
    assert "Question 1: [Original question]" in instruction
    assert "Answer: [Answer]" in instruction
    assert "Explanation: [Full, detailed, step-by-step explanation" in instruction
    assert "full, comprehensive explanation" in instruction.lower()
    assert "Part 1: Questions 1–20" in instruction


def test_needs_full_document_context_patterns():
    # Empty message should trigger full context
    assert _needs_full_document_context("") is True
    assert _needs_full_document_context(None) is True
    # Explicit requests
    assert _needs_full_document_context("Answer all questions") is True
    assert _needs_full_document_context("Solve all questions") is True
    assert _needs_full_document_context("Process this document") is True
    assert _needs_full_document_context("What are the questions in this document?") is True
    assert _needs_full_document_context("1. What is AI?\n2. What is ML?") is True


def test_token_limits_expansion_for_questions():
    tokens = _file_response_max_tokens("Answer all questions in this exam", has_context=True)
    assert tokens == EXPANDED_FILE_RESPONSE_MAX_TOKENS
    assert tokens >= 16384

    doc_tokens = _document_answer_max_tokens("Answer all questions")
    assert doc_tokens >= 16384
