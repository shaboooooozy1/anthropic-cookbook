"""Tests for tool_use/utils/customer_service_api.py.

Pins the consumer-visible contracts of the ticket enums and processing helpers
so the ``str, Enum`` → ``enum.StrEnum`` conversion (ruff UP042) is safe:
customer_service_tools.py relies on ``.value``, construction from raw strings,
plain-string equality, and TEAM_ROUTING dict lookups — all locked in here.
"""

from __future__ import annotations

import json

import pytest

from tool_use.utils.customer_service_api import (
    KNOWLEDGE_BASE,
    TEAM_ROUTING,
    Ticket,
    TicketCategory,
    TicketGenerator,
    TicketPriority,
    TicketStatus,
    determine_priority,
    process_ticket,
)

ALL_ENUMS = [TicketCategory, TicketPriority, TicketStatus]


def make_ticket(**overrides) -> Ticket:
    """Build a minimal ticket with sensible defaults for targeted tests."""
    defaults = {
        "id": "TICKET-1",
        "customer_name": "Test Customer",
        "customer_email": "test@example.com",
        "subject": "Test subject",
        "description": "A perfectly calm description with no keywords",
    }
    defaults.update(overrides)
    return Ticket(**defaults)


class TestEnumStringContracts:
    """Behaviors customer_service_tools.py and the notebooks depend on."""

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS)
    def test_members_are_strings(self, enum_cls):
        for member in enum_cls:
            assert isinstance(member, str)

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS)
    def test_value_roundtrip_construction(self, enum_cls):
        # customer_service_tools.py does e.g. TicketCategory(category)
        for member in enum_cls:
            assert enum_cls(member.value) is member

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS)
    def test_equality_with_plain_string(self, enum_cls):
        for member in enum_cls:
            assert member == member.value

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS)
    def test_str_and_format_render_as_value(self, enum_cls):
        # Guaranteed by StrEnum; this is the behavior change UP042's
        # unsafe fix warns about, pinned here deliberately.
        for member in enum_cls:
            assert str(member) == member.value
            assert f"{member}" == member.value

    @pytest.mark.parametrize("enum_cls", ALL_ENUMS)
    def test_json_serializes_as_value(self, enum_cls):
        for member in enum_cls:
            assert json.dumps(member) == json.dumps(member.value)

    def test_expected_category_values(self):
        assert {c.value for c in TicketCategory} == {
            "billing",
            "technical",
            "account",
            "product",
            "shipping",
        }

    def test_expected_priority_values(self):
        assert {p.value for p in TicketPriority} == {"low", "medium", "high", "urgent"}

    def test_expected_status_values(self):
        assert {s.value for s in TicketStatus} == {
            "new",
            "open",
            "pending",
            "resolved",
            "closed",
        }


class TestTeamRoutingAndKnowledgeBase:
    def test_every_category_has_a_team(self):
        for category in TicketCategory:
            assert category in TEAM_ROUTING
            assert isinstance(TEAM_ROUTING[category], str)

    def test_routing_lookup_by_enum_member(self):
        # process_ticket does TEAM_ROUTING.get(ticket.category, ...)
        assert TEAM_ROUTING[TicketCategory.BILLING] == "billing-team"
        assert TEAM_ROUTING.get(TicketCategory.SHIPPING) == "logistics-team"

    def test_knowledge_base_keys_match_category_values(self):
        # search_knowledge_base indexes KNOWLEDGE_BASE with lowercase strings
        assert set(KNOWLEDGE_BASE) <= {c.value for c in TicketCategory}


class TestDeterminePriority:
    def test_urgent_keyword_wins(self):
        ticket = make_ticket(description="I am locked out and need help immediately")
        assert determine_priority(ticket) is TicketPriority.URGENT

    def test_urgent_keyword_beats_billing_category(self):
        ticket = make_ticket(
            description="This is urgent, please refund me",
            category=TicketCategory.BILLING,
        )
        assert determine_priority(ticket) is TicketPriority.URGENT

    def test_high_keyword(self):
        ticket = make_ticket(description="The export feature is not working at all")
        assert determine_priority(ticket) is TicketPriority.HIGH

    def test_billing_category_defaults_to_high(self):
        ticket = make_ticket(category=TicketCategory.BILLING)
        assert determine_priority(ticket) is TicketPriority.HIGH

    def test_everything_else_is_medium(self):
        ticket = make_ticket(category=TicketCategory.PRODUCT)
        assert determine_priority(ticket) is TicketPriority.MEDIUM

    def test_keyword_match_is_case_insensitive(self):
        ticket = make_ticket(description="URGENT: everything is on fire")
        assert determine_priority(ticket) is TicketPriority.URGENT


class TestProcessTicket:
    def test_assigns_priority_and_team(self):
        ticket = make_ticket(category=TicketCategory.TECHNICAL)
        processed = process_ticket(ticket)
        assert processed.priority is TicketPriority.MEDIUM
        assert processed.assigned_team == "tech-support"

    def test_uncategorized_ticket_goes_to_general_support(self):
        processed = process_ticket(make_ticket(category=None))
        assert processed.assigned_team == "general-support"


class TestTicketDataclass:
    def test_post_init_sets_created_at(self):
        assert make_ticket().created_at is not None

    def test_default_status_is_new(self):
        assert make_ticket().status is TicketStatus.NEW


class TestTicketGenerator:
    def test_generate_ticket_shape(self):
        ticket = TicketGenerator.generate_ticket(7)
        assert ticket.id == "TICKET-7"
        assert ticket.status is TicketStatus.NEW
        assert isinstance(ticket.category, TicketCategory)
        assert ticket.priority is None
        assert "@example.com" in ticket.customer_email

    def test_generated_description_has_no_unfilled_placeholders(self):
        for _ in range(20):
            ticket = TicketGenerator.generate_ticket()
            assert "{" not in ticket.description
            assert "}" not in ticket.description

    def test_generate_batch_count_and_sequential_ids(self):
        batch = TicketGenerator.generate_batch(5)
        assert [t.id for t in batch] == [f"TICKET-{i}" for i in range(1, 6)]
