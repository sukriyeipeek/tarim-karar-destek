import requests

from app.services import hal_price_service as hal


def test_exact_product_name_wins_over_a_variety():
    assert hal.match_allowed_product("MARUL") == ("MARUL", True)
    assert hal.match_allowed_product("MARUL  KIVIRCIK") == ("MARUL", False)
    assert hal.match_allowed_product("KABAK TAZE") == ("KABAK TAZE", True)
    assert hal.match_allowed_product("ELMA") == (None, False)


def test_last_known_prices_prefer_the_product_over_its_varieties(tmp_path):
    csv = tmp_path / "hal.csv"
    csv.write_text(
        "MAL_ADI,BIRIM,ASGARI_FIYAT,AZAMI_FIYAT,ORTALAMA_FIYAT,MAL_TIPI,TARIH\n"
        "MARUL,ADET,10,20,15,SEBZE,2026-07-27\n"
        "MARUL KIVIRCIK,ADET,30,40,35,SEBZE,2026-07-28\n"
        "KARPUZ,KG,5,14,9.5,SEBZE,2026-07-28\n",
        encoding="utf-8",
    )

    result = hal.load_last_known_prices.__wrapped__(csv)
    prices = {item["product_name"]: item for item in result["prices"]}

    assert result["is_live"] is False
    assert result["date"] == "2026-07-28"
    assert prices["MARUL"]["average_price"] == 15.0
    assert prices["MARUL"]["unit"] == "ADET"
    assert prices["KARPUZ"]["note"] == "Son bilinen fiyat (2026-07-28)"
    assert prices["BAKLA"]["price_found"] is False


def live_result(source):
    return {"source": source, "prices": [{"price_found": True}]}


def test_falls_back_through_sources_and_skips_a_failing_one(monkeypatch):
    calls = []

    def izmir_down():
        calls.append("izmir")
        raise requests.ConnectionError("dns")

    def national():
        calls.append("national")
        return live_result("national")

    monkeypatch.setattr(hal, "_cache", {})
    monkeypatch.setattr(hal, "fetch_daily_hal_prices", izmir_down)
    monkeypatch.setattr(hal, "fetch_national_hal_prices", national)

    assert hal.get_hal_prices()["source"] == "national"
    assert hal.get_hal_prices()["source"] == "national"
    # The failing site is not retried right away, and the national result is cached.
    assert calls == ["izmir", "national"]


def test_uses_recorded_prices_when_every_live_source_fails(monkeypatch):
    def down():
        raise requests.ConnectionError("dns")

    monkeypatch.setattr(hal, "_cache", {})
    monkeypatch.setattr(hal, "fetch_daily_hal_prices", down)
    monkeypatch.setattr(hal, "fetch_national_hal_prices", down)
    monkeypatch.setattr(hal, "load_last_known_prices", lambda: live_result("recorded"))

    assert hal.get_hal_prices()["source"] == "recorded"


def test_izmir_site_is_used_when_it_works(monkeypatch):
    monkeypatch.setattr(hal, "_cache", {})
    monkeypatch.setattr(hal, "fetch_daily_hal_prices", lambda: live_result("izmir"))

    assert hal.get_hal_prices()["source"] == "izmir"
