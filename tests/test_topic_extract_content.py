#!/usr/bin/env python3
# version: 0.1.0
"""test_topic_extract_content.py — the content path (`extract_topics`) carries no noise topics.

`moc-tree-builder.py` builds every MOC-structure cache entry's topics through
`topic-extract.py --content`. That path still read H2 headings and kept function
words and date links. Live (2026-10-30, 214 orphans): 151 clusters, among them
"related notes"/"resources"/"why it's important" (template H2s, 30 each) and
"not"/"you"/"ist"/"nicht"/"have"/"2022-09-11".
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tomo" / "scripts" / "topic-extract.py"

_spec = importlib.util.spec_from_file_location("topic_extract_content", SCRIPT)
te = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(te)


def _topics(content: str, title: str | None = None) -> list[str]:
    return te.extract_topics(content, title)["topics"]


def test_h2_headings_yield_no_topics():
    content = "# Zettelkasten\n\n## Related Notes\n\n## Why it's important\n\ntext\n"

    result = te.extract_topics(content)

    assert result["source_methods"]["headings"] == []
    assert "related notes" not in result["topics"]
    assert "why it's important" not in result["topics"]
    assert "zettelkasten" in result["topics"]


def test_english_function_words_from_title_words_are_dropped():
    topics = _topics("body\n", "Choose the positive. You have a choice (Quote)")

    for word in ("you", "have", "the"):
        assert word not in topics
    assert "choice" in topics


def test_german_function_words_from_title_words_are_dropped():
    topics = _topics("body\n", "Was nicht passt und bleibt")

    for word in ("was", "nicht", "und"):
        assert word not in topics
    assert "passt" in topics


def test_topics_without_a_letter_are_dropped():
    content = "# 2821 Quotes\n\nSee [[2022-11-08]] and [[Obsidian]].\n"

    topics = _topics(content)

    assert "2022-11-08" not in topics
    assert "2821" not in topics
    assert "quotes" in topics and "obsidian" in topics


def test_short_letter_topics_survive():
    assert "ai" in _topics("body\n", "AI Agents")


def test_cli_content_path_applies_the_same_rules():
    content = "# Nicht der Plan\n\n## Resources\n\n[[2023-05-25]]\n"
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--content", content, "--title", "Nicht der Plan"],
        capture_output=True, text=True, check=True,
    )

    topics = json.loads(out.stdout)["topics"]

    assert "plan" in topics
    for noise in ("nicht", "der", "resources", "2023-05-25"):
        assert noise not in topics
