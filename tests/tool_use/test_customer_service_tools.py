from __future__ import annotations

import json

import pytest

from tool_use.utils import customer_service_tools as tools


@pytest.fixture(autouse=True)
def reset_queue() -> None:
    tools.initialize_ticket_queue(0)
    yield
    tools.initialize_ticket_queue(0)


def test_get_next_ticket_exhaustion() -> None:
    tools.initialize_ticket_queue(2)

    first = json.loads(tools.get_next_ticket())
    second = json.loads(tools.get_next_ticket())
    exhausted = json.loads(tools.get_next_ticket())

    assert "id" in first
    assert "id" in second
    assert "error" in exhausted
    assert exhausted["processed"] == 2


def test_ticket_processing_flow() -> None:
    tools.initialize_ticket_queue(1)
    ticket = json.loads(tools.get_next_ticket())
    ticket_id = ticket["id"]

    classified = json.loads(tools.classify_ticket(ticket_id, "billing"))
    assert classified["success"] is True

    priority = json.loads(tools.set_priority(ticket_id, "urgent"))
    assert priority["success"] is True
    assert priority["new_priority"] == "urgent"

    routed = json.loads(tools.route_to_team(ticket_id, "billing-team"))
    assert routed["success"] is True
    assert routed["new_team"] == "billing-team"

    drafted = json.loads(tools.draft_response(ticket_id, "Thanks for reaching out!"))
    assert drafted["success"] is True
    assert drafted["draft_length"] > 0

    noted = json.loads(tools.add_note(ticket_id, "Internal note"))
    assert noted["success"] is True
    assert noted["total_notes"] >= 2

    completed = json.loads(tools.mark_complete(ticket_id))
    assert completed["success"] is True
    assert completed["summary"]["status"] == "resolved"


def test_mark_complete_requires_classification() -> None:
    tools.initialize_ticket_queue(1)
    ticket = json.loads(tools.get_next_ticket())

    result = json.loads(tools.mark_complete(ticket["id"]))

    assert "error" in result
    assert "category" in result["error"].lower()


def test_search_knowledge_base_invalid_category() -> None:
    result = json.loads(tools.search_knowledge_base("invalid", "refund"))

    assert "error" in result
    assert "available_categories" in result
