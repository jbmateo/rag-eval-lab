"""System registry. Adapters with heavy imports are loaded only when asked for."""
from evallab.adapters.base import RAGSystem
from evallab.config import Settings


def _fake(settings: Settings) -> RAGSystem:
    from evallab.adapters.fake import FakeSystem

    return FakeSystem()


def _rag_studio(settings: Settings) -> RAGSystem:
    from evallab.adapters.rag_studio import RagStudioSystem

    return RagStudioSystem(settings)


SYSTEMS = {"fake": _fake, "rag_studio": _rag_studio}


def get_system(name: str, settings: Settings) -> RAGSystem:
    if name not in SYSTEMS:
        raise KeyError(f"Unknown system {name!r}; known: {', '.join(sorted(SYSTEMS))}")
    return SYSTEMS[name](settings)
