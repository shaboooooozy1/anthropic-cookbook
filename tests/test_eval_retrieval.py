"""Tests for promptfoo retrieval evaluation helpers."""

from __future__ import annotations

import sys
from pathlib import Path

EVALUATION_DIR = (
    Path(__file__).parent.parent / "capabilities" / "retrieval_augmented_generation" / "evaluation"
)
sys.path.insert(0, str(EVALUATION_DIR))

from eval_retrieval import evaluate_retrieval, get_assert  # noqa: E402


def test_evaluate_retrieval_calculates_metrics():
    precision, recall, mrr, f1 = evaluate_retrieval(
        ["chunk-a", "chunk-c"], "['chunk-a', 'chunk-b']"
    )

    assert precision == 0.5
    assert recall == 0.5
    assert mrr == 1.0
    assert f1 == 0.5


def test_get_assert_returns_component_scores_for_valid_input():
    result = get_assert(["chunk-a", "chunk-c"], {"vars": {"correct_chunks": "['chunk-a']"}})

    assert result["pass"] is True
    assert result["score"] == 2 / 3
    assert result["componentResults"][0]["named_scores"] == {"MRR": 1.0}


def test_get_assert_handles_malformed_correct_chunks():
    result = get_assert(["chunk-a"], {"vars": {"correct_chunks": "not-a-python-list"}})

    assert result["pass"] is False
    assert result["score"] == 0.0
    assert "Unexpected error" in result["reason"]
    assert [component["score"] for component in result["componentResults"]] == [0.0, 0.0, 0.0, 0.0]


def test_get_assert_handles_missing_context_shape():
    result = get_assert(["chunk-a"], {})

    assert result["pass"] is False
    assert result["score"] == 0.0
    assert "Unexpected error" in result["reason"]
