from __future__ import annotations

import asyncio

from models.conversation import Conversation
from services.conversation_memory import add_message, clear_history, get_history
from services.conversation_summary import build_summary_history_message
from services.vector_service import VectorService


def test_conversation_memory_is_scoped_by_session() -> None:
    clear_history("session-a")
    clear_history("session-b")

    add_message("user", "Build me a timetable", session_id="session-a")
    add_message("assistant", "What days are blocked?", session_id="session-a")
    add_message("user", "This should stay isolated", session_id="session-b")

    assert [item["content"] for item in get_history(session_id="session-a")] == [
        "Build me a timetable",
        "What days are blocked?",
    ]
    assert [item["content"] for item in get_history(session_id="session-b")] == [
        "This should stay isolated",
    ]

    clear_history("session-a")
    clear_history("session-b")


def test_build_summary_history_message_uses_saved_memory() -> None:
    conversation = Conversation()
    assert build_summary_history_message(conversation) is None

    conversation.context_summary = "- Goals: Build a college timetable\n- Constraints: No Friday labs"
    message = build_summary_history_message(conversation)

    assert message is not None
    assert message["role"] == "system"
    assert "Goals" in message["content"]


def test_vector_service_chunking_preserves_overlap() -> None:
    service = VectorService()
    words = [f"w{index}" for index in range(24)]
    chunks = service.chunk_text(" ".join(words), chunk_size=10, overlap=4)

    assert len(chunks) >= 2
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    assert second_words[:4] == first_words[-4:]


def test_vector_service_can_lazy_reindex_without_embeddings() -> None:
    async def scenario() -> None:
        service = VectorService()
        service.embeddings_enabled = False
        text = (
            "College timetable planning includes physics lab on monday, chemistry lecture on tuesday, "
            "math revision on wednesday, and project work on thursday."
        )

        await service.ensure_document(text, 11)
        results = await service.search("physics lab monday", k=2, doc_id=11)
        assert results
        assert "physics lab" in results[0][0].lower()

        service.remove_document(11)
        assert await service.search("physics lab monday", k=2, doc_id=11) == []

    asyncio.run(scenario())
