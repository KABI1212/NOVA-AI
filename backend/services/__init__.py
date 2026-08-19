# backend/services/__init__.py
"""Modular service exports for NOVA AI."""

def __getattr__(name: str):
    if name == "ai_service":
        from .ai_service import ai_service
        return ai_service
    if name == "file_intelligence_service":
        from .file_intelligence import file_intelligence_service
        return file_intelligence_service
    if name == "document_service":
        from .document_service import document_service
        return document_service
    if name == "email_service":
        from .email_service import email_service
        return email_service
    if name == "vector_service":
        from .vector_service import vector_service
        return vector_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ai_service",
    "file_intelligence_service",
    "document_service",
    "email_service",
    "vector_service",
]

