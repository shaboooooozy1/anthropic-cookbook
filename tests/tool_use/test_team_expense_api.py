from __future__ import annotations

import json
from datetime import datetime

from tool_use.utils import team_expense_api as api


def test_get_team_members_valid_department() -> None:
    data = json.loads(api.get_team_members("engineering"))

    assert isinstance(data, list)
    assert data
    member = data[0]
    assert {"id", "name", "role", "level", "email", "department"} <= set(member.keys())


def test_get_team_members_invalid_department() -> None:
    data = json.loads(api.get_team_members("support"))

    assert "error" in data
    assert "available departments" in data["error"].lower()


def test_get_expenses_invalid_quarter() -> None:
    data = json.loads(api.get_expenses("ENG001", "Q5"))

    assert "error" in data
    assert "invalid quarter" in data["error"].lower()


def test_get_expenses_structure_and_order() -> None:
    expenses = json.loads(api.get_expenses("ENG001", "Q1"))

    assert isinstance(expenses, list)
    assert expenses

    dates = []
    for expense in expenses:
        assert {
            "expense_id",
            "date",
            "category",
            "amount",
            "currency",
            "status",
            "receipt_url",
            "payment_method",
        } <= set(expense.keys())

        date_value = datetime.fromisoformat(expense["date"])
        dates.append(date_value)
        assert datetime(2024, 1, 1) <= date_value <= datetime(2024, 3, 31)

    assert dates == sorted(dates)


def test_get_custom_budget_custom_and_standard() -> None:
    custom = json.loads(api.get_custom_budget("ENG004"))
    standard = json.loads(api.get_custom_budget("ENG001"))

    assert custom["has_custom_budget"] is True
    assert custom["travel_budget"] == 12000
    assert standard["has_custom_budget"] is False
    assert standard["travel_budget"] == 5000
