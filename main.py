"""
ClubCombos - Find football players who played for multiple clubs.
Uses FBRef's multi-club tool to query player combinations.

Usage:
    python main.py teams              - Scrape all available teams from FBRef
    python main.py search "term"      - Search for a team by name
    python main.py combo ID1 ID2      - Query a single team combination
    python main.py batch "TeamName"   - Run a team against all Top 5 League teams
    python main.py batch_all "TeamName" - Run a team against ALL available teams
"""

import sys

from scrape_teams import scrape_teams, find_team, load_teams
from scrape_combos import (
    run_batch, query_combo,
    launch_browser, wait_for_page_ready, COMBOS_DIR
)


def cmd_teams():
    """Scrape and save all available teams."""
    teams = scrape_teams()
    print(f"\nDone! {len(teams)} teams saved.")


def cmd_search(term):
    """Search for a team by name."""
    try:
        teams = load_teams()
    except FileNotFoundError:
        print("Teams file not found. Run 'python main.py teams' first.")
        return
    matches = find_team(teams, term)
    if matches:
        print(f"Found {len(matches)} matches for '{term}':")
        for t in matches:
            print(f"  {t['id']}: {t['name']}")
    else:
        print(f"No teams found matching '{term}'.")


def cmd_combo(t1_id, t2_id):
    """Query a single team combination."""
    import time
    from scrape_combos import slugify
    import json
    import os
    
    try:
        teams = load_teams()
    except FileNotFoundError:
        teams = []

    t1_name = next((t["name"] for t in teams if t["id"] == t1_id), t1_id)
    t2_name = next((t["name"] for t in teams if t["id"] == t2_id), t2_id)

    driver = launch_browser()
    try:
        print("Establishing session (solve Cloudflare if prompted)...")
        driver.get("https://fbref.com/")
        wait_for_page_ready(driver)
        time.sleep(2)

        t1 = {"id": t1_id, "name": t1_name}
        t2 = {"id": t2_id, "name": t2_name}
        result = query_combo(driver, t1, t2)
        
        if result:
            from datetime import datetime
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
            print(f"\nSaved {result['player_count']} players to {filepath}")
        else:
            print("\nNo players found.")
            
    finally:
        try:
            driver.quit()
        except:
            pass


def cmd_batch(team_name, all_teams=False):
    """Run batch for a specific team."""
    run_batch(squad1_name=team_name, top5_only=not all_teams)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == "teams":
        cmd_teams()
    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python main.py search <term>")
            return
        cmd_search(sys.argv[2])
    elif command == "combo":
        if len(sys.argv) < 4:
            print("Usage: python main.py combo <team1_id> <team2_id>")
            return
        cmd_combo(sys.argv[2], sys.argv[3])
    elif command == "batch":
        if len(sys.argv) < 3:
            print("Usage: python main.py batch <team_name>")
            return
        cmd_batch(sys.argv[2], all_teams=False)
    elif command == "batch_all":
        if len(sys.argv) < 3:
            print("Usage: python main.py batch_all <team_name>")
            return
        cmd_batch(sys.argv[2], all_teams=True)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
