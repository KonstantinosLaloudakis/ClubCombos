"""
Scrape the FBRef multi-club tool form page to extract all available team names and IDs.
Uses undetected-chromedriver to bypass Cloudflare protection.
Saves the result to data/teams.json.
"""

import json
import os
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


BASE_URL = "https://fbref.com/en/friv/players-who-played-for-multiple-clubs-countries.fcgi"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def launch_browser(headless=False):
    """
    Launch undetected-chromedriver.
    Default is non-headless so the user can solve Cloudflare challenges if necessary.
    """
    options = uc.ChromeOptions()
    if headless:
        options.add_argument('--headless')
    
    # Launch browser with explicit version matching the installed Chrome
    driver = uc.Chrome(options=options, version_main=134)
    # Set window size
    driver.set_window_size(1920, 1080)
    return driver


def wait_for_page_ready(driver, timeout=120):
    """
    Wait for the actual FBRef page to load (past Cloudflare).
    The user may need to solve a challenge manually.
    """
    print("\n  Waiting for page to load (solve Cloudflare challenge if prompted)...")
    print("  The browser window should be visible. If you see a CAPTCHA, please solve it.")
    print(f"  Timeout: {timeout}s\n")

    start = time.time()
    while time.time() - start < timeout:
        title = driver.title
        # Cloudflare challenge pages have "Just a moment" as title
        if "just a moment" not in title.lower() and "cloudflare" not in title.lower():
            print(f"  ✓ Page loaded! Title: {title}")
            return True
        elapsed = int(time.time() - start)
        if elapsed % 5 == 0 and elapsed > 0:
            print(f"  Still waiting... ({elapsed}s)")
        time.sleep(1)

    print(f"  ✗ Timed out after {timeout}s")
    return False


def scrape_teams(headless=False):
    """Scrape the form page and extract all team options from the dropdowns."""
    driver = launch_browser(headless=headless)
    
    try:
        print(f"Opening: {BASE_URL}")
        driver.get(BASE_URL)

        if not wait_for_page_ready(driver):
            print("Failed to get past Cloudflare. Try running again.")
            return []

        # Wait a bit for dynamic content
        time.sleep(2)

        # Wait for select elements
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "t1"))
            )
            print("  Form selects found!")
        except Exception:
            print("  Warning: Could not find team selects. Page may not have loaded correctly.")

        html = driver.page_source
    finally:
        driver.quit()

    soup = BeautifulSoup(html, "lxml")

    # Extract teams from all select dropdowns
    teams = {}
    for select_name in ["t1", "t2", "t3", "t4"]:
        select_el = soup.find("select", {"name": select_name})
        if select_el:
            count = 0
            for option in select_el.find_all("option"):
                value = option.get("value", "")
                text = option.get_text(strip=True)
                if value and value != "--" and text:
                    teams[value] = text
                    count += 1
            print(f"  Select '{select_name}': {count} team options")

    if not teams:
        # Debug save
        debug_path = os.path.join(DATA_DIR, "debug_form_page.html")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n  No teams found! HTML saved to {debug_path}")
        return []

    # Sort by name and save
    team_list = [
        {"id": tid, "name": name}
        for tid, name in sorted(teams.items(), key=lambda x: x[1])
    ]

    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = os.path.join(DATA_DIR, "teams.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(team_list, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(team_list)} teams to {output_path}")
    print(f"\nFirst 10 teams:")
    for team in team_list[:10]:
        print(f"  {team['id']}: {team['name']}")

    return team_list


def load_teams():
    """Load the teams list from data/teams.json."""
    teams_path = os.path.join(DATA_DIR, "teams.json")
    if not os.path.exists(teams_path):
        raise FileNotFoundError(
            f"Teams file not found at {teams_path}. "
            "Run 'python main.py teams' first."
        )
    with open(teams_path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_team(teams, search_term):
    """Search for a team by partial name match (case-insensitive)."""
    search_lower = search_term.lower()
    return [t for t in teams if search_lower in t["name"].lower()]


if __name__ == "__main__":
    teams = scrape_teams()

    if teams:
        print("\n--- Searching for Olympiacos ---")
        for t in find_team(teams, "Olympiacos"):
            print(f"  {t['id']}: {t['name']}")

        print("\n--- Searching for Panathinaikos ---")
        for t in find_team(teams, "Panathinaikos"):
            print(f"  {t['id']}: {t['name']}")
