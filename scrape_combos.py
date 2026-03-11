"""
Query FBRef for players who played for selected team combinations.
Uses undetected-chromedriver to bypass Cloudflare protection.
Parses the results HTML table and saves data.
Batch mode accumulates results into a single JSON file.
"""

import json
import os
import re
import time
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrape_teams import launch_browser, wait_for_page_ready, load_teams, find_team

BASE_URL = "https://fbref.com/en/friv/players-who-played-for-multiple-clubs-countries.fcgi"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
COMBOS_DIR = os.path.join(DATA_DIR, "combos")

REQUEST_DELAY = 4

def slugify(name):
    slug = name.lower()
    slug = re.sub(r"^[a-z]{2,3}:\s*", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug

def build_query_url(t1_id, t2_id, level="franch"):
    return (
        f"{BASE_URL}?level={level}"
        f"&t1={t1_id}&t2={t2_id}&t3=--&t4=--"
    )

def parse_results_page(html_content):
    soup = BeautifulSoup(html_content, "lxml")
    players = []

    # First look for the specific multi-franchise table
    table = soup.find("table", id=re.compile(r"multifranchise_stats_.*"))
    
    # If not found, try any stats table
    if not table:
        table = soup.find("table", class_=re.compile(r"stats_table"))
    
    if not table:
        return players

    headers = []
    thead = table.find("thead")
    if thead:
        header_rows = thead.find_all("tr")
        if header_rows:
            for th in header_rows[-1].find_all(["th", "td"]):
                headers.append(th.get_text(strip=True))

    tbody = table.find("tbody")
    if tbody:
        for tr in tbody.find_all("tr"):
            classes = tr.get("class", [])
            if any("thead" in c or "spacer" in c for c in classes):
                continue
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue

            player = {}
            for i, cell in enumerate(cells):
                key = headers[i] if i < len(headers) else f"col_{i}"
                link = cell.find("a")
                if link and link.get("href"):
                    href = link["href"]
                    player[f"{key}_link"] = (
                        "https://fbref.com" + href if href.startswith("/") else href
                    )
                value = cell.get_text(strip=True)
                player[key] = value if value else None

            if any(v for v in player.values() if v):
                players.append(player)

    return players

def query_combo(driver, team1, team2, level="franch"):
    url = build_query_url(team1["id"], team2["id"], level=level)
    print(f"  Querying: {team1['name']} + {team2['name']}")

    driver.get(url)

    # Check Cloudflare
    title = driver.title
    if "just a moment" in title.lower() or "cloudflare" in title.lower():
        wait_for_page_ready(driver, timeout=60)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table, #content"))
        )
    except Exception:
        pass

    time.sleep(1)
    html = driver.page_source
    players = parse_results_page(html)
    print(f"  Found {len(players)} players")

    # Only return the data we actually want to save
    if not players:
        return None
        
    return {
        "team2_id": team2["id"],
        "team2_name": team2["name"],
        "query_url": url,
        "player_count": len(players),
        "players": players,
    }

def run_batch(squad1_name, top5_only=True, headless=False):
    """
    Run a batch query for a single team against a target group of teams.
    Accumulates all results into a single JSON file.
    """
    teams = load_teams()

    # Find the focus team (squad 1)
    matches = find_team(teams, squad1_name)
    if not matches:
        print(f"Error: No team found matching '{squad1_name}'")
        return
        
    # Prefer exact match
    exact_match = next((m for m in matches if m["name"].lower() == squad1_name.lower()), None)
    focus_team = exact_match if exact_match else matches[0]
    print(f"\nFocus Team (Squad 1): {focus_team['name']} ({focus_team['id']})")

    # Get opponent teams
    opponents = []
    if top5_only:
        top5_prefixes = ["ENG: ", "ESP: ", "GER: ", "ITA: ", "FRA: "]
        opponents = [t for t in teams if any(t["name"].startswith(p) for p in top5_prefixes)]
        print(f"Filtering for Top 5 Leagues... Found {len(opponents)} target teams")
    else:
        opponents = teams
        print(f"Using all {len(opponents)} available teams")

    # Remove the focus team from opponents if present
    opponents = [t for t in opponents if t["id"] != focus_team["id"]]

    total = len(opponents)
    count = 0
    results_list = []
    combos_with_players = 0
    total_players_found = 0

    print(f"\nTotal queries to run: {total}")
    est_minutes = (total * REQUEST_DELAY) / 60
    print(f"Estimated time: ~{est_minutes:.0f} minutes")

    driver = launch_browser(headless=headless)
    try:
        print("\n--- Step 1: Establishing browser session ---")
        driver.get("https://fbref.com/")

        if not wait_for_page_ready(driver):
            print("Failed to get past Cloudflare. Aborting.")
            return

        print("\n--- Step 2: Starting batch queries ---\n")
        time.sleep(2)

        for opp in opponents:
            count += 1
            print(f"\n[{count}/{total}] ---")

            try:
                result = query_combo(driver, focus_team, opp)
                if result:
                    results_list.append(result)
                    combos_with_players += 1
                    total_players_found += result["player_count"]
            except Exception as e:
                print(f"  Error: {e}")

            if count < total:
                time.sleep(REQUEST_DELAY)
                
            # Auto-save progress every 20 queries so we don't lose data if it crashes
            if count % 20 == 0:
                _save_batch_results(focus_team, results_list, top5_only)

    finally:
        try:
            driver.quit()
        except:
            pass
            
    # Final save
    outfile = _save_batch_results(focus_team, results_list, top5_only)

    print(f"\n{'='*50}")
    print(f"Batch complete!")
    print(f"  Total queries: {count}")
    print(f"  Combos with players: {combos_with_players}")
    print(f"  Total unique player-combo pairs: {total_players_found}")
    print(f"  Final Results saved to: {outfile}")

def _save_batch_results(focus_team, results_list, top5_only):
    """Helper to save the accumulated batch results."""
    os.makedirs(COMBOS_DIR, exist_ok=True)
    slug = slugify(focus_team["name"])
    suffix = "_top5" if top5_only else "_all"
    filename = f"{slug}{suffix}.json"
    filepath = os.path.join(COMBOS_DIR, filename)
    
    final_output = {
        "focus_team": focus_team,
        "target_group": "Top 5 European Leagues (ENG, ESP, GER, ITA, FRA)" if top5_only else "All Teams",
        "scraped_at": datetime.now().isoformat(),
        "total_combos_found": len(results_list),
        "total_players": sum(r["player_count"] for r in results_list),
        "combos": results_list
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
        
    print(f"  Progress saved to {filepath}")
    return filepath

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Query FBRef for players who played for multiple clubs."
    )
    parser.add_argument("--t1", help="Team 1 ID")
    parser.add_argument("--t2", help="Team 2 ID")
    parser.add_argument("--batch", help="Run batch for a specific team (e.g. 'Olympiacos')")
    parser.add_argument("--all-teams", action="store_true", help="Batch against ALL teams instead of just Top 5 leagues")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    args = parser.parse_args()

    if args.batch:
        run_batch(
            squad1_name=args.batch,
            top5_only=not args.all_teams,
            headless=args.headless,
        )
    elif args.t1 and args.t2:
        teams_data = load_teams()
        t1_name = next((t["name"] for t in teams_data if t["id"] == args.t1), args.t1)
        t2_name = next((t["name"] for t in teams_data if t["id"] == args.t2), args.t2)

        driver = launch_browser(headless=args.headless)
        try:
            print("Establishing session...")
            driver.get("https://fbref.com/")
            wait_for_page_ready(driver)
            time.sleep(2)

            t1 = {"id": args.t1, "name": t1_name}
            t2 = {"id": args.t2, "name": t2_name}
            from datetime import datetime
            import json
            import os
            
            result = query_combo(driver, t1, t2)
            if result:
                # Reformat a bit for the single combo endpoint so it has team1
                combo_result = {
                    "team1": t1,
                    "team2": t2,
                    "query_url": result["query_url"],
                    "scraped_at": datetime.now().isoformat(),
                    "player_count": result["player_count"],
                    "players": result["players"]
                }
                
                os.makedirs(COMBOS_DIR, exist_ok=True)
                slug1 = slugify(t1["name"])
                slug2 = slugify(t2["name"])
                filepath = os.path.join(COMBOS_DIR, f"{slug1}__{slug2}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(combo_result, f, indent=2, ensure_ascii=False)
                print(f"  Saved to {filepath}")
                print(f"\nFound {result['player_count']} players.")
            else:
                print("No players found.")
        finally:
            try:
                driver.quit()
            except:
                pass
    else:
        parser.print_help()
