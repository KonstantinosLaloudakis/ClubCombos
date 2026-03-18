"""
Reads the JSON combo data and compiles it into a compact JavaScript file.
This JS file will be loaded by the trivia game to run locally in the browser
without needing a backend server or database.

Auto-detects all *_top5.json files in data/combos/ as focus teams.
"""

import json
import os
import re

DATA_DIR           = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "combos")
CAREERS_FILE       = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "careers.json")
BADGES_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "badges.json")
NATIONALITIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "nationalities.json")
OUTPUT_FILE        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")

def clean_name(name):
    """Remove country prefixes like 'ENG: ' or 'GRE: '"""
    return re.sub(r'^[A-Z]{3,4}:\s*', '', name)

def extract_pid(player):
    link = player.get("Player_link", "")
    m = re.search(r'/players/([a-z0-9]+)/', link)
    return m.group(1) if m else None

def main():
    # Auto-detect all focus team files (*_top5.json)
    focus_files = sorted(
        f for f in os.listdir(DATA_DIR) if f.endswith("_top5.json")
    )
    if not focus_files:
        print("No *_top5.json files found in data/combos/")
        return

    players_dict = {}   # pid -> name
    team_names   = {}   # tid -> clean name
    matrix       = {}   # focus_tid -> { target_tid -> [pid, ...] }
    focus_ids    = []   # ordered list of focus team ids

    for fname in focus_files:
        with open(os.path.join(DATA_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)

        fid   = data["focus_team"]["id"]
        fname_ = clean_name(data["focus_team"]["name"])
        team_names[fid] = fname_
        matrix[fid]     = {}
        focus_ids.append(fid)

        for combo in data.get("combos", []):
            t2_id = combo["team2_id"]
            team_names[t2_id] = clean_name(combo["team2_name"])

            shared = []
            for p in combo.get("players", []):
                pid = extract_pid(p)
                if pid:
                    # Keep the longest name variant
                    if pid not in players_dict or len(p["Player"]) > len(players_dict[pid]):
                        players_dict[pid] = p["Player"]
                    shared.append(pid)

            if shared:
                matrix[fid][t2_id] = shared

    # Valid target columns: any club that has players for at least 2 focus teams
    all_target_ids = set()
    for fid in focus_ids:
        all_target_ids.update(matrix[fid].keys())

    valid_target_teams = []
    for tid in all_target_ids:
        focus_count = sum(1 for fid in focus_ids if tid in matrix[fid] and matrix[fid][tid])
        if focus_count >= 2:
            valid_target_teams.append({"id": tid, "name": team_names[tid]})

    valid_target_teams.sort(key=lambda x: x["name"])
    valid_tids = {t["id"] for t in valid_target_teams}

    # Build final matrix: only keep valid target columns
    final_matrix = {
        fid: {tid: matrix[fid][tid] for tid in valid_tids if tid in matrix[fid]}
        for fid in focus_ids
    }

    # Load career data
    careers_data = {}
    if os.path.exists(CAREERS_FILE):
        with open(CAREERS_FILE, "r", encoding="utf-8") as f:
            raw_careers = json.load(f)
        for pid, stints in raw_careers.items():
            if pid in players_dict and stints and len(stints) >= 2:
                careers_data[pid] = stints

    # Load badge URLs
    badges_data = {}
    if os.path.exists(BADGES_FILE):
        with open(BADGES_FILE, "r", encoding="utf-8") as f:
            raw_badges = json.load(f)
        badges_data = {k: v for k, v in raw_badges.items() if v}

    # Load nationalities
    nationalities_data = {}
    if os.path.exists(NATIONALITIES_FILE):
        with open(NATIONALITIES_FILE, "r", encoding="utf-8") as f:
            raw_nat = json.load(f)
        nationalities_data = {pid: nat for pid, nat in raw_nat.items()
                              if pid in players_dict and nat}

    trivia_data = {
        "focus_teams": [{"id": fid, "name": team_names[fid]} for fid in focus_ids],
        "valid_target_teams": valid_target_teams,
        "players": players_dict,
        "matrix": final_matrix,
        "careers": careers_data,
        "badges": badges_data,
        "nationalities": nationalities_data
    }

    js_content = f"const TRIVIA_DATA = {json.dumps(trivia_data, separators=(',', ':'))};\n"
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"Successfully generated JS database at {OUTPUT_FILE}")
    print(f"  - {len(focus_ids)} Focus teams: {[team_names[fid] for fid in focus_ids]}")
    print(f"  - {len(players_dict)} Total unique players mapped")
    print(f"  - {len(valid_target_teams)} Valid target teams available for columns")
    print(f"  - {len(careers_data)} Players with career history included")
    four_to_six = sum(1 for s in careers_data.values() if 4 <= len(s) <= 6)
    print(f"  - {four_to_six} of those have 4-6 stints (Career Path puzzle pool)")
    print(f"  - {len(badges_data)} club badges included")
    print(f"  - {len(nationalities_data)} player nationalities included")

if __name__ == "__main__":
    main()
