"""不使用 metadata 过滤的纯文本加载与段落感知分块。"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

TEXT_EXTS = {".md", ".markdown", ".mdx", ".txt", ".rst", ".org", ".text"}
EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
}


def iter_files(root: str | Path, exts: set[str] = TEXT_EXTS) -> Iterator[Path]:
    root = Path(root)
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        relative_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in relative_parts[:-1]):
            continue
        if path.is_file() and path.suffix.lower() in exts:
            yield path


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """把段落组合成知识块，仅对超过长度限制的段落添加重叠。"""

    if size <= 0:
        raise ValueError("知识块长度必须大于零。")
    if overlap < 0 or overlap >= size:
        raise ValueError("知识块重叠长度必须大于等于零，并且小于知识块长度。")

    paragraphs = [part.strip() for part in str(text).split("\n\n") if part.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        if len(paragraph) > size:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            step = size - overlap
            for start in range(0, len(paragraph), step):
                piece = paragraph[start : start + size]
                if piece:
                    chunks.append(piece)
            continue
        candidate = f"{buffer}\n\n{paragraph}".strip()
        if len(candidate) <= size:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer)
            buffer = paragraph
    if buffer:
        chunks.append(buffer)
    return chunks


def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")
