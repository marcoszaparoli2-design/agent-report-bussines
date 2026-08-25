"""Loads the shared business-knowledge layer for injection into the curator prompt.

The same files that document the project for a human onboarding to the repo
are read here and handed to the LLM -- one source of truth, so a human's
understanding of a term and the model's context for it can never diverge.
"""
from __future__ import annotations

from pathlib import Path


def load_knowledge(knowledge_dir: str | Path) -> str:
    knowledge_dir = Path(knowledge_dir)
    if not knowledge_dir.exists():
        return ""

    sections = []
    for path in sorted(knowledge_dir.glob("*.md")):
        sections.append(f"## {path.stem}\n\n{path.read_text(encoding='utf-8').strip()}")
    return "\n\n---\n\n".join(sections)
