"""Rolling-origin backtest for the price model.

For each forecast origin the model is trained only on prices up to that season and
then predicts the next four seasons, which are compared with the real prices. This
mirrors how the app is used: a farmer asks in one season about the coming ones.

Two simple methods are reported next to the model; a change to the model is only
an improvement if it beats them:
  B1  last year's price for the same season
  B2  B1 grown by inflation (the model's own starting point)

All methods use the recorded inflation of the target season. In the app that value
comes from the inflation forecast, so real errors are somewhat larger; the
comparison between methods is still fair.

Run from the project root:  python -m app.scripts.price_backtest
"""

import numpy as np
import pandas as pd

from app.services.price_prediction import (
    build_training_frame,
    expected_log_growth,
    find_base_period,
    fit_price_model,
    forecast_price,
    from_period,
    get_actual_inflation,
    get_prices,
    to_period,
)

ORIGINS = [
    to_period(2021, "Fall"),
    to_period(2022, "Fall"),
    to_period(2023, "Fall"),
    to_period(2024, "Fall"),
    to_period(2025, "Summer"),
]
HORIZON = 4
METHODS = ["B1_last_year", "B2_last_year_x_inflation", "model"]


def run_backtest() -> pd.DataFrame:
    prices = get_prices()
    inflation = get_actual_inflation()
    products = sorted({product for product, _ in prices})

    records = []
    for origin in ORIGINS:
        model = fit_price_model(*build_training_frame(prices, inflation, last_period=origin))

        for product in products:
            for target in range(origin + 1, origin + HORIZON + 1):
                actual = prices.get((product, target))
                base = find_base_period(prices, product, target, last_known_period=origin)
                if actual is None or base is None or target not in inflation:
                    continue

                base_period, years_back = base
                base_price = prices[(product, base_period)]
                predicted, _ = forecast_price(
                    model, product, base_price, from_period(target)[1], years_back, inflation[target]
                )
                records.append(
                    {
                        "origin": origin,
                        "product": product,
                        "target": target,
                        "actual": actual,
                        "B1_last_year": base_price,
                        "B2_last_year_x_inflation": base_price
                        * np.exp(expected_log_growth(years_back, inflation[target])),
                        "model": predicted,
                    }
                )

    return pd.DataFrame(records)


def error_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for method in METHODS:
        ape = (frame[method] - frame["actual"]).abs() / frame["actual"] * 100
        # Geometric mean of predicted/actual: -10% means predictions run 10% low.
        bias = np.exp(np.log(frame[method] / frame["actual"]).mean()) * 100 - 100
        rows[method] = {"MAPE %": ape.mean(), "MdAPE %": ape.median(), "bias %": bias}
    return pd.DataFrame(rows).T.round(1)


def mape_by(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return frame.groupby(column).apply(
        lambda group: pd.Series(
            {method: ((group[method] - group["actual"]).abs() / group["actual"] * 100).mean() for method in METHODS}
        ),
        include_groups=False,
    ).round(1)


def main():
    results = run_backtest()

    print(f"Rolling-origin backtest: {len(ORIGINS)} origins, {HORIZON} seasons ahead, {len(results)} predictions\n")
    print(error_summary(results).to_string(), "\n")

    by_origin = mape_by(results, "origin")
    by_origin.index = [f"{year}-{season}" for year, season in map(from_period, by_origin.index)]
    print("MAPE % by forecast origin")
    print(by_origin.to_string(), "\n")

    print("MAPE % by product")
    print(mape_by(results, "product").to_string())


if __name__ == "__main__":
    main()
