"""
Reads the JSON combo data and compiles it into a compact JavaScript file.
This JS file will be loaded by the trivia game to run locally in the browser
without needing a backend server or database.
"""

import json
import os
import re

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "combos")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")

def clean_name(name):
    """Remove country prefixes like 'ENG: ' or 'GRE: '"""
    return re.sub(r'^[A-Z]{3,4}:\s*', '', name)

def main():
    # Load the two result files
    oly_path = os.path.join(DATA_DIR, "olympiacos_fc_top5.json")
    pao_path = os.path.join(DATA_DIR, "panathinaikos_fc_top5.json")
    
    with open(oly_path, "r", encoding="utf-8") as f:
        oly_data = json.load(f)
        
    with open(pao_path, "r", encoding="utf-8") as f:
        pao_data = json.load(f)

    # Dictionaries to hold our parsed data
    players_dict = {}  # id -> name
    team_names = {}    # id -> clean_name
    
    # We will build a matrix: team1_id -> { team2_id: [player_id, ...] }
    matrix = {}
    
    oly_id = oly_data["focus_team"]["id"]
    pao_id = pao_data["focus_team"]["id"]
    
    team_names[oly_id] = clean_name(oly_data["focus_team"]["name"])
    team_names[pao_id] = clean_name(pao_data["focus_team"]["name"])
    
    matrix[oly_id] = {}
    matrix[pao_id] = {}
    
    # Process Olympiacos combos
    for combo in oly_data.get("combos", []):
        t2_id = combo["team2_id"]
        team_names[t2_id] = clean_name(combo["team2_name"])
        
        shared_players = []
        for p in combo.get("players", []):
            # Extract a unique player ID from their FBRef link
            # e.g., "https://fbref.com/en/players/895ff3ca/Joel-Campbell" -> "895ff3ca"
            link = p.get("Player_link", "")
            pid_match = re.search(r'/players/([a-z0-9]+)/', link)
            if pid_match:
                pid = pid_match.group(1)
                players_dict[pid] = p["Player"]
                shared_players.append(pid)
        
        if shared_players:
            matrix[oly_id][t2_id] = shared_players
            
    # Process Panathinaikos combos
    for combo in pao_data.get("combos", []):
        t2_id = combo["team2_id"]
        team_names[t2_id] = clean_name(combo["team2_name"])
        
        shared_players = []
        for p in combo.get("players", []):
            link = p.get("Player_link", "")
            pid_match = re.search(r'/players/([a-z0-9]+)/', link)
            if pid_match:
                pid = pid_match.group(1)
                # Keep the longest/best formatted name if there's a variation
                if pid not in players_dict or len(p["Player"]) > len(players_dict[pid]):
                    players_dict[pid] = p["Player"]
                shared_players.append(pid)
        
        if shared_players:
            matrix[pao_id][t2_id] = shared_players

    # Find valid columns: Target teams that have >= 1 player shared with BOTH focus clubs
    valid_target_teams = []
    
    oly_targets = set(matrix[oly_id].keys())
    pao_targets = set(matrix[pao_id].keys())
    
    common_targets = oly_targets.intersection(pao_targets)
    for tid in common_targets:
        # Check that both actual have players (should be yes based on logic above)
        if len(matrix[oly_id][tid]) > 0 and len(matrix[pao_id][tid]) > 0:
            valid_target_teams.append({
                "id": tid,
                "name": team_names[tid]
            })
            
    # Sort valid targets alphabetically
    valid_target_teams.sort(key=lambda x: x["name"])
            
    # To reduce file size, we only need to output the players that are actually in the matrix.
    # Furthermore, we only need to output matrix entries for the valid targets.
    
    final_matrix = {
        oly_id: {tid: matrix[oly_id][tid] for tid in common_targets},
        pao_id: {tid: matrix[pao_id][tid] for tid in common_targets}
    }
    
    # Optional: also include players from Greek mutual combinations if Oly and Pao share players
    # Actually, we scraped that manually earlier. Let's merge it if it exists.
    oly_pao_file = os.path.join(DATA_DIR, "olympiacos_fc__panathinaikos_fc.json")
    if os.path.exists(oly_pao_file):
        with open(oly_pao_file, "r", encoding="utf-8") as f:
            mutual = json.load(f)
            shared = []
            for p in mutual.get("players", []):
                link = p.get("Player_link", "") or p.get("col_0_link", "") or ""
                name = p.get("Player", "") or p.get("col_0", "") or "Unknown"
                
                pid_match = re.search(r'/players/([a-z0-9]+)/', link)
                if pid_match:
                    pid = pid_match.group(1)
                    players_dict[pid] = name
                    shared.append(pid)
            if shared:
                # Add cross-compatibility
                final_matrix[oly_id][pao_id] = shared
                final_matrix[pao_id][oly_id] = shared

    # Compile the final object
    trivia_data = {
        "focus_teams": [
            {"id": oly_id, "name": team_names[oly_id]},
            {"id": pao_id, "name": team_names[pao_id]}
        ],
        "valid_target_teams": valid_target_teams,
        "players": players_dict,
        "matrix": final_matrix
    }

    # Write as a JavaScript variable assignment
    js_content = f"const TRIVIA_DATA = {json.dumps(trivia_data, separators=(',', ':'))};\n"
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js_content)
        
    print(f"Successfully generated JS database at {OUTPUT_FILE}")
    print(f"  - {len(players_dict)} Total unique players mapped")
    print(f"  - {len(valid_target_teams)} Valid Top 5 teams available for columns")

if __name__ == "__main__":
    main()
