import csv
import os
import random
import re
import sys
import time
from curl_cffi import requests

BASE_URL = "https://letterboxd.com"
OUTPUT_FILE = "all_popular_lists_entries.csv"

# Persistent browser session
session = requests.Session(impersonate="chrome120")
session.headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://letterboxd.com/",
}

# Cache to avoid requesting the same movie twice
# { "parasite-2019": "496243", ... }
SLUG_TO_TMDB_CACHE = {}

def fetch_html(url, retries=3):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 403:
                print(f"\n[!] 403 Blocked on {url}. Cloudflare challenge triggered.")
                time.sleep(15)
            elif resp.status_code == 429:
                print(f"\n[!] 429 Rate limited. Cooling down for 30s...")
                time.sleep(30)
            elif resp.status_code == 404:
                return ""
        except Exception:
            time.sleep(3)
    return ""

def get_tmdb_id(film_slug):
    """
    Fetches the TMDb ID from the movie's main page.
    Uses memory cache so each film is only fetched ONCE.
    """
    if film_slug in SLUG_TO_TMDB_CACHE:
        return SLUG_TO_TMDB_CACHE[film_slug]

    url = f"{BASE_URL}/film/{film_slug}/"
    html = fetch_html(url)
    if not html:
        SLUG_TO_TMDB_CACHE[film_slug] = ""
        return ""

    # Matches: https://www.themoviedb.org/movie/12345/
    match = re.search(r'href="https://www\.themoviedb\.org/movie/(\d+)/"', html)
    tmdb_id = match.group(1) if match else ""

    SLUG_TO_TMDB_CACHE[film_slug] = tmdb_id

    # Small jitter so we don't spam while looking up films
    time.sleep(random.uniform(0.3, 0.7))
    return tmdb_id

def get_popular_list_urls(start_page=1, end_page=15):
    list_urls = []
    print(f"=== Harvesting list URLs (Pages {start_page} to {end_page}) ===")

    for page in range(start_page, end_page + 1):
        url = f"{BASE_URL}/lists/popular/page/{page}/"
        html = fetch_html(url)

        found = re.findall(r'href="(/[^/]+/list/[^/]+/)">', html)
        unique = [u for u in dict.fromkeys(found) if not u.startswith("/films/")]

        print(f"  Page {page:02d}: Found {len(unique)} lists")
        list_urls.extend(unique)

        time.sleep(random.uniform(1.0, 1.8))

    return list(dict.fromkeys(list_urls))

def stream_list_to_csv(list_path, writer, file_handle, fetch_tmdb=True):
    page = 1
    total_films = 0

    while True:
        url = f"{BASE_URL}{list_path}page/{page}/"
        html = fetch_html(url)

        slugs = re.findall(r'data-film-slug="([^"]+)"', html)
        if not slugs:
            slugs = re.findall(r'data-item-slug="([^"]+)"', html)

        if not slugs:
            break

        for slug in slugs:
            total_films += 1

            # Fetch or retrieve cached TMDb ID
            tmdb_id = get_tmdb_id(slug) if fetch_tmdb else ""

            writer.writerow([list_path, total_films, slug, tmdb_id])

        file_handle.flush()

        sys.stdout.write(f"\r    ...page {page} ({total_films} films processed)")
        sys.stdout.flush()

        if 'class="next"' not in html:
            break

        page += 1
        time.sleep(random.uniform(0.8, 1.5))

    return total_films

def main():
    list_urls = get_popular_list_urls(1, 15)
    print(f"\nTotal lists ready to scrape: {len(list_urls)}")

    file_exists = os.path.exists(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["list_path", "rank", "film_slug", "tmdb_id"])

        for idx, list_path in enumerate(list_urls, start=1):
            print(f"\n[{idx}/{len(list_urls)}] Scraping: {list_path}")
            count = stream_list_to_csv(list_path, writer, f, fetch_tmdb=True)
            print(f"\n  -> Completed: {count} films.")
            time.sleep(random.uniform(1.2, 2.2))

if __name__ == "__main__":
    main()