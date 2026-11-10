"""Tests for ``skills/custom_skills/analyzing-financial-statements/calculate_ratios.py``.

The module lives in a hyphenated directory, so it can't be imported as a normal
package. It's loaded directly from its file path with ``importlib``. All logic
here is pure arithmetic, so the expected values below are hand-computed and
exact (compared with ``pytest.approx`` for floats).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parent.parent
    / "custom_skills"
    / "analyzing-financial-statements"
    / "calculate_ratios.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("calculate_ratios", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


calculate_ratios = _load_module()
FinancialRatioCalculator = calculate_ratios.FinancialRatioCalculator


# A small, self-consistent dataset with hand-computed expected ratios.
SAMPLE_DATA = {
    "income_statement": {
        "revenue": 1000,
        "cost_of_goods_sold": 600,
        "operating_income": 200,
        "net_income": 150,
        "ebit": 180,
        "ebitda": 250,
        "interest_expense": 20,
    },
    "balance_sheet": {
        "total_assets": 2000,
        "current_assets": 800,
        "cash_and_equivalents": 200,
        "accounts_receivable": 100,
        "inventory": 300,
        "current_liabilities": 400,
        "total_debt": 500,
        "current_portion_long_term_debt": 50,
        "shareholders_equity": 1250,
    },
    "market_data": {
        "share_price": 50,
        "shares_outstanding": 100,
        "earnings_growth_rate": 0.10,
    },
}


@pytest.fixture
def calc():
    return FinancialRatioCalculator(SAMPLE_DATA)


class TestSafeDivide:
    def test_normal_division(self, calc):
        assert calc.safe_divide(10, 2) == 5.0

    def test_zero_denominator_returns_default(self, calc):
        assert calc.safe_divide(10, 0) == 0.0

    def test_zero_denominator_custom_default(self, calc):
        assert calc.safe_divide(10, 0, default=1.5) == 1.5


class TestProfitabilityRatios:
    def test_values(self, calc):
        r = calc.calculate_profitability_ratios()
        assert r["roe"] == pytest.approx(150 / 1250)  # 0.12
        assert r["roa"] == pytest.approx(150 / 2000)  # 0.075
        assert r["gross_margin"] == pytest.approx(0.40)
        assert r["operating_margin"] == pytest.approx(0.20)
        assert r["net_margin"] == pytest.approx(0.15)

    def test_zero_revenue_is_safe(self):
        calc = FinancialRatioCalculator({"income_statement": {"net_income": 10}})
        r = calc.calculate_profitability_ratios()
        assert r["gross_margin"] == 0.0
        assert r["net_margin"] == 0.0


class TestLiquidityRatios:
    def test_values(self, calc):
        r = calc.calculate_liquidity_ratios()
        assert r["current_ratio"] == pytest.approx(2.0)
        assert r["quick_ratio"] == pytest.approx(1.25)  # (800-300)/400
        assert r["cash_ratio"] == pytest.approx(0.5)


class TestLeverageRatios:
    def test_values(self, calc):
        r = calc.calculate_leverage_ratios()
        assert r["debt_to_equity"] == pytest.approx(0.40)
        assert r["interest_coverage"] == pytest.approx(9.0)
        assert r["debt_service_coverage"] == pytest.approx(200 / 70)


class TestEfficiencyRatios:
    def test_values(self, calc):
        r = calc.calculate_efficiency_ratios()
        assert r["asset_turnover"] == pytest.approx(0.5)
        assert r["inventory_turnover"] == pytest.approx(2.0)
        assert r["receivables_turnover"] == pytest.approx(10.0)
        assert r["days_sales_outstanding"] == pytest.approx(36.5)

    def test_zero_receivables_does_not_raise(self):
        calc = FinancialRatioCalculator(
            {"income_statement": {"revenue": 1000}, "balance_sheet": {"inventory": 0}}
        )
        r = calc.calculate_efficiency_ratios()
        # receivables_turnover is 0, so DSO divides 365 by 0 -> safe default 0.0
        assert r["receivables_turnover"] == 0.0
        assert r["days_sales_outstanding"] == 0.0


class TestValuationRatios:
    def test_values(self, calc):
        r = calc.calculate_valuation_ratios()
        assert r["eps"] == pytest.approx(1.5)
        assert r["pe_ratio"] == pytest.approx(50 / 1.5)
        assert r["book_value_per_share"] == pytest.approx(12.5)
        assert r["pb_ratio"] == pytest.approx(4.0)
        assert r["ps_ratio"] == pytest.approx(5.0)  # market_cap 5000 / revenue 1000
        assert r["ev_to_ebitda"] == pytest.approx(5300 / 250)  # (5000+500-200)/250
        assert r["peg_ratio"] == pytest.approx((50 / 1.5) / (0.10 * 100))

    def test_peg_omitted_without_growth(self):
        data = {
            **SAMPLE_DATA,
            "market_data": {**SAMPLE_DATA["market_data"], "earnings_growth_rate": 0},
        }
        r = FinancialRatioCalculator(data).calculate_valuation_ratios()
        assert "peg_ratio" not in r


class TestCalculateAllRatios:
    def test_has_all_categories(self, calc):
        r = calc.calculate_all_ratios()
        assert set(r) == {"profitability", "liquidity", "leverage", "efficiency", "valuation"}


class TestInterpretRatio:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (2.5, "Strong liquidity"),
            (2.0, "Adequate liquidity"),  # boundary: not > 2
            (1.2, "Potential liquidity concerns"),
            (0.9, "Liquidity issues"),
        ],
    )
    def test_current_ratio(self, calc, value, expected):
        assert calc.interpret_ratio("current_ratio", value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0.25, "Excellent returns"),
            (0.16, "Good returns"),
            (0.12, "Average returns"),
            (0.05, "Below average returns"),
            (-0.1, "Negative returns"),
        ],
    )
    def test_roe(self, calc, value, expected):
        assert calc.interpret_ratio("roe", value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (10, "Potentially undervalued"),
            (20, "Fair value"),
            (33, "Growth premium"),
            (45, "High valuation"),
            (-5, "N/A (negative earnings)"),
        ],
    )
    def test_pe_ratio(self, calc, value, expected):
        assert calc.interpret_ratio("pe_ratio", value) == expected

    def test_unknown_ratio(self, calc):
        assert calc.interpret_ratio("made_up_ratio", 1.0) == "No interpretation available"


class TestFormatRatio:
    def test_percentage(self, calc):
        assert calc.format_ratio("net_margin", 0.1234, "percentage") == "12.34%"

    def test_times(self, calc):
        assert calc.format_ratio("interest_coverage", 9.0, "times") == "9.00x"

    def test_days(self, calc):
        assert calc.format_ratio("dso", 36.5, "days") == "36.5 days"

    def test_currency(self, calc):
        assert calc.format_ratio("bvps", 12.5, "currency") == "$12.50"

    def test_default(self, calc):
        assert calc.format_ratio("ratio", 2.0) == "2.00"


class TestTopLevelHelpers:
    def test_calculate_ratios_from_data_structure(self):
        result = calculate_ratios.calculate_ratios_from_data(SAMPLE_DATA)
        assert set(result) == {"ratios", "interpretations", "summary"}
        assert result["interpretations"]["liquidity"]["current_ratio"]["formatted"] == "2.00"
        assert isinstance(result["summary"], str) and result["summary"]

    def test_generate_summary_mentions_key_metrics(self):
        ratios = FinancialRatioCalculator(SAMPLE_DATA).calculate_all_ratios()
        summary = calculate_ratios.generate_summary(ratios)
        assert "ROE" in summary
        assert "Current ratio" in summary
        assert "Debt-to-equity" in summary

    def test_generate_summary_empty_on_no_data(self):
        assert calculate_ratios.generate_summary({}) == "Insufficient data for summary."
