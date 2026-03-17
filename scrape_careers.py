"""
Scrape FBRef player pages to extract career club histories.
For each player in the combo data, fetches their season-by-season stats
and builds an ordered list of clubs with year ranges and appearances.

Output: data/careers.json

Usage (via main.py):
    python main.py careers           - Scrape all players from scratch
    python main.py careers --resume  - Skip already-scraped players
"""

import json
import os
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup, Comment
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrape_teams import launch_browser, wait_for_page_ready

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
COMBOS_DIR = os.path.join(DATA_DIR, "combos")
OUTPUT_FILE = os.path.join(DATA_DIR, "careers.json")
NATIONALITY_FILE = os.path.join(DATA_DIR, "nationalities.json")

PLAYER_BASE_URL = "https://fbref.com/en/players/{player_id}/"
REQUEST_DELAY = 4       # seconds between requests
SAVE_INTERVAL = 20      # save progress every N players
MIN_APPS = 1            # minimum appearances to count a stint


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_player_ids():
    """
    Extract all unique player IDs from the scraped combo result files.
    Returns a list of (player_id, player_name) tuples, sorted by name.
    """
    player_map = {}  # id -> name (best/longest version wins)

    for filename in ["olympiacos_fc_top5.json", "panathinaikos_fc_top5.json"]:
        filepath = os.path.join(COMBOS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  Warning: {filename} not found, skipping.")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for combo in data.get("combos", []):
            for player in combo.get("players", []):
                link = player.get("Player_link", "")
                match = re.search(r'/players/([a-z0-9]+)/', link)
                if not match:
                    continue
                pid = match.group(1)
                name = player.get("Player", "")
                # Keep the longest version of the name (most complete)
                if pid not in player_map or len(name) > len(player_map[pid]):
                    player_map[pid] = name

    players = sorted(player_map.items(), key=lambda x: x[1])
    return players


def load_existing_careers():
    """Load an existing careers.json file for resume support."""
    if not os.path.exists(OUTPUT_FILE):
        return {}
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Strip the metadata key if present
    return {k: v for k, v in data.items() if k != "_meta"}


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _find_career_table(soup):
    """
    Locate the season-by-season stats table on a player page.

    FBRef serves tables inside HTML comment blocks server-side and uses
    JavaScript to uncomment them.  If Selenium captured the page before
    that JS ran the tables are still in comments, so we check both places.
    """
    # Patterns to match, in preference order
    id_patterns = [
        r"stats_standard_dom_lg",
        r"stats_standard_club_lg",
        r"stats_standard",
    ]

    # ── Pass 1: normal DOM (Selenium likely already uncommented them) ──
    for pattern in id_patterns:
        t = soup.find("table", id=re.compile(pattern))
        if t:
            return t

    # Any table with a team column
    for t in soup.find_all("table"):
        if t.find(attrs={"data-stat": "team"}):
            return t

    # ── Pass 2: search inside HTML comment nodes ───────────────────────
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        inner = BeautifulSoup(comment, "lxml")
        for pattern in id_patterns:
            t = inner.find("table", id=re.compile(pattern))
            if t:
                return t
        for t in inner.find_all("table"):
            if t.find(attrs={"data-stat": "team"}):
                return t

    return None


def parse_player_nationality(soup):
    """
    Extract a player's nationality from their FBRef page.
    Returns a country name string or None.
    """
    meta = soup.find("div", id="meta")
    if not meta:
        return None

    # Strategy 1: anchor next to a flag span (f-i f-XX class)
    for span in meta.find_all("span", class_=re.compile(r'\bf-i\b')):
        for a in [span.find_previous_sibling("a"), span.find_next_sibling("a")]:
            if a and "/country/" in a.get("href", ""):
                return a.get_text(strip=True)

    # Strategy 2: any anchor pointing to a country players page
    for p in meta.find_all("p"):
        for a in p.find_all("a", href=re.compile(r'/en/country/')):
            return a.get_text(strip=True)

    return None


def parse_player_career(html):
    """
    Parse a player's FBRef page and return an ordered list of career stints.

    Each stint is a dict:
        {club, start_year, end_year, apps, goals}

    Rules applied:
    - Only the first occurrence of each club is kept (handles loan returns).
    - Stints with fewer than MIN_APPS appearances are filtered out.
    - Results are sorted chronologically by start_year.
    """
    soup = BeautifulSoup(html, "lxml")
    nationality = parse_player_nationality(soup)
    table = _find_career_table(soup)

    if not table:
        return None, nationality  # page structure not recognised

    tbody = table.find("tbody")
    if not tbody:
        return None, nationality

    raw_rows = []

    for row in tbody.find_all("tr"):
        classes = row.get("class", [])
        # Skip sub-headers and spacer rows injected into tbody
        if any(c in classes for c in ("thead", "over_header", "spacer", "partial_table")):
            continue

        year_cell   = row.find(attrs={"data-stat": "year_id"})
        team_cell   = row.find(attrs={"data-stat": "team"})
        games_cell  = row.find(attrs={"data-stat": "games"})
        goals_cell  = row.find(attrs={"data-stat": "goals"})

        if not year_cell or not team_cell:
            continue

        year_text = year_cell.get_text(strip=True)
        team_text = team_cell.get_text(strip=True)

        if not year_text or not team_text or team_text in ("-", ""):
            continue

        # Parse start year from "2006-2007" or "2023"
        year_match = re.match(r"(\d{4})", year_text)
        if not year_match:
            continue
        start_year = int(year_match.group(1))

        games_text = games_cell.get_text(strip=True) if games_cell else ""
        try:
            apps = int(games_text)
        except (ValueError, TypeError):
            apps = 0

        goals_text = goals_cell.get_text(strip=True) if goals_cell else ""
        try:
            goals = int(goals_text)
        except (ValueError, TypeError):
            goals = 0

        raw_rows.append({"squad": team_text, "year": start_year, "apps": apps, "goals": goals})

    if not raw_rows:
        return [], nationality

    return _process_raw_rows(raw_rows), nationality


def _process_raw_rows(raw_rows):
    """
    Group consecutive same-club rows into stints, deduplicate by first
    occurrence, and filter by minimum appearances.
    """
    # Step 1: group consecutive seasons at the same club
    grouped = []
    current = None

    for row in raw_rows:
        if current and row["squad"] == current["club"]:
            # Extend the current stint
            current["end_year"] = row["year"] + 1
            current["apps"] += row["apps"]
            current["goals"] += row["goals"]
        else:
            if current:
                grouped.append(current)
            current = {
                "club": row["squad"],
                "start_year": row["year"],
                "end_year": row["year"] + 1,
                "apps": row["apps"],
                "goals": row["goals"],
            }

    if current:
        grouped.append(current)

    # Step 2: first occurrence of each club only + minimum apps filter
    seen = set()
    result = []
    for stint in grouped:
        if stint["apps"] < MIN_APPS:
            continue
        if stint["club"] in seen:
            continue
        seen.add(stint["club"])
        result.append(stint)

    return result


# ---------------------------------------------------------------------------
# Per-player scraping
# ---------------------------------------------------------------------------

def scrape_player_career(driver, player_id):
    """
    Navigate to a player's FBRef page and return their processed career,
    or None on failure.
    """
    url = PLAYER_BASE_URL.format(player_id=player_id)

    try:
        driver.get(url)
    except Exception as e:
        print(f"    Navigation error: {e}")
        return None

    # Handle Cloudflare challenge pages
    if "just a moment" in driver.title.lower():
        print("    Cloudflare challenge — waiting...")
        if not wait_for_page_ready(driver, timeout=60):
            return None

    # Wait for any stats table to appear
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table, #content"))
        )
    except Exception:
        pass  # proceed anyway and let the parser handle the result

    time.sleep(3)  # allow FBRef's JS to uncomment stats tables

    career, nationality = parse_player_career(driver.page_source)
    return career, nationality


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def _save_careers(careers_dict):
    """Persist the careers dict to disk with metadata."""
    os.makedirs(DATA_DIR, exist_ok=True)
    output = {
        "_meta": {
            "scraped_at": datetime.now().isoformat(),
            "total_players": len(careers_dict),
            "with_career": sum(
                1 for v in careers_dict.values() if v is not None and len(v) >= 4
            ),
        }
    }
    output.update(careers_dict)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"    Saved {len(careers_dict)} players → {OUTPUT_FILE}")


def _save_nationalities(nationalities_dict):
    """Persist the nationalities dict to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NATIONALITY_FILE, "w", encoding="utf-8") as f:
        json.dump(nationalities_dict, f, indent=2, ensure_ascii=False)
    print(f"    Saved {len(nationalities_dict)} nationalities → {NATIONALITY_FILE}")


def load_existing_nationalities():
    if not os.path.exists(NATIONALITY_FILE):
        return {}
    with open(NATIONALITY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _needs_goals(stints):
    """Return True if any stint in the list is missing the 'goals' key."""
    if not stints:
        return False
    return any("goals" not in s for s in stints)


def run_career_scrape(resume=False, goals_only=False, headless=False):
    """
    Scrape career data for all players found in the combo files.

    Args:
        resume:     If True, skip players already present in careers.json.
        goals_only: If True, only re-scrape players whose stints lack goal data.
        headless:   Run Chrome headlessly (may fail Cloudflare more easily).
    """
    print("\n=== Career Scraper ===")

    all_players = load_player_ids()
    if not all_players:
        print("No players found. Run 'python main.py batch' first to populate combo data.")
        return

    print(f"Found {len(all_players)} unique players in combo data.")

    careers = {}
    nationalities = load_existing_nationalities()
    if resume or goals_only:
        careers = load_existing_careers()
        skipped = sum(1 for pid, _ in all_players if pid in careers)
        print(f"Resume mode: {skipped}/{len(all_players)} already scraped.")

    if goals_only:
        # Re-scrape only players whose existing stints are missing goal data
        to_scrape = [
            (pid, name) for pid, name in all_players
            if pid not in careers or _needs_goals(careers.get(pid) or [])
        ]
        print(f"Goals mode: {len(to_scrape)} players need goal data added.")
    else:
        to_scrape = [(pid, name) for pid, name in all_players if pid not in careers]
    total = len(to_scrape)
    print(f"Players to scrape: {total}")

    if total == 0:
        print("Nothing to do.")
        return

    est_minutes = (total * REQUEST_DELAY) / 60
    print(f"Estimated time: ~{est_minutes:.0f} minutes at {REQUEST_DELAY}s/request\n")

    driver = launch_browser(headless=headless)

    try:
        print("--- Establishing FBRef session ---")
        driver.get("https://fbref.com/")
        if not wait_for_page_ready(driver):
            print("Could not pass Cloudflare. Aborting.")
            return
        print()
        time.sleep(2)

        for i, (player_id, player_name) in enumerate(to_scrape, start=1):
            print(f"[{i}/{total}] {player_name} ({player_id})")

            career, nationality = scrape_player_career(driver, player_id)

            if nationality:
                nationalities[player_id] = nationality

            if career is None:
                print(f"    ✗ Failed to parse page")
                careers[player_id] = None
            elif len(career) < 2:
                print(f"    – Only {len(career)} usable stint(s), storing anyway")
                careers[player_id] = career
            else:
                nat_str = f" [{nationality}]" if nationality else ""
                club_names = " → ".join(s["club"] for s in career)
                print(f"    ✓ {len(career)} clubs{nat_str}: {club_names}")
                careers[player_id] = career

            # Auto-save progress
            if i % SAVE_INTERVAL == 0:
                print(f"  [Auto-save at {i}/{total}]")
                _save_careers(careers)
                _save_nationalities(nationalities)

            if i < total:
                time.sleep(REQUEST_DELAY)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    _save_careers(careers)
    _save_nationalities(nationalities)

    valid = sum(1 for v in careers.values() if v and len(v) >= 4)
    print(f"\n{'='*50}")
    print(f"Scrape complete!")
    print(f"  Total players scraped : {len(careers)}")
    print(f"  With 4+ usable clubs  : {valid}  ← available for Career Path game")
    print(f"  Output                : {OUTPUT_FILE}")
