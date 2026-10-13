import re
import time
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://www.izmir.bel.tr/tr/SeffafIzmir/HalFiyatlari/sebze"
SOURCE = "İzmir Büyükşehir Belediyesi - Şeffaf İzmir"

# Daily prices downloaded from the same source; shown when the website can't be reached.
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
FALLBACK_PATH = ROOT_DIR / "data" / "raw_data" / "marketplace_data" / "izbb_hal_fiyatlari_2026_gecici.csv"

# Live prices change once a day, and a failed request makes the page wait ~10 seconds,
# so successes are reused for an hour and a failing source is skipped for half an hour.
LIVE_CACHE_SECONDS = 60 * 60
RETRY_AFTER_FAILURE_SECONDS = 30 * 60

ALLOWED_PRODUCTS = [
    "DOMATES SALKIM",
    "BİBER SİVRİ",
    "SALATALIK SİLOR",
    "KABAK TAZE",
    "KARPUZ",
    "PATLICAN UZUN",
    "MARUL",
    "ISPANAK",
    "BROKOLI",
    "BEZELYE",
    "LAHANA BEYAZ",
    "LAHANA KIRMIZI",
    "BAKLA",
    "PIRASA",
    "KARNABAHAR",
]

# Ministry of Trade's market registry: daily national averages, used when the
# İzmir site is down. Product names there differ, so each product is mapped to
# (product name, variety); None means a volume-weighted average of all varieties.
NATIONAL_URL = "https://www.hal.gov.tr/Sayfalar/FiyatDetaylari.aspx"
NATIONAL_SOURCE = "T.C. Ticaret Bakanlığı - Hal Kayıt Sistemi"
NATIONAL_PRODUCTS = {
    "DOMATES SALKIM": ("DOMATES", "SALKIM"),
    "BİBER SİVRİ": ("BİBER SİVRİ", None),
    "SALATALIK SİLOR": ("SALATALIK", "SİLOR"),
    "KABAK TAZE": ("KABAK", None),
    "KARPUZ": ("KARPUZ", None),
    "PATLICAN UZUN": ("PATLICAN", "DİĞER"),
    "MARUL": ("MARUL GÖBEKLİ", None),
    "ISPANAK": ("ISPANAK", None),
    "BROKOLI": ("BROKOLİ", None),
    "BEZELYE": ("BEZELYE TAZE", None),
    "LAHANA BEYAZ": ("BEYAZ LAHANA", None),
    "LAHANA KIRMIZI": ("KIRMIZI LAHANA", None),
    "BAKLA": ("BAKLA TAZE", None),
    "PIRASA": ("PIRASA", None),
    "KARNABAHAR": ("KARNABAHAR", None),
}


def fix_encoding(value):
    value = str(value)

    if any(bad in value for bad in ["Ã", "Ä", "Å"]):
        try:
            return value.encode("latin1").decode("utf-8")
        except UnicodeError:
            return value

    return value


def normalize_text(value):
    value = fix_encoding(value).upper().strip()

    value = (
        value
        .replace("İ", "I")
        .replace("Ş", "S")
        .replace("Ğ", "G")
        .replace("Ü", "U")
        .replace("Ö", "O")
        .replace("Ç", "C")
    )

    return " ".join(value.split())


NORMALIZED_ALLOWED_PRODUCTS = [
    normalize_text(product)
    for product in ALLOWED_PRODUCTS
]


def parse_price(value):
    value = fix_encoding(value)
    value = value.replace("TL", "")
    value = value.replace("En Az:", "")
    value = value.replace("En Çok:", "")
    value = value.replace("Ortalama:", "")
    value = value.strip()
    value = value.replace(".", "").replace(",", ".")

    return float(value)


def match_allowed_product(name):
    """Returns (allowed product, is exact match) or (None, False).

    The market lists varieties such as "MARUL KIVIRCIK" next to "MARUL"; an exact
    name must win over a variety that merely contains it.
    """
    normalized_name = normalize_text(name)

    if normalized_name in NORMALIZED_ALLOWED_PRODUCTS:
        return normalized_name, True

    for allowed_product in NORMALIZED_ALLOWED_PRODUCTS:
        if allowed_product in normalized_name:
            return allowed_product, False

    return None, False


def is_allowed_product(name):
    return match_allowed_product(name)[0] is not None


def get_display_product_name(normalized_name):
    for product in ALLOWED_PRODUCTS:
        if normalize_text(product) == normalized_name:
            return product

    return normalized_name


def build_price_list(found_prices, missing_note):
    prices = []

    for allowed_product in NORMALIZED_ALLOWED_PRODUCTS:
        if allowed_product in found_prices:
            prices.append(found_prices[allowed_product])
        else:
            prices.append({
                "type": "-",
                "product_name": get_display_product_name(allowed_product),
                "market_product_name": None,
                "unit": "-",
                "min_price": None,
                "max_price": None,
                "average_price": None,
                "price_found": False,
                "is_current": False,
                "note": missing_note,
            })

    return prices


def fetch_daily_hal_prices(target_date=None):
    params = {}

    if target_date:
        params["tarih"] = target_date

    response = requests.get(
        URL,
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=5,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    text = soup.get_text("\n", strip=True)
    text = fix_encoding(text)

    pattern = re.compile(
        r"(SEBZE|MEYVE|İTHAL|ITHAL)\s+"
        r"(.+?)\s+"
        r"Birim:\s*(.+?)\s+"
        r"En Az:\s*([\d\.,]+)\s+"
        r"En Çok:\s*([\d\.,]+)\s+"
        r"Ortalama:\s*([\d\.,]+)",
        re.DOTALL,
    )

    found_prices = {}
    exact_matches = set()

    for match in pattern.finditer(text):
        product_type = fix_encoding(match.group(1)).strip()
        product_name = fix_encoding(match.group(2)).strip()
        unit = fix_encoding(match.group(3)).strip()

        matched_allowed_product, is_exact = match_allowed_product(product_name)
        if matched_allowed_product is None:
            continue
        if matched_allowed_product in exact_matches:
            continue

        try:
            min_price = parse_price(match.group(4))
            max_price = parse_price(match.group(5))
            average_price = parse_price(match.group(6))
        except ValueError:
            continue

        if is_exact:
            exact_matches.add(matched_allowed_product)
        elif matched_allowed_product in found_prices:
            continue

        found_prices[matched_allowed_product] = {
            "type": product_type,
            "product_name": get_display_product_name(matched_allowed_product),
            "market_product_name": product_name,
            "unit": unit,
            "min_price": min_price,
            "max_price": max_price,
            "average_price": average_price,
            "price_found": True,
            "is_current": True,
            "note": "Güncel hal fiyatı",
        }

    prices = build_price_list(found_prices, "Bugünkü hal fiyatı bulunamadı.")

    return {
        "source": SOURCE,
        "date": target_date or date.today().isoformat(),
        "is_live": True,
        "message": None,
        "count": len(prices),
        "prices": prices,
    }


def parse_number(value):
    return float(value.replace(".", "").replace(",", "."))


def fetch_national_hal_prices():
    """Daily national average prices from the market registry's full-list export."""
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"

    page = BeautifulSoup(session.get(NATIONAL_URL, timeout=15).text, "html.parser")
    form = {
        field.get("name"): field.get("value", "")
        for field in page.find_all("input")
        if field.get("name") and field.get("type") in ("hidden", "text")
    }
    # The form's control names are generated by the site, so find them instead of hard-coding them.
    buttons = [field.get("name") for field in page.find_all("input") if str(field.get("name")).endswith("$btnExcel")]
    if not buttons:
        raise ValueError("Hal Kayıt Sistemi sayfasının yapısı değişmiş.")
    form[buttons[0]] = "Excel'e Çıkar"
    form[buttons[0].replace("$btnExcel", "$rblExcelOptions")] = "2"  # all pages

    response = session.post(NATIONAL_URL, data=form, timeout=30)
    response.raise_for_status()
    table = BeautifulSoup(response.content.decode("utf-16"), "html.parser")

    data_date = None
    rows = []
    for tr in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["td", "th"])]
        date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4}) Tarihli Veriler", " ".join(cells))
        if date_match:
            day, month, year = date_match.groups()
            data_date = f"{year}-{month}-{day}"
        if len(cells) == 6 and cells[2].startswith("Geleneksel"):
            rows.append(cells)

    found_prices = {}
    for product, (market_name, variety) in NATIONAL_PRODUCTS.items():
        matches = [
            row for row in rows
            if row[0] == market_name and (variety is None or row[1] == variety)
        ]
        try:
            weighted = [(parse_number(row[3]), parse_number(row[4])) for row in matches]
        except ValueError:
            continue
        volume = sum(amount for _, amount in weighted)
        if volume <= 0:
            continue

        found_prices[normalize_text(product)] = {
            "type": "SEBZE",
            "product_name": product,
            "market_product_name": market_name if variety is None else f"{market_name} ({variety})",
            "unit": matches[0][5].upper(),
            "min_price": None,
            "max_price": None,
            "average_price": round(sum(price * amount for price, amount in weighted) / volume, 2),
            "price_found": True,
            "is_current": True,
            "note": "Türkiye ortalaması",
        }

    prices = build_price_list(found_prices, "Hal Kayıt Sistemi'nde fiyat bulunamadı.")

    return {
        "source": NATIONAL_SOURCE,
        "date": data_date or date.today().isoformat(),
        "is_live": True,
        "message": (
            "İzmir Büyükşehir Belediyesi'nin sitesine şu an ulaşılamıyor. "
            "Ticaret Bakanlığı Hal Kayıt Sistemi'nden Türkiye geneli günlük ortalama fiyatlar gösteriliyor."
        ),
        "count": len(prices),
        "prices": prices,
    }


@lru_cache(maxsize=1)
def load_last_known_prices(path=FALLBACK_PATH):
    """Latest recorded price of each product in the downloaded market data."""
    df = pd.read_csv(path, engine="python", on_bad_lines="skip")
    df["TARIH"] = pd.to_datetime(df["TARIH"], errors="coerce")
    df = df.dropna(subset=["TARIH", "MAL_ADI", "ORTALAMA_FIYAT"])

    matches = df["MAL_ADI"].map(match_allowed_product)
    df["allowed_product"] = matches.map(lambda match: match[0])
    df["is_exact"] = matches.map(lambda match: match[1])
    df = df.dropna(subset=["allowed_product"])

    found_prices = {}
    price_dates = []
    for allowed_product, rows in df.groupby("allowed_product"):
        # Prefer the product itself over a variety, then the most recent day.
        row = rows.sort_values(["is_exact", "TARIH"]).iloc[-1]
        price_date = row["TARIH"].date().isoformat()
        price_dates.append(price_date)
        found_prices[allowed_product] = {
            "type": str(row["MAL_TIPI"]) if pd.notna(row["MAL_TIPI"]) else "-",
            "product_name": get_display_product_name(allowed_product),
            "market_product_name": str(row["MAL_ADI"]).strip(),
            "unit": str(row["BIRIM"]) if pd.notna(row["BIRIM"]) else "-",
            "min_price": float(row["ASGARI_FIYAT"]),
            "max_price": float(row["AZAMI_FIYAT"]),
            "average_price": float(row["ORTALAMA_FIYAT"]),
            "price_found": True,
            "is_current": False,
            "note": f"Son bilinen fiyat ({price_date})",
        }

    prices = build_price_list(found_prices, "Kayıtlı fiyat bulunamadı.")

    return {
        "source": SOURCE,
        "date": max(price_dates, default=None),
        "is_live": False,
        "message": (
            "İzmir Büyükşehir Belediyesi'nin sitesine şu an ulaşılamıyor. "
            "Kayıtlı verilerdeki son hal fiyatları gösteriliyor."
        ),
        "count": len(prices),
        "prices": prices,
    }


_cache = {}


def _from_live_source(name, fetch):
    """Cached result of a live source, or None while it's failing."""
    now = time.monotonic()
    entry = _cache.setdefault(name, {"result": None, "fetched_at": 0.0, "failed_at": None})

    if entry["result"] and now - entry["fetched_at"] < LIVE_CACHE_SECONDS:
        return entry["result"]
    if entry["failed_at"] is not None and now - entry["failed_at"] < RETRY_AFTER_FAILURE_SECONDS:
        return None

    try:
        result = fetch()
        # A page that loads but yields no prices means its layout changed.
        if any(item["price_found"] for item in result["prices"]):
            entry.update(result=result, fetched_at=now, failed_at=None)
            return result
    except (requests.RequestException, ValueError, UnicodeError):
        pass

    entry["failed_at"] = now
    return None


def get_hal_prices():
    """Today's İzmir prices; else today's national averages; else the last recorded İzmir prices."""
    return (
        _from_live_source("izmir", fetch_daily_hal_prices)
        or _from_live_source("national", fetch_national_hal_prices)
        or load_last_known_prices()
    )
