import datetime
import requests

def get_week_birthdays(days_ahead=7):
    """
    Fetch footballers whose birthdays fall within the next `days_ahead` days.
    Returns list of dicts with name, dob, and photo_url.
    """
    today = datetime.date.today()
    future = today + datetime.timedelta(days=days_ahead)

    # Extract month/day ranges
    start_month, start_day = today.month, today.day
    end_month, end_day = future.month, future.day

    # SPARQL supports extracting MONTH() and DAY() separately, but not date addition easily.
    # So we handle two cases: within the same month OR crossing month boundary.
    same_month = (start_month == end_month)

    if same_month:
        filter_condition = f"""
        FILTER(MONTH(?dob) = {start_month} && DAY(?dob) >= {start_day} && DAY(?dob) <= {end_day})
        """
    else:
        # Covers two ranges: from start_day..end_of_month and from 1..end_day of next month
        filter_condition = f"""
        FILTER(
            (MONTH(?dob) = {start_month} && DAY(?dob) >= {start_day}) ||
            (MONTH(?dob) = {end_month} && DAY(?dob) <= {end_day})
        )
        """

    query = f"""
    SELECT ?player ?playerLabel ?dob ?image WHERE {{
      ?player wdt:P31 wd:Q5;
              wdt:P106 wd:Q937857;
              wdt:P569 ?dob.
      {filter_condition}
      OPTIONAL {{ ?player wdt:P18 ?image. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 100
    """

    url = "https://query.wikidata.org/sparql"
    r = requests.get(url, params={"format": "json", "query": query}, timeout=30)

    players = []
    if r.status_code == 200:
        for item in r.json()["results"]["bindings"]:
            players.append({
                "name": item["playerLabel"]["value"],
                "dob": item["dob"]["value"],
                "photo": item.get("image", {}).get("value", "")
            })
    else:
        print("SPARQL error:", r.status_code, r.text[:300])

    return players
