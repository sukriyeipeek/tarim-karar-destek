import requests

def get_usd_try():
    url = "https://open.er-api.com/v6/latest/USD"

    response = requests.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()

    return data["rates"]["TRY"]
