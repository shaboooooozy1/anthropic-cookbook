"""Tests for ``skills/custom_skills/creating-financial-models/dcf_model.py``.

Loaded via ``importlib`` because the module lives in a hyphenated directory.
The DCF math is deterministic, so expected values are hand-computed and checked
with ``pytest.approx``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parent.parent / "custom_skills" / "creating-financial-models" / "dcf_model.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("dcf_model", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dcf_model = _load_module()
DCFModel = dcf_model.DCFModel


def _single_year_model(wacc: float = 0.10):
    """A model with no history and one projection year, fully deterministic.

    base_revenue defaults to 1000, prev_nwc to 100. With the assumptions below:
      revenue = 1000 * 1.10               = 1100
      ebitda  = 1100 * 0.20               = 220
      deprec. = 1100 * 0.05               = 55
      ebit    = 220 - 55                  = 165
      tax     = 165 * 0.25                = 41.25
      nopat   = 165 - 41.25               = 123.75
      capex   = 1100 * 0.05               = 55
      nwc     = 1100 * 0.10 = 110; change = 10
      fcf     = 123.75 + 55 - 55 - 10     = 113.75
    """
    model = DCFModel("TestCo")
    model.set_assumptions(
        projection_years=1,
        revenue_growth=[0.10],
        ebitda_margin=[0.20],
        tax_rate=0.25,
        capex_percent=[0.05],
        nwc_percent=[0.10],
        terminal_growth=0.03,
    )
    model.wacc_components = {"wacc": wacc}
    return model


class TestWACC:
    def test_capm_and_weights(self):
        model = DCFModel()
        wacc = model.calculate_wacc(
            risk_free_rate=0.04,
            beta=1.2,
            market_premium=0.07,
            cost_of_debt=0.05,
            debt_to_equity=0.5,
            tax_rate=0.25,
        )
        # cost_of_equity = 0.04 + 1.2*0.07 = 0.124
        # equity_weight  = 1/1.5 = 0.6667 ; debt_weight = 0.5/1.5 = 0.3333
        # wacc = 0.6667*0.124 + 0.3333*0.05*0.75
        expected = (1 / 1.5) * 0.124 + (0.5 / 1.5) * 0.05 * 0.75
        assert wacc == pytest.approx(expected)
        assert model.wacc_components["cost_of_equity"] == pytest.approx(0.124)
        assert model.wacc_components["equity_weight"] == pytest.approx(1 / 1.5)

    def test_zero_leverage_all_equity(self):
        model = DCFModel()
        wacc = model.calculate_wacc(
            risk_free_rate=0.03,
            beta=1.0,
            market_premium=0.05,
            cost_of_debt=0.06,
            debt_to_equity=0.0,
        )
        # No debt -> wacc == cost_of_equity == 0.03 + 0.05 = 0.08
        assert wacc == pytest.approx(0.08)


class TestProjectCashFlows:
    def test_single_year_projection(self):
        model = _single_year_model()
        proj = model.project_cash_flows()
        assert proj["revenue"] == [pytest.approx(1100)]
        assert proj["ebitda"] == [pytest.approx(220)]
        assert proj["ebit"] == [pytest.approx(165)]
        assert proj["nopat"] == [pytest.approx(123.75)]
        assert proj["fcf"] == [pytest.approx(113.75)]

    def test_uses_last_historical_revenue_as_base(self):
        model = DCFModel()
        model.set_historical_financials(
            revenue=[800, 900, 1000],
            ebitda=[160, 180, 200],
            capex=[40, 45, 50],
            nwc=[80, 90, 100],
            years=[2022, 2023, 2024],
        )
        model.set_assumptions(projection_years=1, revenue_growth=[0.10])
        proj = model.project_cash_flows()
        # base revenue is last historical (1000) -> year1 revenue 1100
        assert proj["revenue"][0] == pytest.approx(1100)


class TestTerminalValue:
    def test_growth_method(self):
        model = _single_year_model(wacc=0.10)
        model.project_cash_flows()  # final fcf = 113.75
        tv = model.calculate_terminal_value(method="growth")
        # terminal_fcf = 113.75 * 1.03; tv = terminal_fcf / (0.10 - 0.03)
        expected = 113.75 * 1.03 / (0.10 - 0.03)
        assert tv == pytest.approx(expected)

    def test_multiple_method(self):
        model = _single_year_model()
        model.project_cash_flows()  # final ebitda = 220
        tv = model.calculate_terminal_value(method="multiple", exit_multiple=10)
        assert tv == pytest.approx(2200)

    def test_requires_projection_first(self):
        model = _single_year_model()
        with pytest.raises(ValueError):
            model.calculate_terminal_value()

    def test_invalid_method(self):
        model = _single_year_model()
        model.project_cash_flows()
        with pytest.raises(ValueError):
            model.calculate_terminal_value(method="bogus")


class TestEnterpriseAndEquityValue:
    def test_enterprise_value_discounting(self):
        model = _single_year_model(wacc=0.10)
        model.project_cash_flows()
        result = model.calculate_enterprise_value(terminal_method="growth")
        # PV of year-1 FCF = 113.75 / 1.10
        pv_fcf = 113.75 / 1.10
        tv = 113.75 * 1.03 / (0.10 - 0.03)
        pv_terminal = tv / 1.10
        assert result["pv_fcf"] == pytest.approx(pv_fcf)
        assert result["pv_terminal"] == pytest.approx(pv_terminal)
        assert result["enterprise_value"] == pytest.approx(pv_fcf + pv_terminal)
        assert result["terminal_percent"] == pytest.approx(
            pv_terminal / (pv_fcf + pv_terminal) * 100
        )

    def test_enterprise_value_requires_wacc(self):
        model = DCFModel()
        model.set_assumptions(projection_years=1)
        model.project_cash_flows()
        with pytest.raises(ValueError):
            model.calculate_enterprise_value()

    def test_equity_value(self):
        model = _single_year_model(wacc=0.10)
        model.project_cash_flows()
        ev = model.calculate_enterprise_value()["enterprise_value"]
        eq = model.calculate_equity_value(net_debt=100, cash=0, shares_outstanding=50)
        assert eq["equity_value"] == pytest.approx(ev - 100)
        assert eq["value_per_share"] == pytest.approx((ev - 100) / 50)

    def test_equity_value_requires_enterprise_value(self):
        model = _single_year_model()
        with pytest.raises(ValueError):
            model.calculate_equity_value(net_debt=100)


class TestHelpers:
    def test_beta_constant_market_returns_one(self):
        # Zero market variance -> guarded fallback of 1.0. Use exactly
        # representable 0.0 values so np.var is exactly 0 (0.05 would leave
        # floating-point noise that defeats the guard).
        assert dcf_model.calculate_beta([0.1, 0.2, 0.3], [0.0, 0.0, 0.0]) == 1.0

    def test_beta_positive_for_correlated_series(self):
        stock = [0.02, 0.04, 0.06, 0.08]
        market = [0.01, 0.02, 0.03, 0.04]
        assert dcf_model.calculate_beta(stock, market) > 0

    def test_fcf_cagr_basic(self):
        # (121/100)^(1/2) - 1 = 0.10
        assert dcf_model.calculate_fcf_cagr([100, 110, 121]) == pytest.approx(0.10)

    def test_fcf_cagr_doubling_one_period(self):
        assert dcf_model.calculate_fcf_cagr([100, 200]) == pytest.approx(1.0)

    def test_fcf_cagr_too_short(self):
        assert dcf_model.calculate_fcf_cagr([100]) == 0

    def test_fcf_cagr_nonpositive_endpoints(self):
        assert dcf_model.calculate_fcf_cagr([-100, 200]) == 0
        assert dcf_model.calculate_fcf_cagr([100, -200]) == 0


class TestSummary:
    def test_summary_empty_without_results(self):
        assert "No valuation results" in DCFModel().generate_summary()

    def test_summary_includes_key_lines_after_valuation(self):
        model = _single_year_model(wacc=0.10)
        model.project_cash_flows()
        model.calculate_enterprise_value()
        model.calculate_equity_value(net_debt=100, shares_outstanding=50)
        summary = model.generate_summary()
        assert "DCF Valuation Summary - TestCo" in summary
        assert "Enterprise Value:" in summary
        assert "Value per Share:" in summary
