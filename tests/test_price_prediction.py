from datetime import date

import numpy as np
import pytest

from app.services import price_prediction as pp


def test_periods_make_same_season_one_year_apart():
    summer_2025 = pp.to_period(2025, "Summer")

    assert summer_2025 - pp.to_period(2024, "Summer") == 4
    assert pp.from_period(summer_2025) == (2025, "Summer")


def test_target_year_is_next_year_once_the_season_has_started():
    october = date(2026, 10, 12)

    assert pp.get_target_year("Winter", october) == 2027
    assert pp.get_target_year("Fall", october) == 2027
    assert pp.get_target_year("Fall", date(2026, 7, 1)) == 2026


def test_base_period_skips_missing_seasons_instead_of_shifting_rows():
    target = pp.to_period(2027, "Fall")
    prices = {
        ("BAKLA", pp.to_period(2024, "Fall")): 28.7,
        ("BAKLA", pp.to_period(2026, "Summer")): 40.0,
    }

    # Fall 2026 and Fall 2025 are missing, so the base is Fall 2024, three years back.
    assert pp.find_base_period(prices, "BAKLA", target) == (pp.to_period(2024, "Fall"), 3)


def test_base_period_ignores_prices_after_the_forecast_origin():
    target = pp.to_period(2026, "Summer")
    prices = {
        ("KARPUZ", pp.to_period(2025, "Summer")): 16.0,
        ("KARPUZ", pp.to_period(2024, "Summer")): 12.0,
    }

    base = pp.find_base_period(prices, "KARPUZ", target, last_known_period=pp.to_period(2024, "Fall"))

    assert base == (pp.to_period(2024, "Summer"), 2)


def test_training_target_is_growth_beyond_inflation():
    prices = {
        ("KARPUZ", pp.to_period(2024, "Summer")): 10.0,
        ("KARPUZ", pp.to_period(2025, "Summer")): 15.0,
        ("KARPUZ", pp.to_period(2025, "Fall")): 9.0,
    }
    inflation = {pp.to_period(2025, "Summer"): 50.0}

    features, targets = pp.build_training_frame(prices, inflation)

    # Prices rose exactly as fast as inflation, so there is nothing left for the model.
    assert features.to_dict("records") == [{"product_name": "KARPUZ", "season": "Summer", "years_back": 1}]
    assert targets == pytest.approx([0.0])


class ConstantModel:
    def __init__(self, adjustment):
        self.adjustment = adjustment

    def predict(self, features):
        return np.full(len(features), self.adjustment)


def test_forecast_grows_base_price_by_inflation_per_year_and_applies_adjustment():
    price, adjustment = pp.forecast_price(ConstantModel(0.0), "KARPUZ", 10.0, "Summer", 2, 20.0)
    assert price == pytest.approx(10.0 * 1.2**2)

    price, adjustment = pp.forecast_price(ConstantModel(np.log(1.1)), "KARPUZ", 10.0, "Summer", 1, 20.0)
    assert price == pytest.approx(10.0 * 1.2 * 1.1)
    assert adjustment == pytest.approx(np.log(1.1))


def test_predict_product_price_uses_latest_same_season_price(monkeypatch):
    prices = {
        ("KARPUZ", pp.to_period(2025, "Summer")): 12.0,
        ("KARPUZ", pp.to_period(2026, "Summer")): 16.0,
        ("KARPUZ", pp.to_period(2026, "Spring")): 50.0,
    }
    monkeypatch.setattr(pp, "get_prices", lambda: prices)
    monkeypatch.setattr(pp, "get_inflation", lambda period: 25.0)
    monkeypatch.setattr(pp, "get_price_model", lambda: ConstantModel(0.0))

    result = pp.predict_product_price("KARPUZ", "Summer", today=date(2026, 10, 12))

    assert (result["year"], result["base_year"], result["years_back"]) == (2027, 2026, 1)
    assert result["predicted_price"] == pytest.approx(20.0)


def test_predict_product_price_without_history_raises(monkeypatch):
    monkeypatch.setattr(pp, "get_prices", lambda: {})

    with pytest.raises(ValueError, match="gecmis fiyat"):
        pp.predict_product_price("KARPUZ", "Summer", today=date(2026, 10, 12))
