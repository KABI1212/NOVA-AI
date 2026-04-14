from .auth import router as auth_router
from .chat import router as chat_router
from .code import router as code_router
from .document import router as document_router
from .explain import router as explain_router
from .files import router as files_router
from .image import router as image_router
from .learning import router as learning_router
from .voice import router as voice_router
from .compat import router as compat_router
from .search import router as search_router
from .share import router as share_router

__all__ = [
    "auth_router",
    "chat_router",
    "code_router",
    "document_router",
    "explain_router",
    "files_router",
    "image_router",
    "learning_router",
    "voice_router",
    "compat_router",
    "search_router",
    "share_router"
]
