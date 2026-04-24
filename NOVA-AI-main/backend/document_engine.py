from services.document_service import document_service
from services.vector_service import vector_service
from services.ai_service import ai_service


async def process_document(file_path: str, file_type: str) -> str:
    return await document_service.process_document(file_path, file_type)


async def summarize_document(text: str) -> str:
    return await ai_service.summarize_document(text)


async def answer_from_document(question: str, context: str) -> str:
    return await ai_service.answer_question_from_document(question, context)


async def index_document(text: str, doc_id: int) -> None:
    await vector_service.add_document(text, doc_id)


async def search_document(question: str, k: int = 3):
    return await vector_service.search(question, k=k)
