# 🇬🇷 Club Combos — The Greek Giants Grid

An **Immaculate Grid**-style trivia game for Greek football fans. Name a player who played for **both** intersecting clubs — one Greek giant (Olympiacos FC or Panathinaikos FC) and one Top 5 European league team.

<p align="center">
  <img src="docs/preview.png" alt="Club Combos Preview" width="700">
</p>

## 🎮 Play Now

👉 **[Play on GitHub Pages](https://YOUR_USERNAME.github.io/ClubCombos/)**

## Features

- **Dynamic Grid Sizes** — Choose between a 2×3 or 2×4 grid
- **Player Headshots** — Wikipedia images fetched live on correct guesses
- **Smart Tooltips** — Hover over solved cells to see all other valid answers
- **Full Answer Reveal** — On Game Over, every cell shows all valid players
- **Toast Notifications** — Instant visual feedback for correct and incorrect guesses
- **Dark Premium UI** — Sleek glassmorphism design with smooth micro-animations

## Project Structure

```
ClubCombos/
├── trivia/                 # 🎮 The game (static site hosted on GitHub Pages)
│   ├── index.html          # Main HTML
│   ├── style.css           # All styling
│   ├── app.js              # Game engine
│   ├── data.js             # Player/combo dataset (generated)
│   └── prepare_data.py     # Script to regenerate data.js
│
├── data/                   # Raw scraped data
│   ├── teams.json          # All FBRef team IDs
│   └── combos/             # Per-team combo JSON files
│
├── scrape_teams.py         # Scrape team IDs from FBRef
├── scrape_combos.py        # Scrape player combos from FBRef
├── main.py                 # CLI entry point for scraping
└── requirements.txt        # Python dependencies
```

## Data Pipeline

The game data is generated through a multi-step scraping pipeline:

1. **`scrape_teams.py`** — Scrapes all team IDs from FBRef's squad finder
2. **`scrape_combos.py`** — Queries FBRef for players shared between two clubs
3. **`trivia/prepare_data.py`** — Compiles scraped JSON into `data.js` for the game

To regenerate the game data:

```bash
pip install -r requirements.txt
python main.py                        # Scrape combos
cd trivia && python prepare_data.py   # Compile into data.js
```

## Hosting

The game is a purely static site (HTML + CSS + JS). It is hosted via **GitHub Pages** from the `trivia/` directory.

To deploy your own:

1. Push this repo to GitHub
2. Go to **Settings → Pages**
3. Set Source to **GitHub Actions** (uses the included workflow)
4. The site will be live at `https://<username>.github.io/ClubCombos/`

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Vanilla HTML, CSS, JavaScript |
| Fonts | Google Fonts (Inter, Outfit) |
| Images | Wikipedia API (page thumbnails) |
| Data | Python + BeautifulSoup (FBRef scraping) |
| Hosting | GitHub Pages |

## License

This project is for educational and personal use. Player data is sourced from [FBRef](https://fbref.com).
