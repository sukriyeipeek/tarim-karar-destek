
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from app.services.inflation_service import load_raw_inflation_data, predict_inflation


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = ROOT_DIR / "data" / "processed" / "data_files" / "final_price_dataset.csv"
MODEL_PATH = ROOT_DIR / "models" / "price_model_catboost.cbm"

SEASON_ORDER = {
    "Winter": 0,
    "Spring": 1,
    "Summer": 2,
    "Fall": 3,
}
SEASON_SEQUENCE = list(SEASON_ORDER)

CATEGORICAL_FEATURES = ["product_name", "season"]
FEATURE_COLUMNS = [*CATEGORICAL_FEATURES, "years_back"]


TRAINING_YEARS_BACK = (1, 2)
MAX_YEARS_BACK = 5


def validate_season(season: str) -> str:
    season = str(season).strip()

    if season not in SEASON_ORDER:
        valid_seasons = ", ".join(SEASON_SEQUENCE)
        raise ValueError(
            f"Gecersiz sezon: {season}. Gecerli sezonlar: {valid_seasons}"
        )

    return season


def to_period(year: int, season: str) -> int:
    """Number of seasons since year 0, so that period - 4 is the same season a year earlier."""
    return int(year) * 4 + SEASON_ORDER[validate_season(season)]


def from_period(period: int) -> tuple[int, str]:
    return period // 4, SEASON_SEQUENCE[period % 4]


def get_current_season(today: date | None = None) -> tuple[int, str]:
    if today is None:
        today = date.today()

    month = today.month
    if month in [12, 1, 2]:
        return today.year, "Winter"
    if month in [3, 4, 5]:
        return today.year, "Spring"
    if month in [6, 7, 8]:
        return today.year, "Summer"
    return today.year, "Fall"


def get_target_year(target_season: str, today: date | None = None) -> int:
    target_season = validate_season(target_season)
    current_year, current_season = get_current_season(today)

    if SEASON_ORDER[target_season] > SEASON_ORDER[current_season]:
        return current_year

    return current_year + 1


def load_prices(dataset_path: Path = DATASET_PATH) -> dict[tuple[str, int], float]:
    """Average price per (product, period). Lags are derived from periods, never from row order."""
    if not Path(dataset_path).exists():
        raise FileNotFoundError(f"Dataset bulunamadi: {dataset_path}")

    df = pd.read_csv(dataset_path, usecols=["product_name", "year", "season", "average_price"])
    df["average_price"] = pd.to_numeric(df["average_price"], errors="coerce")
    df = df.dropna(subset=["average_price"])
    df = df[df["average_price"] > 0]

    return {
        (str(row.product_name), to_period(row.year, row.season)): float(row.average_price)
        for row in df.itertuples()
    }


@lru_cache(maxsize=1)
def get_prices() -> dict[tuple[str, int], float]:
    return load_prices()


@lru_cache(maxsize=1)
def get_actual_inflation() -> dict[int, float]:
    df = load_raw_inflation_data()
    return {
        to_period(row.year, row.season): float(row.annual_inflation)
        for row in df.itertuples()
    }


@lru_cache(maxsize=64)
def get_inflation(period: int) -> float:
    """Annual inflation (%) for a period: the recorded value if known, otherwise the forecast."""
    actual = get_actual_inflation()
    if period in actual:
        return actual[period]

    year, season = from_period(period)
    return float(predict_inflation(year, season))


def expected_log_growth(years_back: int, annual_inflation: float) -> float:
    return years_back * float(np.log1p(annual_inflation / 100))


def find_base_period(
    prices: dict[tuple[str, int], float],
    product_name: str,
    target_period: int,
    last_known_period: int | None = None,
) -> tuple[int, int] | None:
    """Latest same-season period with a known price, at least a year before the target."""
    for years_back in range(1, MAX_YEARS_BACK + 1):
        base_period = target_period - 4 * years_back
        if last_known_period is not None and base_period > last_known_period:
            continue
        if (product_name, base_period) in prices:
            return base_period, years_back
    return None


def build_training_frame(
    prices: dict[tuple[str, int], float],
    inflation: dict[int, float],
    last_period: int | None = None,
) -> tuple[pd.DataFrame, np.ndarray]:
    """One example per observed price and years_back; the target is the change the inflation baseline missed."""
    rows, targets = [], []
    for (product_name, period), price in prices.items():
        if last_period is not None and period > last_period:
            continue
        if period not in inflation:
            continue

        for years_back in TRAINING_YEARS_BACK:
            base_price = prices.get((product_name, period - 4 * years_back))
            if base_price is None:
                continue

            rows.append(
                {
                    "product_name": product_name,
                    "season": from_period(period)[1],
                    "years_back": years_back,
                }
            )
            targets.append(
                float(np.log(price / base_price))
                - expected_log_growth(years_back, inflation[period])
            )

    if not rows:
        raise ValueError("Egitim icin yeterli fiyat gecmisi bulunamadi.")

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS), np.array(targets)


def build_price_model() -> CatBoostRegressor:
    # Deliberately small: with ~15 products and ~12 years, deeper models learned
    # one-off price shocks (e.g. 2022) and repeated them in later years.
    return CatBoostRegressor(
        iterations=200,
        learning_rate=0.03,
        depth=2,
        l2_leaf_reg=20,
        loss_function="RMSE",
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
    )


def fit_price_model(features: pd.DataFrame, targets: np.ndarray) -> CatBoostRegressor:
    model = build_price_model()
    model.fit(features, targets, cat_features=CATEGORICAL_FEATURES)
    return model


def train_price_model(model_path: Path = MODEL_PATH) -> CatBoostRegressor:
    features, targets = build_training_frame(get_prices(), get_actual_inflation())
    model = fit_price_model(features, targets)

    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    return model


@lru_cache(maxsize=1)
def get_price_model() -> CatBoostRegressor:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Fiyat modeli bulunamadi: {MODEL_PATH}. "
            "Egitmek icin: python -m app.services.price_prediction"
        )

    model = CatBoostRegressor()
    model.load_model(str(MODEL_PATH))
    return model


def forecast_price(
    model: CatBoostRegressor,
    product_name: str,
    base_price: float,
    target_season: str,
    years_back: int,
    annual_inflation: float,
) -> tuple[float, float]:
    """Returns (predicted price, model adjustment in log space)."""
    features = pd.DataFrame(
        [{"product_name": product_name, "season": target_season, "years_back": years_back}],
        columns=FEATURE_COLUMNS,
    )
    adjustment = float(model.predict(features)[0])
    predicted = base_price * np.exp(expected_log_growth(years_back, annual_inflation) + adjustment)
    return float(predicted), adjustment


def predict_product_price(
    product_name: str,
    target_season: str,
    today: date | None = None,
) -> dict[str, Any]:
    target_season = validate_season(target_season)
    target_year = get_target_year(target_season, today)
    target_period = to_period(target_year, target_season)

    prices = get_prices()
    base = find_base_period(prices, product_name, target_period)
    if base is None:
        raise ValueError(
            f"{product_name} icin {target_season} sezonunda gecmis fiyat verisi bulunamadi."
        )

    base_period, years_back = base
    base_price = prices[(product_name, base_period)]
    annual_inflation = get_inflation(target_period)

    predicted_price, adjustment = forecast_price(
        get_price_model(),
        product_name=product_name,
        base_price=base_price,
        target_season=target_season,
        years_back=years_back,
        annual_inflation=annual_inflation,
    )

    return {
        "product_name": product_name,
        "season": target_season,
        "year": target_year,
        "base_year": from_period(base_period)[0],
        "base_price": round(base_price, 2),
        "years_back": years_back,
        "annual_inflation": round(annual_inflation, 2),
        "model_adjustment": round(adjustment, 4),
        "predicted_price": round(max(0.0, predicted_price), 2),
    }


if __name__ == "__main__":
    train_price_model()
    get_price_model.cache_clear()
    print(f"Model kaydedildi: {MODEL_PATH}")
    print("Dogruluk olcumu icin: python -m app.scripts.price_backtest\n")

    for product in ["DOMATES SALKIM", "BAKLA", "KARPUZ", "BIBER SIVRI", "KARNABAHAR", "BROKOLI"]:
        for season in SEASON_SEQUENCE:
            result = predict_product_price(product, season)
            print(
                f"{product:<16} {result['season']:<7} {result['year']}  "
                f"{result['predicted_price']:>7} TL  "
                f"(taban {result['base_year']}: {result['base_price']} TL, "
                f"enflasyon %{result['annual_inflation']})"
            )
