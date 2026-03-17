"""
Fetch club badge URLs from Wikipedia and store them in data/badges.json.
Uses the Wikipedia REST API v1 summary endpoint to get article thumbnails.

Usage:
    python main.py badges
    python main.py badges --resume
"""

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR     = Path(__file__).parent / "data"
CAREERS_FILE = DATA_DIR / "careers.json"
BADGES_FILE  = DATA_DIR / "badges.json"

THUMB_SIZE = 120  # px (standard Wikimedia thumbnail step)

# FBRef short name → Wikipedia article title (spaces, not underscores)
WIKI_TITLES = {
    'Milan':               'AC Milan',
    'Inter':               'Inter Milan',
    'Monaco':              'AS Monaco FC',
    'Dortmund':            'Borussia Dortmund',
    'Gladbach':            'Borussia Mönchengladbach',
    'Leverkusen':          'Bayer 04 Leverkusen',
    'Manchester Utd':      'Manchester United F.C.',
    'Manchester City':     'Manchester City F.C.',
    'West Brom':           'West Bromwich Albion F.C.',
    'Wolves':              'Wolverhampton Wanderers F.C.',
    'Sheffield Weds':      'Sheffield Wednesday F.C.',
    'Newcastle Utd':       'Newcastle United F.C.',
    'Tottenham':           'Tottenham Hotspur F.C.',
    'Arminia':             'DSC Arminia Bielefeld',
    'Hamburger SV':        'Hamburger SV',
    'Mainz 05':            '1. FSV Mainz 05',
    'Loko Moscow':         'Lokomotiv Moscow',
    'Dep La Coruña':       'Deportivo de La Coruña',
    'St Pauli':            'FC St. Pauli',
    'Paris Saint-Germain': 'Paris Saint-Germain F.C.',
    'Roma':                'AS Roma',
    'Red Star':            'Red Star Belgrade',
    'Dynamo Kyiv':         'FC Dynamo Kyiv',
    'CSKA Moscow':         'CSKA Moscow',
    'Atletico Madrid':     'Atlético Madrid',
    'AEK Athens':          'AEK Athens F.C.',
    'PAOK':                'PAOK FC',
    'Olympiacos':          'Olympiacos F.C.',
    'Panathinaikos':       'Panathinaikos F.C.',
    'Aris':                'Aris Thessaloniki F.C.',
    'OFI Crete':           'OFI Crete F.C.',
    'Shakhtar Donetsk':    'FC Shakhtar Donetsk',
    'Spartak Moscow':      'FC Spartak Moscow',
    'Lyon':                'Olympique Lyonnais',
    'Marseille':           'Olympique de Marseille',
    'Rayo Vallecano':      'Rayo Vallecano',
    'Betis':               'Real Betis',
    'Sociedad':            'Real Sociedad',
    'Celta Vigo':          'Celta de Vigo',
    'Nantes':              'FC Nantes',
    'Lens':                'RC Lens',
    'Strasbourg':          'RC Strasbourg Alsace',
    'Metz':                'FC Metz',
    'Genoa':               'Genoa C.F.C.',
    'Lazio':               'S.S. Lazio',
    'Fiorentina':          'ACF Fiorentina',
    'Napoli':              'SSC Napoli',
    'Torino':              'Torino F.C.',
    'Sampdoria':           'U.C. Sampdoria',
    'Udinese':             'Udinese Calcio',
    'Bologna':             'Bologna F.C. 1909',
    'Verona':              'Hellas Verona F.C.',
    'Cagliari':            'Cagliari Calcio',
    'Parma':               'Parma Calcio 1913',
    'Juventus':            'Juventus F.C.',
    'Anderlecht':          'R.S.C. Anderlecht',
    'Club Brugge':         'Club Brugge KV',
    'Ajax':                'AFC Ajax',
    'PSV':                 'PSV Eindhoven',
    'Feyenoord':           'Feyenoord',
    'Porto':               'FC Porto',
    'Benfica':             'S.L. Benfica',
    'Sporting CP':         'Sporting CP',
    'Braga':               'S.C. Braga',
    'Galatasaray':         'Galatasaray S.K.',
    'Fenerbahçe':          'Fenerbahçe S.K.',
    'Beşiktaş':            'Beşiktaş J.K.',
    'Trabzonspor':         'Trabzonspor',
    'Zenit':               'FC Zenit Saint Petersburg',
    'Lokomotiv':           'Lokomotiv Moscow',
    'Celtic':              'Celtic F.C.',
    'Rangers':             'Rangers F.C.',
    'Dinamo Zagreb':       'GNK Dinamo Zagreb',
    'Hajduk Split':        'HNK Hajduk Split',
    'Barcelona':           'FC Barcelona',
    'Arsenal':             'Arsenal F.C.',
    'Chelsea':             'Chelsea F.C.',
    'Liverpool':           'Liverpool F.C.',
    'Everton':             'Everton F.C.',
    'Leeds United':        'Leeds United A.F.C.',
    'Aston Villa':         'Aston Villa F.C.',
    'Leicester City':      'Leicester City F.C.',
    'West Ham':            'West Ham United F.C.',
    'Fulham':              'Fulham F.C.',
    'Sunderland':          'Sunderland A.F.C.',
    'Ipswich Town':        'Ipswich Town F.C.',
    'Brentford':           'Brentford F.C.',
    'Sevilla':             'Sevilla FC',
    'Valencia':            'Valencia CF',
    'Villarreal':          'Villarreal CF',
    'Deportivo':           'Deportivo de La Coruña',
    'Athletic Club':       'Athletic Club',
    'Atalanta':            'Atalanta B.C.',
    'Schalke 04':          'FC Schalke 04',
    'Stuttgart':           'VfB Stuttgart',
    'Wolfsburg':           'VfL Wolfsburg',
    'Werder Bremen':       'SV Werder Bremen',
    'Augsburg':            'FC Augsburg',
    'Hoffenheim':          'TSG 1899 Hoffenheim',
    'Bochum':              'VfL Bochum',
    'Kaiserslautern':      '1. FC Kaiserslautern',
    'Köln':                '1. FC Köln',
    'Nürnberg':            '1. FC Nürnberg',
    'Düsseldorf':          'Fortuna Düsseldorf',
    'Dresden':             'Dynamo Dresden',
    'Southampton':         'Southampton F.C.',
    'Sunderland':          'Sunderland A.F.C.',
    'West Ham United':     'West Ham United F.C.',
    'Watford':             'Watford F.C.',
    'Swansea City':        'Swansea City A.F.C.',
    'Stoke City':          'Stoke City F.C.',
    'Wigan Athletic':      'Wigan Athletic F.C.',
    'Nottingham Forest':   'Nottingham Forest F.C.',
    'Sheffield United':    'Sheffield United F.C.',
    'Coventry City':       'Coventry City F.C.',
    'Tottenham Hotspur':   'Tottenham Hotspur F.C.',
    'Sao Paulo':           'São Paulo FC',
    'São Paulo':           'São Paulo FC',
    'Corinthians':         'Sport Club Corinthians Paulista',
    'Flamengo':            'Clube de Regatas do Flamengo',
    'Sporting KC':         'Sporting Kansas City',
    'Seattle Sounders':    'Seattle Sounders FC',
    'Sparta Prague':       'AC Sparta Prague',
    'Slavia Prague':       'SK Slavia Prague',
    'Partizan':            'FK Partizan',
    'Red Star Belgrade':   'Red Star Belgrade',
    'Rosenborg':           'Rosenborg BK',
    'Young Boys':          'BSC Young Boys',
    'Grasshopper':         'Grasshopper Club Zürich',
    'Lausanne-Sport':      'FC Lausanne-Sport',
    'Rapid Wien':          'SK Rapid Wien',
    'Sturm Graz':          'SK Sturm Graz',
    'Lille':               'LOSC Lille',
    'Nice':                'OGC Nice',
    'Rennes':              'Stade Rennais FC',
    'Montpellier':         'Montpellier HSC',
    'Toulouse':            'Toulouse FC',
    'Saint-Étienne':       'AS Saint-Étienne',
    'Sochaux':             'FC Sochaux-Montbéliard',
    'Troyes':              'ES Troyes AC',
    'Shakhtar Donetsk':    'FC Shakhtar Donetsk',
    'Spartak Moscow':      'FC Spartak Moscow',
    'Zenit':               'FC Zenit Saint Petersburg',
    'Krasnodar':           'FC Krasnodar',
    'Rostov':              'FC Rostov',
    'Twente':              'FC Twente',
    'Utrecht':             'FC Utrecht',
    'Groningen':           'FC Groningen',
    'Vitesse':             'Vitesse',
    'Heerenveen':          'SC Heerenveen',
    'Brøndby':             'Brøndby IF',
    'Nordsjælland':        'FC Nordsjælland',
    'Odense':              'Odense BK',
    'Malmö':               'Malmö FF',
    'AIK Stockholm':       'AIK Fotboll',
    'Göteborg':            'IFK Göteborg',
    'Djurgården':          'Djurgårdens IF',
    'Elfsborg':            'IF Elfsborg',
    'Eibar':               'SD Eibar',
    'Levante':             'Levante UD',
    'Granada':             'Granada CF',
    'Osasuna':             'CA Osasuna',
    'Deportivo La Coruña': 'Deportivo de La Coruña',
    'Sporting Gijón':      'Real Sporting de Gijón',
    'Málaga':              'Málaga CF',
    'Valladolid':          'Real Valladolid',
    'Lugo':                'CD Lugo',
    'Almería':             'UD Almería',
    'Cádiz':               'Cádiz CF',
    'Huesca':              'SD Huesca',
    'Elche':               'Elche CF',
    'San Lorenzo':         'San Lorenzo de Almagro',
    'Independiente':       'Club Atlético Independiente',
    'Racing Club':         'Racing Club de Avellaneda',
    'River Plate':         'Club Atlético River Plate',
    'Boca Juniors':        'Club Atlético Boca Juniors',
    'Estudiantes':         'Estudiantes de La Plata',
}


def is_crest(url: str) -> bool:
    """Return True only if the URL looks like a badge/crest, not a photo."""
    lower = url.lower()
    # Hard reject JPEG — photos of cities, stadiums, players are always JPEG
    if re.search(r'\.jpe?g(/|$)', lower):
        return False
    non_crest = {'stadium', 'ground', 'arena', 'portrait', 'headshot',
                 'collage', 'panorama', 'skyline', 'aerial', 'cathedral',
                 'rathaus', 'map_', '_map', 'flag_', '_flag', 'landscape'}
    if any(k in lower for k in non_crest):
        return False
    # SVG (rendered as .svg.png or plain .svg) → always a crest
    if '.svg' in lower:
        return True
    # PNG with crest-like keywords
    crest_kw = {'crest', 'badge', 'logo', 'emblem', 'shield', 'seal',
                '_fc', 'fc_', '_sc', 'sc_', '_ac', 'ac_', '_cf', 'cf_',
                'sport', 'calcio', 'futbol', 'football', 'united', 'city',
                'rovers', 'athletic', 'atleti', 'dynamo', 'spartak'}
    if any(k in lower for k in crest_kw):
        return True
    return False


def resize_thumb(url: str, size: int) -> str:
    """Replace the px size in a Wikimedia thumbnail URL."""
    return re.sub(r'/\d+px-', f'/{size}px-', url)


def _wiki_action(params: dict) -> dict:
    """Call the Wikipedia Action API."""
    params['format'] = 'json'
    url = 'https://en.wikipedia.org/w/api.php?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'ClubCombos/1.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def fetch_page_thumbnail(title: str) -> str | None:
    """Try Action API piprop=thumbnail for a Wikipedia page title."""
    try:
        data = _wiki_action({
            'action': 'query',
            'titles': title,
            'prop': 'pageimages',
            'piprop': 'thumbnail',
            'pithumbsize': THUMB_SIZE,
        })
        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            if page.get('ns', 0) != 0:
                continue
            src = page.get('thumbnail', {}).get('source', '')
            if src and is_crest(src):
                return resize_thumb(src, THUMB_SIZE)
    except Exception:
        pass
    return None


# SVG files to always skip (flags, wiki logos, generic icons)
_SKIP_SVG = re.compile(
    r'(flag.of|wiki.?media|wiki.?quote|wiki.?news|wiki.?source|wiki.?books|wiki.?voyage|'
    r'commons.logo|wikipedia.logo|red.dot|\.icon|stub|portal|pictogram|'
    r'map.of|coat.of.arms|disputed|territory|nuvola|ambox|question|'
    r'crystal.clear|gnome|oxygen|tango|autoroute|autouroute|autostrada|'
    r'district|region|province|county|municipality|road_sign)',
    re.IGNORECASE
)


def fetch_page_svg_image(title: str, club_name: str = '') -> str | None:
    """Scan the article's image list for an SVG crest, then fetch its URL."""
    # Build words from club name for filename matching
    name_words = [w.lower() for w in re.split(r'\W+', club_name) if len(w) > 2
                  and w.lower() not in {'the', 'and', 'for', 'football', 'club', 'sport'}]

    try:
        data = _wiki_action({
            'action': 'query',
            'titles': title,
            'prop': 'images',
            'imlimit': 50,
        })
        pages = data.get('query', {}).get('pages', {})
        svg_files = []
        for page in pages.values():
            for img in page.get('images', []):
                fn = img.get('title', '')
                if not fn.lower().endswith('.svg'):
                    continue
                if _SKIP_SVG.search(fn):
                    continue
                svg_files.append(fn)

        if not svg_files:
            return None

        # Score SVGs: prefer files containing club name words > crest keywords > anything else
        CREST_KW = re.compile(
            r'(crest|badge|emblem|shield)',
            re.IGNORECASE
        )

        def score(fn: str):
            lower = fn.lower()
            name_match = any(w in lower for w in name_words) if name_words else False
            crest_match = bool(CREST_KW.search(fn))
            # Lower score = better
            if name_match and crest_match:
                return (0, len(fn))
            if name_match:
                return (1, len(fn))
            if crest_match:
                return (2, len(fn))
            return (3, len(fn))

        svg_files.sort(key=score)
        # Only accept files with score < 3 (must match club name or crest keyword)
        if score(svg_files[0])[0] >= 3:
            return None

        best = svg_files[0]

        # Get the image URL via imageinfo
        time.sleep(0.3)
        info = _wiki_action({
            'action': 'query',
            'titles': best,
            'prop': 'imageinfo',
            'iiprop': 'url',
            'iiurlwidth': THUMB_SIZE,
        })
        for page in info.get('query', {}).get('pages', {}).values():
            ii = page.get('imageinfo', [{}])[0]
            src = ii.get('thumburl', '') or ii.get('url', '')
            if src and is_crest(src):
                return src
    except Exception:
        pass
    return None


# FBRef short name → TheSportsDB search term (only where name differs)
SPORTSDB_OVERRIDES = {
    'Milan':               'AC Milan',
    'Inter':               'Inter Milan',
    'Monaco':              'AS Monaco',
    'Dortmund':            'Borussia Dortmund',
    'Gladbach':            'Borussia Monchengladbach',
    'Leverkusen':          'Bayer Leverkusen',
    'Manchester Utd':      'Manchester United',
    'West Brom':           'West Bromwich Albion',
    'Wolves':              'Wolverhampton Wanderers',
    'Sheffield Weds':      'Sheffield Wednesday',
    'Newcastle Utd':       'Newcastle United',
    'Arminia':             'Arminia Bielefeld',
    'Hamburger SV':        'Hamburger SV',
    'Mainz 05':            'Mainz 05',
    'Loko Moscow':         'Lokomotiv Moscow',
    'Dep La Coruña':       'Deportivo La Coruna',
    'St Pauli':            'FC St Pauli',
    'Paris Saint-Germain': 'Paris Saint-Germain',
    'Roma':                'AS Roma',
    'Red Star':            'Red Star Belgrade',
    'Dynamo Kyiv':         'Dynamo Kyiv',
    'CSKA Moscow':         'CSKA Moscow',
    'Atletico Madrid':     'Atletico Madrid',
    'AEK Athens':          'AEK Athens',
    'Olympiacos':          'Olympiakos',
    'Panathinaikos':       'Panathinaikos',
    'Aris':                'Aris Thessaloniki',
    'Shakhtar Donetsk':    'Shakhtar Donetsk',
    'Spartak Moscow':      'Spartak Moscow',
    'Lyon':                'Olympique Lyonnais',
    'Marseille':           'Olympique de Marseille',
    'Betis':               'Real Betis',
    'Sociedad':            'Real Sociedad',
    'Celta Vigo':          'Celta Vigo',
    'Schalke 04':          'Schalke 04',
    'Stuttgart':           'VfB Stuttgart',
    'Wolfsburg':           'VfL Wolfsburg',
    'Werder Bremen':       'Werder Bremen',
    'Augsburg':            'FC Augsburg',
    'Hoffenheim':          'Hoffenheim',
    'Bochum':              'VfL Bochum',
    'Köln':                'FC Koln',
    'Nürnberg':            'Nurnberg',
    'Düsseldorf':          'Fortuna Dusseldorf',
    'Athletic Club':       'Athletic Club Bilbao',
    'AIK Stockholm':       'AIK',
    'Malmö':               'Malmo FF',
    'Göteborg':            'IFK Goteborg',
    'Brøndby':             'Brondby',
    'Lille':               'Lille OSC',
    'Nice':                'OGC Nice',
    'Rennes':              'Stade Rennais',
    'Montpellier':         'Montpellier HSC',
    'Toulouse':            'Toulouse FC',
    'Saint-Étienne':       'Saint-Etienne',
    'Sochaux':             'Sochaux',
    'Troyes':              'Troyes',
    'Strasbourg':          'Strasbourg',
    'Sporting CP':         'Sporting CP',
    'Braga':               'Sporting Braga',
    'Galatasaray':         'Galatasaray',
    'Fenerbahçe':          'Fenerbahce',
    'Beşiktaş':            'Besiktas',
    'Trabzonspor':         'Trabzonspor',
    'Zenit':               'Zenit St Petersburg',
    'Dinamo Zagreb':       'Dinamo Zagreb',
    'Hajduk Split':        'Hajduk Split',
    'Barcelona':           'Barcelona',
    'Arg Juniors':         'Argentinos Juniors',
    'Atl Juniors':         'Atletico Junior',
    'Sao Paulo':           'Sao Paulo',
    'São Paulo':           'Sao Paulo',
    'América Cali':        'America de Cali',
    'Am\u00e9rica Cali':   'America de Cali',
    'Botafogo (RJ)':       'Botafogo',
    'Vancouver W\'caps':   'Vancouver Whitecaps',
    'NE Revolution':       'New England Revolution',
    'Sporting KC':         'Sporting Kansas City',
    'Melb City':           'Melbourne City',
    'Malmö':               'Malmo FF',
}


def fetch_sportsdb_badge(club_name: str) -> str | None:
    """Query TheSportsDB for a club badge (strBadge field, free tier)."""
    search_name = SPORTSDB_OVERRIDES.get(club_name, club_name)
    encoded = urllib.parse.quote(search_name)
    url = f'https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t={encoded}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ClubCombos/1.0'})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        teams = data.get('teams') or []
        if teams:
            badge = teams[0].get('strBadge') or teams[0].get('strLogo')
            if badge:
                return badge
    except Exception:
        pass
    return None


def fetch_badge_url(club_name: str) -> str | None:
    """Fetch badge URL for a club, trying Wikipedia then TheSportsDB."""
    candidates = []

    if club_name in WIKI_TITLES:
        candidates.append(WIKI_TITLES[club_name])

    candidates.append(club_name)
    if not re.search(r'\bFC\b|\bF\.C\b', club_name):
        candidates.append(f'{club_name} FC')

    seen = set()
    for title in candidates:
        if title in seen:
            continue
        seen.add(title)

        # Strategy 1: Wikipedia pageimages thumbnail
        result = fetch_page_thumbnail(title)
        if result:
            return result
        time.sleep(0.2)

        # Strategy 2: Wikipedia page image list (SVG crests)
        result = fetch_page_svg_image(title, club_name)
        if result:
            return result
        time.sleep(0.2)

    # Strategy 3: TheSportsDB (strBadge, free tier)
    result = fetch_sportsdb_badge(club_name)
    if result:
        return result
    time.sleep(0.2)

    return None


def get_puzzle_clubs() -> set[str]:
    """Return unique club names that appear in 4+ stint career entries."""
    with open(CAREERS_FILE, encoding='utf-8') as f:
        careers = json.load(f)

    clubs: set[str] = set()
    for pid, stints in careers.items():
        if pid == '_meta' or not isinstance(stints, list) or len(stints) < 4:
            continue
        for stint in stints:
            clubs.add(stint['club'])
    return clubs


def run_fetch_badges(resume: bool = False) -> None:
    clubs = get_puzzle_clubs()
    print(f'Found {len(clubs)} unique clubs in 4+ stint careers.')

    existing: dict = {}
    if resume and BADGES_FILE.exists():
        with open(BADGES_FILE, encoding='utf-8') as f:
            existing = json.load(f)
        print(f'Resuming -- {len(existing)} clubs already cached.')

    skip_pattern = re.compile(r'\s(B|II|Reserves?|U\d{2})$')
    to_fetch = sorted(c for c in clubs
                      if c not in existing and not skip_pattern.search(c))

    print(f'Fetching badges for {len(to_fetch)} clubs...\n')

    results = dict(existing)
    found = sum(1 for v in existing.values() if v)
    failed = sum(1 for v in existing.values() if not v)

    for i, club in enumerate(to_fetch, 1):
        url = fetch_badge_url(club)
        results[club] = url
        status = 'ok' if url else '--'
        safe_club = club.encode('ascii', 'replace').decode()
        print(f'  [{i:>3}/{len(to_fetch)}] {status} {safe_club}')
        if url:
            found += 1
        else:
            failed += 1

        if i % 20 == 0 or i == len(to_fetch):
            with open(BADGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)  # polite rate limiting

    print(f'\nDone. {found} badges found, {failed} not found.')
    print(f'Saved to {BADGES_FILE}')
