"""
ClubCombos - Find football players who played for multiple clubs.
Uses FBRef's multi-club tool to query player combinations.

Usage:
    python main.py teams                     - Scrape all available teams from FBRef
    python main.py search "term"             - Search for a team by name
    python main.py combo ID1 ID2            - Query a single team combination
    python main.py batch "TeamName"          - Run a team against all Top 5 League teams
    python main.py batch_all "TeamName"      - Run a team against ALL available teams
    python main.py careers                   - Scrape career histories for all players
    python main.py careers --resume          - Resume a previous career scrape
    python main.py careers --goals           - Re-scrape only players missing goal data
    python main.py badges                    - Fetch club badge images
    python main.py badges --resume           - Resume a previous badge fetch
    python main.py build                     - careers + badges + prepare data (incremental)
    python main.py build --full              - batch scrape + careers + badges + prepare data
"""

import sys


def cmd_teams():
    """Scrape and save all available teams."""
    from scrape_teams import scrape_teams
    teams = scrape_teams()
    print(f"\nDone! {len(teams)} teams saved.")


def cmd_search(term):
    """Search for a team by name."""
    from scrape_teams import find_team, load_teams
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
    import time, json, os
    from scrape_teams import load_teams
    from scrape_combos import slugify, query_combo, launch_browser, wait_for_page_ready, COMBOS_DIR

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
    from scrape_combos import run_batch
    run_batch(squad1_name=team_name, top5_only=not all_teams)


def cmd_careers(resume=False, goals_only=False):
    """Scrape career histories for all players in the combo data."""
    from scrape_careers import run_career_scrape
    run_career_scrape(resume=resume, goals_only=goals_only)


def cmd_badges(resume=False):
    """Fetch club badge URLs from Wikipedia and store in data/badges.json."""
    from fetch_badges import run_fetch_badges
    run_fetch_badges(resume=resume)


def cmd_prepare():
    """Regenerate trivia/data.js from all data sources."""
    import importlib.util, os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trivia", "prepare_data.py")
    spec = importlib.util.spec_from_file_location("prepare_data", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.main()


def cmd_build(full=False):
    """
    Chain all data pipeline steps into one command.

    --full  also re-scrapes combos for Olympiacos and Panathinaikos first.
    """
    FOCUS_TEAMS = ["Olympiacos", "Panathinaikos"]

    if full:
        print("=" * 60)
        print("STEP 1/4 — Scraping combos for focus teams")
        print("=" * 60)
        for team in FOCUS_TEAMS:
            print(f"\n→ Batch scraping {team}...")
            cmd_batch(team, all_teams=False)
    else:
        print("Skipping combo scrape (use --full to include it)\n")

    step = 2 if full else 1
    total = 4 if full else 3

    print("=" * 60)
    print(f"STEP {step}/{total} — Scraping careers (resume mode)")
    print("=" * 60)
    cmd_careers(resume=True)

    print("\n" + "=" * 60)
    print(f"STEP {step+1}/{total} — Fetching club badges (resume mode)")
    print("=" * 60)
    cmd_badges(resume=True)

    print("\n" + "=" * 60)
    print(f"STEP {step+2}/{total} — Regenerating data.js")
    print("=" * 60)
    cmd_prepare()

    print("\nBuild complete.")


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
    elif command == "careers":
        cmd_careers(resume="--resume" in sys.argv, goals_only="--goals" in sys.argv)
    elif command == "badges":
        cmd_badges(resume="--resume" in sys.argv)
    elif command == "build":
        cmd_build(full="--full" in sys.argv)
    elif command == "prepare":
        cmd_prepare()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
