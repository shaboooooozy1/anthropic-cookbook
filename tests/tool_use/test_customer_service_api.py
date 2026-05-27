from __future__ import annotations

from datetime import datetime

import pytest

from tool_use.utils.customer_service_api import (
    TEAM_ROUTING,
    Ticket,
    TicketCategory,
    TicketGenerator,
    TicketPriority,
    TicketStatus,
    determine_priority,
    process_ticket,
)


def _make_ticket(description: str, category: TicketCategory | None = None) -> Ticket:
    return Ticket(
        id="TICKET-TEST",
        customer_name="Test User",
        customer_email="test@example.com",
        subject="Test Subject",
        description=description,
        category=category,
    )


def test_generate_ticket_defaults() -> None:
    ticket = TicketGenerator.generate_ticket(42)

    assert ticket.id == "TICKET-42"
    assert isinstance(ticket.category, TicketCategory)
    assert ticket.priority is None
    assert ticket.status == TicketStatus.NEW
    assert isinstance(ticket.created_at, datetime)
    assert ticket.subject
    assert ticket.description


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("I can't access my account", TicketPriority.URGENT),
        ("The app crashes on startup", TicketPriority.HIGH),
    ],
)
def test_determine_priority_keyword_matches(description: str, expected: TicketPriority) -> None:
    ticket = _make_ticket(description, TicketCategory.ACCOUNT)

    assert determine_priority(ticket) == expected


def test_determine_priority_billing_defaults_high() -> None:
    ticket = _make_ticket("General billing question", TicketCategory.BILLING)

    assert determine_priority(ticket) == TicketPriority.HIGH


def test_determine_priority_default_medium() -> None:
    ticket = _make_ticket("Feature clarification", TicketCategory.PRODUCT)

    assert determine_priority(ticket) == TicketPriority.MEDIUM


def test_process_ticket_assigns_priority_and_team() -> None:
    ticket = _make_ticket("Feature clarification", TicketCategory.PRODUCT)

    processed = process_ticket(ticket)

    assert processed.priority == TicketPriority.MEDIUM
    assert processed.assigned_team == TEAM_ROUTING[TicketCategory.PRODUCT]


def test_process_ticket_unclassified_routes_to_general() -> None:
    ticket = _make_ticket("General question", None)

    processed = process_ticket(ticket)

    assert processed.assigned_team == "general-support"
