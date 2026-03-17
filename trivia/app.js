/**
 * Club Combos Trivia Game Engine
 * Loads TRIVIA_DATA from data.js
 */

// State
let state = {
    gridSize: 3, // columns (3 or 4)
    lives: 6,
    score: 0,
    activeCellId: null, // format: "focusId-targetId"
    columns: [], // Selected target teams
    focusTeams: [], // The Greek teams
    cells: {}, // State of each cell: 'empty', 'solved', 'failed'
    usedPlayers: new Set(), // Prevent using the same player twice
    isDailyChallenge: false
};

// DOM Elements
const views = {
    start: document.getElementById('start-screen'),
    game: document.getElementById('game-screen'),
    end: document.getElementById('game-over-screen'),
    commonClub: document.getElementById('common-club-screen'),
    careerPath: document.getElementById('career-path-screen')
};

const dom = {
    livesContainer: document.getElementById('lives-container'),
    score: document.getElementById('current-score'),
    maxScore: document.getElementById('max-score'),
    gridHeader: document.getElementById('grid-header'),
    gridBody: document.getElementById('grid-body'),
    
    // Search Modal
    searchModal: document.getElementById('search-modal'),
    searchInput: document.getElementById('player-search-input'),
    searchResults: document.getElementById('search-results'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    btnSurrenderCell: document.getElementById('btn-surrender-cell'),
    
    // End screen
    endTitle: document.getElementById('end-title'),
    endMsg: document.getElementById('end-message')
};

// --- Daily Challenge ---

// Seeded PRNG (mulberry32) — used so everyone gets the same daily grid.
function mulberry32(seed) {
    return function() {
        seed |= 0; seed = seed + 0x6D2B79F5 | 0;
        let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
        t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
}

function getDailyKey() {
    const now = new Date();
    return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`;
}

function formatDailyDate() {
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const now = new Date();
    return `${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
}

function startDailyChallenge() {
    const key = getDailyKey();
    const stored = localStorage.getItem(`clubcombos_daily_${key}`);

    if (stored) {
        showAlreadyPlayedResult(JSON.parse(stored));
        return;
    }

    state.isDailyChallenge = true;
    state.gridSize = 3;

    const totalCells = TRIVIA_DATA.focus_teams.length * 3;
    state.lives = totalCells;
    state.score = 0;
    state.cells = {};
    state.usedPlayers.clear();
    state.focusTeams = TRIVIA_DATA.focus_teams;

    // Seeded Fisher-Yates — same shuffle every day
    const rng = mulberry32(parseInt(key));
    const available = [...TRIVIA_DATA.valid_target_teams];
    for (let i = available.length - 1; i > 0; i--) {
        const j = Math.floor(rng() * (i + 1));
        [available[i], available[j]] = [available[j], available[i]];
    }
    state.columns = available.slice(0, 3);

    dom.maxScore.textContent = totalCells;
    document.getElementById('btn-give-up').style.display = 'block';
    renderLives();
    dom.score.textContent = state.score;
    buildGrid();
    showView('game');
}

function showAlreadyPlayedResult(result) {
    dom.endTitle.textContent = result.score === result.total ? 'Immaculate!' :
                               result.score === 0 ? 'Better luck tomorrow!' : 'Daily Complete!';
    dom.endMsg.textContent = `Today's score: ${result.score}/${result.total}`;
    document.getElementById('daily-emoji-grid').textContent = result.emojiGrid;
    document.getElementById('share-section').classList.remove('hidden');
    showView('end');
}

function generateEmojiGrid() {
    return state.focusTeams.map(focusTeam =>
        state.columns.map(col => {
            const cellId = `${focusTeam.id}-${col.id}`;
            return state.cells[cellId] === 'solved' ? '🟩' : '🟥';
        }).join('')
    ).join('\n');
}

function saveDailyResult() {
    const key = getDailyKey();
    const totalCells = state.focusTeams.length * state.gridSize;
    localStorage.setItem(`clubcombos_daily_${key}`, JSON.stringify({
        score: state.score,
        total: totalCells,
        emojiGrid: generateEmojiGrid(),
        date: key
    }));
}

async function handleShare() {
    const key = getDailyKey();
    const stored = localStorage.getItem(`clubcombos_daily_${key}`);
    if (!stored) return;

    const result = JSON.parse(stored);
    const shareText = `Club Combos – ${formatDailyDate()}\n${result.emojiGrid}\nScore: ${result.score}/${result.total}\nhttps://konstantinoslaloudakis.github.io/ClubCombos/`;

    if (navigator.share) {
        try {
            await navigator.share({ text: shareText });
            return;
        } catch(e) { /* user cancelled or API unavailable */ }
    }

    try {
        await navigator.clipboard.writeText(shareText);
        showToast('Result copied to clipboard!', 'success');
    } catch(e) {
        showToast('Could not copy to clipboard.', 'error');
    }
}

function updateDailyButtonState() {
    const btn = document.getElementById('btn-daily');
    if (!btn) return;
    if (localStorage.getItem(`clubcombos_daily_${getDailyKey()}`)) {
        btn.textContent = '✓ Daily Completed – View Result';
        btn.classList.add('btn-daily-done');
    } else {
        btn.textContent = '🗓 Today\'s Daily Challenge';
        btn.classList.remove('btn-daily-done');
    }
}

// --- Initialization ---

// Timeout handle so we can cancel the end-screen transition if user navigates away early
let gameOverTimeoutId = null;

function init() {
    state.focusTeams = TRIVIA_DATA.focus_teams;

    // Bind buttons
    document.querySelectorAll('[data-size]').forEach(btn => {
        btn.addEventListener('click', (e) => startGame(parseInt(e.target.dataset.size)));
    });

    document.getElementById('btn-daily').addEventListener('click', startDailyChallenge);
    document.getElementById('btn-give-up').addEventListener('click', gameOver);
    document.getElementById('btn-restart').addEventListener('click', resetToStart);
    document.getElementById('btn-play-again').addEventListener('click', resetToStart);
    document.getElementById('btn-share').addEventListener('click', handleShare);

    // Common Club buttons
    document.getElementById('btn-common-club').addEventListener('click', startCommonClub);
    document.getElementById('cc-quit-btn').addEventListener('click', resetToStart);
    document.getElementById('cc-play-again-btn').addEventListener('click', startCommonClub);
    document.getElementById('cc-menu-btn').addEventListener('click', resetToStart);
    document.getElementById('cc-share-btn').addEventListener('click', handleCCShare);
    document.getElementById('cc-search-input').addEventListener('input', handleCCSearch);
    document.getElementById('cc-give-up-btn').addEventListener('click', handleCCGiveUp);

    // Career Path buttons
    document.getElementById('btn-career-path').addEventListener('click', startCareerPath);
    document.getElementById('cp-submit-btn').addEventListener('click', submitCPOrder);
    document.getElementById('cp-give-up-btn').addEventListener('click', handleCPGiveUp);
    document.getElementById('cp-quit-btn').addEventListener('click', resetToStart);
    document.getElementById('cp-play-again-btn').addEventListener('click', startCareerPath);
    document.getElementById('cp-menu-btn').addEventListener('click', resetToStart);
    document.getElementById('cp-share-btn').addEventListener('click', handleCPShare);

    // Close CC dropdown when clicking outside
    document.addEventListener('click', e => {
        const wrap = document.getElementById('cc-search-input')?.closest('.cc-search-wrap');
        if (wrap && !wrap.contains(e.target)) {
            document.getElementById('cc-dropdown').classList.add('hidden');
        }
    });

    // Modal events
    dom.btnCloseModal.addEventListener('click', closeModal);
    dom.btnSurrenderCell.addEventListener('click', handleSurrenderCell);
    dom.searchInput.addEventListener('input', handleSearch);

    // Close modal on escape or background click
    document.addEventListener('keydown', e => {
        if(e.key === 'Escape' && !dom.searchModal.classList.contains('hidden')) {
            closeModal();
        }
    });
    dom.searchModal.addEventListener('click', e => {
        if(e.target === dom.searchModal) closeModal();
    });

    updateDailyButtonState();
}

function showView(viewName) {
    Object.values(views).forEach(v => v.classList.remove('active'));
    views[viewName].classList.add('active');
}

// --- Game Flow ---

function startGame(columns) {
    state.gridSize = columns;
    const totalCells = TRIVIA_DATA.focus_teams.length * columns;
    state.lives = totalCells;
    state.score = 0;
    state.cells = {};
    state.usedPlayers.clear();
    dom.maxScore.textContent = totalCells;
    
    document.getElementById('btn-give-up').style.display = 'block';
    
    // Filter target teams based on Easy Mode toggle
    const isEasyMode = document.getElementById('easy-mode-toggle').checked;
    let availableTargets = [...TRIVIA_DATA.valid_target_teams];
    
    if (isEasyMode) {
        availableTargets = availableTargets.filter(target => {
            // Must have at least 2 players for EVERY focus team (Greek giant)
            return state.focusTeams.every(focusTeam => {
                const validPlayers = TRIVIA_DATA.matrix[focusTeam.id]?.[target.id];
                return validPlayers && validPlayers.length >= 2;
            });
        });
        
        // Safety fallback in case there aren't enough 2+ player teams
        if (availableTargets.length < columns) {
            console.warn("Not enough Easy Mode targets found, falling back to normal mode.");
            availableTargets = [...TRIVIA_DATA.valid_target_teams];
        }
    }
    
    // Randomly select n target teams
    shuffleArray(availableTargets);
    state.columns = availableTargets.slice(0, columns);
    
    renderLives();
    dom.score.textContent = state.score;
    
    buildGrid();
    showView('game');
}

function buildGrid() {
    // 1. Setup CSS Grid Templates
    const colTemplate = `1fr repeat(${state.gridSize}, 1fr)`;
    dom.gridHeader.style.gridTemplateColumns = colTemplate;
    
    // 2. Build Header
    dom.gridHeader.innerHTML = '<div class="empty-corner"></div>';
    state.columns.forEach(col => {
        dom.gridHeader.innerHTML += `
            <div class="team-col-header">
                <span>${col.name.split(':')[0] || 'Club'}</span>
                <div>${col.name.replace(/^[A-Z]+:\s*/, '')}</div>
            </div>
        `;
    });
    
    // 3. Build Body Rows
    dom.gridBody.innerHTML = '';
    state.focusTeams.forEach(row => {
        const rowDiv = document.createElement('div');
        rowDiv.className = 'grid-row';
        rowDiv.style.gridTemplateColumns = colTemplate;
        
        // Greek Team Header
        rowDiv.innerHTML = `
            <div class="team-row-header" data-id="${row.id}">
                ${row.name.replace(/^[A-Z]+:\s*/, '')}
            </div>
        `;
        
        // Interactive Cells
        state.columns.forEach(col => {
            const cellId = `${row.id}-${col.id}`;
            state.cells[cellId] = 'empty';
            
            const cellDiv = document.createElement('div');
            cellDiv.className = 'grid-cell';
            cellDiv.dataset.id = cellId;
            cellDiv.innerHTML = `<div class="cell-icon">+</div>`;
            
            cellDiv.addEventListener('click', () => openSearchForCell(cellId));
            rowDiv.appendChild(cellDiv);
        });
        
        dom.gridBody.appendChild(rowDiv);
    });
}

function renderLives() {
    dom.livesContainer.innerHTML = '';
    const totalCells = state.focusTeams.length * state.gridSize;
    for(let i=0; i<totalCells; i++) {
        const span = document.createElement('span');
        span.className = `life-icon ${i >= state.lives ? 'lost' : ''}`;
        span.innerHTML = '♥';
        dom.livesContainer.appendChild(span);
    }
}

// --- Search Modal & Guessing ---

function openSearchForCell(cellId) {
    if(state.cells[cellId] !== 'empty') return; // Cannot guess an already solved/failed cell
    if(state.lives <= 0) return;
    
    state.activeCellId = cellId;
    dom.searchInput.value = '';
    dom.searchResults.innerHTML = '';
    
    // Try to focus after transition
    dom.searchModal.classList.remove('hidden');
    setTimeout(() => dom.searchInput.focus(), 100);
}

function closeModal() {
    dom.searchModal.classList.add('hidden');
    state.activeCellId = null;
}

function handleSurrenderCell() {
    if (!state.activeCellId) return;
    
    state.lives--;
    renderLives();
    
    const [r, c] = state.activeCellId.split('-');
    const valid = TRIVIA_DATA.matrix[r][c];
    const cellEl = document.querySelector(`.grid-cell[data-id="${state.activeCellId}"]`);
    
    state.cells[state.activeCellId] = 'failed';
    cellEl.className = 'grid-cell failed';
    
    if(valid && valid.length > 0) {
        const names = valid.map(id => TRIVIA_DATA.players[id]);
        const displayNames = names.join('<br/>');
        
        cellEl.innerHTML = `
            <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;text-align:center;width:100%;">Missed:</div>
            <div class="player-name" style="font-size:0.8rem;opacity:0.8;text-align:center;line-height:1.2;width:100%;">
                ${displayNames}
            </div>
        `;
    } else {
        cellEl.innerHTML = `<div class="cell-icon" style="color:var(--error-color)">×</div>`;
    }
    
    closeModal();
    showToast(`You surrendered this cell.`, 'error');
    
    if (state.lives <= 0) {
        gameOver();
    }
}

function handleSearch(e) {
    const query = stripDiacritics(e.target.value.toLowerCase().trim());
    if(query.length < 2) {
        dom.searchResults.innerHTML = '';
        return;
    }
    
    // Search the full dictionary (diacritic-insensitive)
    const results = [];
    for(const [pid, name] of Object.entries(TRIVIA_DATA.players)) {
        const normalizedName = stripDiacritics(name.toLowerCase());
        if(normalizedName.includes(query)) {
            // Don't show already used players
            if(!state.usedPlayers.has(pid)) {
                results.push({ id: pid, name: name });
            }
        }
        if(results.length > 20) break; // limit to 20
    }
    
    renderSearchResults(results, query);
}

function renderSearchResults(results, query) {
    dom.searchResults.innerHTML = '';
    
    if(results.length === 0) {
        dom.searchResults.innerHTML = `<div class="result-empty">No matching unused players found.</div>`;
        return;
    }
    
    results.forEach(player => {
        const div = document.createElement('div');
        div.className = 'result-item';
        // Highlight matching text
        const regex = new RegExp(`(${query})`, 'gi');
        div.innerHTML = player.name.replace(regex, '<mark style="background:rgba(255,255,255,0.2);color:inherit">$1</mark>');
        
        div.addEventListener('click', () => makeGuess(player.id, player.name));
        dom.searchResults.appendChild(div);
    });
}

function makeGuess(playerId, playerName) {
    if(!state.activeCellId) return;
    
    const currentCellId = state.activeCellId;
    const [rowId, colId] = currentCellId.split('-');
    const validPlayers = TRIVIA_DATA.matrix[rowId][colId] || [];
    
    closeModal();
    const cellEl = document.querySelector(`.grid-cell[data-id="${currentCellId}"]`);
    
    // Check Answer
    if(validPlayers.includes(playerId)) {
        // Correct
        state.cells[currentCellId] = 'solved';
        state.usedPlayers.add(playerId);
        state.score++;
        dom.score.textContent = state.score;
        
        // Find other valid players for tooltip
        const otherValid = validPlayers.filter(id => id !== playerId);
        const otherNames = otherValid.map(id => TRIVIA_DATA.players[id]);
        
        let tooltipHTML = '';
        if(otherNames.length > 0) {
            const namesList = otherNames.join('<br/>');
            tooltipHTML = `
                <div class="cell-tooltip">
                    <div style="font-weight:700;margin-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:4px;">Other Valid Answers:</div>
                    <div style="line-height:1.4;">${namesList}</div>
                </div>`;
        } else {
            tooltipHTML = `<div class="cell-tooltip" style="text-align:center;">Only valid answer!</div>`;
        }
        
        // Update Cell UI
        cellEl.className = 'grid-cell solved loading-img';
        cellEl.innerHTML = `
            <div class="player-image-container">
                <div class="loader"></div>
            </div>
            <div class="player-name-wrapper">
                <div class="player-name">${playerName}</div>
                ${tooltipHTML}
            </div>
        `;
        
        fetchPlayerImage(playerName).then(imgUrl => {
            const imgContainer = cellEl.querySelector('.player-image-container');
            if(imgUrl) {
                imgContainer.innerHTML = `<img src="${imgUrl}" class="player-headshot" alt="${playerName}" />`;
            } else {
                imgContainer.innerHTML = `
                    <svg class="player-headshot fallback-silhouette" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                        <circle cx="12" cy="7" r="4"></circle>
                    </svg>
                `;
            }
            cellEl.classList.remove('loading-img');
        });
        
        showToast(`Correct! ${playerName}`, 'success');
        checkWinCondition();
    } else {
        // Wrong
        state.lives--;
        renderLives();
        
        showToast(`Incorrect! ${playerName} doesn't match.`, 'error');
        
        /* Note: In traditional immaculate grid, a wrong guess doesn't lock the cell. 
           It just costs a life. The user can try the cell again later. */
        
        // Visual shake feedback
        cellEl.style.transform = 'translate(-5px, 0)';
        setTimeout(() => cellEl.style.transform = 'translate(5px, 0)', 50);
        setTimeout(() => cellEl.style.transform = 'translate(-4px, 0)', 100);
        setTimeout(() => cellEl.style.transform = 'translate(4px, 0)', 150);
        setTimeout(() => cellEl.style.transform = 'translate(0, 0)', 200);
        
        if(state.lives <= 0) {
            gameOver();
        }
    }
}

// --- Notifications ---

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Add to body
    document.body.appendChild(toast);
    
    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- End States ---

function checkWinCondition() {
    const totalCells = state.focusTeams.length * state.gridSize;
    if(state.score === totalCells) {
        setTimeout(() => {
            gameOver();
        }, 500);
    }
}

function gameOver() {
    state.lives = 0;
    renderLives();
    document.getElementById('btn-give-up').style.display = 'none';

    const totalCells = state.focusTeams.length * state.gridSize;

    if(state.score === totalCells) {
        showToast(`Immaculate! Perfect ${state.score}/${totalCells}!`, 'success');
    } else if(state.score === 0) {
        showToast(`Rough day. 0/${totalCells} correct.`, 'error');
    } else {
        showToast(`Game Over! You scored ${state.score}/${totalCells}.`, 'error');
    }

    // Reveal missing answers on the board
    Object.keys(state.cells).forEach(cellId => {
        if(state.cells[cellId] === 'empty') {
            const [r, c] = cellId.split('-');
            const valid = TRIVIA_DATA.matrix[r][c];
            const cellEl = document.querySelector(`.grid-cell[data-id="${cellId}"]`);
            cellEl.className = 'grid-cell failed';

            if(valid && valid.length > 0) {
                const names = valid.map(id => TRIVIA_DATA.players[id]);
                const displayNames = names.join('<br/>');

                cellEl.innerHTML = `
                    <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;text-align:center;width:100%;">Missed:</div>
                    <div class="player-name" style="font-size:0.8rem;opacity:0.8;text-align:center;line-height:1.2;width:100%;">
                        ${displayNames}
                    </div>
                `;
            } else {
                cellEl.innerHTML = `<div class="cell-icon" style="color:var(--error-color)">×</div>`;
            }
        }
    });

    // Transition to end screen after a short delay so the reveals are visible
    gameOverTimeoutId = setTimeout(() => {
        gameOverTimeoutId = null;

        if (state.score === totalCells) {
            dom.endTitle.textContent = 'Immaculate!';
        } else if (state.score === 0) {
            dom.endTitle.textContent = 'Rough Day...';
        } else {
            dom.endTitle.textContent = 'Game Over!';
        }
        dom.endMsg.textContent = `You scored ${state.score} out of ${totalCells}.`;

        if (state.isDailyChallenge) {
            saveDailyResult();
            updateDailyButtonState();
            document.getElementById('daily-emoji-grid').textContent = generateEmojiGrid();
            document.getElementById('share-section').classList.remove('hidden');
        } else {
            document.getElementById('share-section').classList.add('hidden');
        }

        showView('end');
    }, 1500);
}

function resetToStart() {
    if (gameOverTimeoutId) {
        clearTimeout(gameOverTimeoutId);
        gameOverTimeoutId = null;
    }
    state.isDailyChallenge = false;
    document.getElementById('share-section').classList.add('hidden');
    document.querySelector('.score-panel').style.visibility = '';
    updateDailyButtonState();
    showView('start');
}

// --- Utils ---
function shuffleArray(array) {
    for (let i = array.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [array[i], array[j]] = [array[j], array[i]];
    }
}

function stripDiacritics(str) {
    return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

function getClubBadge(clubName) {
    // Badge URLs are pre-fetched at build time and baked into TRIVIA_DATA.badges
    return TRIVIA_DATA.badges?.[clubName] ?? null;
}

async function fetchPlayerImage(playerName) {
    try {
        // We append "football" to improve Wikipedia search accuracy for common names
        const query = encodeURIComponent(playerName + " football");
        const url = `https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${query}&gsrlimit=1&prop=pageimages&piprop=thumbnail&pithumbsize=300&format=json&origin=*`;
        
        const res = await fetch(url);
        const data = await res.json();
        
        if(data && data.query && data.query.pages) {
            const pages = data.query.pages;
            const pageId = Object.keys(pages)[0];
            if(pages[pageId].thumbnail && pages[pageId].thumbnail.source) {
                return pages[pageId].thumbnail.source;
            }
        }
    } catch(err) {
        console.error("Wikipedia API error:", err);
    }
    return null;
}

// --- Common Club Game ---

const ccState = {
    puzzles: [],
    currentRound: 0,
    score: 0,
    results: [], // 'correct' | 'wrong' per round
    totalRounds: 6
};

function buildCommonClubPuzzles() {
    const puzzles = [];
    for (const team of TRIVIA_DATA.valid_target_teams) {
        const playerIdSet = new Set();
        for (const ft of TRIVIA_DATA.focus_teams) {
            (TRIVIA_DATA.matrix[ft.id]?.[team.id] || []).forEach(id => playerIdSet.add(id));
        }
        if (playerIdSet.size >= 4) {
            puzzles.push({
                clubId: team.id,
                clubName: team.name.replace(/^[A-Z]+:\s*/, ''),
                playerIds: [...playerIdSet]
            });
        }
    }
    return puzzles;
}

function startCommonClub() {
    const all = buildCommonClubPuzzles();
    shuffleArray(all);

    ccState.puzzles = all.slice(0, ccState.totalRounds);
    ccState.currentRound = 0;
    ccState.score = 0;
    ccState.results = [];

    document.getElementById('cc-game').classList.remove('hidden');
    document.getElementById('cc-results-panel').classList.add('hidden');
    document.querySelector('.score-panel').style.visibility = 'hidden';

    showView('commonClub');
    renderCCRound();
}

function renderCCRound() {
    const puzzle = ccState.puzzles[ccState.currentRound];

    document.getElementById('cc-round-num').textContent = ccState.currentRound + 1;
    document.getElementById('cc-total-rounds').textContent = ccState.totalRounds;
    document.getElementById('cc-score-display').textContent = ccState.score;

    // Pick 4 random players from the pool to show
    const pool = [...puzzle.playerIds];
    shuffleArray(pool);
    const shown = pool.slice(0, 4);

    document.getElementById('cc-players').innerHTML = shown.map(id => `
        <div class="cc-player-card">
            <div class="cc-player-name">${TRIVIA_DATA.players[id]}</div>
        </div>
    `).join('');

    const input = document.getElementById('cc-search-input');
    input.value = '';
    input.disabled = false;
    setTimeout(() => input.focus(), 100);

    const dropdown = document.getElementById('cc-dropdown');
    dropdown.innerHTML = '';
    dropdown.classList.add('hidden');

    document.getElementById('cc-feedback').innerHTML = '';

    const nextBtn = document.getElementById('cc-next-btn');
    nextBtn.classList.add('hidden');
    nextBtn.onclick = null;

    document.getElementById('cc-give-up-btn').style.display = '';
}

function handleCCGiveUp() {
    const puzzle = ccState.puzzles[ccState.currentRound];
    ccState.results.push('wrong');

    const input = document.getElementById('cc-search-input');
    input.disabled = true;
    document.getElementById('cc-dropdown').classList.add('hidden');
    document.getElementById('cc-give-up-btn').style.display = 'none';

    document.getElementById('cc-feedback').innerHTML =
        `<div class="cc-feedback-wrong">The answer was <strong>${puzzle.clubName}</strong>.</div>`;

    const nextBtn = document.getElementById('cc-next-btn');
    nextBtn.classList.remove('hidden');

    if (ccState.currentRound === ccState.totalRounds - 1) {
        nextBtn.textContent = 'See Results →';
        nextBtn.onclick = showCCResults;
    } else {
        nextBtn.textContent = 'Next Round →';
        nextBtn.onclick = () => { ccState.currentRound++; renderCCRound(); };
    }
}

function handleCCSearch(e) {
    const query = stripDiacritics(e.target.value.toLowerCase().trim());
    const dropdown = document.getElementById('cc-dropdown');

    if (query.length < 2) {
        dropdown.classList.add('hidden');
        return;
    }

    const matches = TRIVIA_DATA.valid_target_teams.filter(team => {
        const name = team.name.replace(/^[A-Z]+:\s*/, '');
        return stripDiacritics(name.toLowerCase()).includes(query);
    }).slice(0, 8);

    if (matches.length === 0) {
        dropdown.classList.add('hidden');
        return;
    }

    dropdown.innerHTML = matches.map(team => {
        const name = team.name.replace(/^[A-Z]+:\s*/, '');
        return `<div class="result-item" data-id="${team.id}" data-name="${name}">${name}</div>`;
    }).join('');
    dropdown.classList.remove('hidden');

    dropdown.querySelectorAll('.result-item').forEach(item => {
        item.addEventListener('click', () => handleCCGuess(item.dataset.id, item.dataset.name));
    });
}

function handleCCGuess(clubId, clubName) {
    const puzzle = ccState.puzzles[ccState.currentRound];
    const isCorrect = clubId === puzzle.clubId;

    const input = document.getElementById('cc-search-input');
    input.disabled = true;
    input.value = clubName;
    document.getElementById('cc-dropdown').classList.add('hidden');
    document.getElementById('cc-give-up-btn').style.display = 'none';

    if (isCorrect) {
        ccState.score++;
        ccState.results.push('correct');
        document.getElementById('cc-score-display').textContent = ccState.score;
        document.getElementById('cc-feedback').innerHTML =
            `<div class="cc-feedback-correct">✓ Correct! It was <strong>${puzzle.clubName}</strong>.</div>`;
        showToast(`Correct! ${puzzle.clubName}`, 'success');
    } else {
        ccState.results.push('wrong');
        document.getElementById('cc-feedback').innerHTML =
            `<div class="cc-feedback-wrong">✗ Wrong! The answer was <strong>${puzzle.clubName}</strong>.</div>`;
        showToast(`It was ${puzzle.clubName}`, 'error');
    }

    const nextBtn = document.getElementById('cc-next-btn');
    nextBtn.classList.remove('hidden');

    if (ccState.currentRound === ccState.totalRounds - 1) {
        nextBtn.textContent = 'See Results →';
        nextBtn.onclick = showCCResults;
    } else {
        nextBtn.textContent = 'Next Round →';
        nextBtn.onclick = () => {
            ccState.currentRound++;
            renderCCRound();
        };
    }
}

function showCCResults() {
    document.getElementById('cc-game').classList.add('hidden');
    document.getElementById('cc-results-panel').classList.remove('hidden');

    const score = ccState.score;
    const total = ccState.totalRounds;

    const title = score === total ? 'Perfect Score! 🎯' :
                  score >= Math.ceil(total * 0.7) ? 'Well Played!' :
                  score >= Math.ceil(total * 0.4) ? 'Not Bad!' :
                  'Better Luck Next Time!';

    document.getElementById('cc-result-title').textContent = title;
    document.getElementById('cc-result-msg').textContent = `Common Club · ${score}/${total}`;
    document.getElementById('cc-emoji-grid').textContent =
        ccState.results.map(r => r === 'correct' ? '🟩' : '🟥').join('');
}

async function handleCCShare() {
    const score = ccState.score;
    const total = ccState.totalRounds;
    const emojiGrid = document.getElementById('cc-emoji-grid').textContent;
    const text = `Club Combos – Common Club\n${emojiGrid}\nScore: ${score}/${total}\nhttps://konstantinoslaloudakis.github.io/ClubCombos/`;

    if (navigator.share) {
        try { await navigator.share({ text }); return; } catch(e) {}
    }
    try {
        await navigator.clipboard.writeText(text);
        showToast('Result copied to clipboard!', 'success');
    } catch(e) {
        showToast('Could not copy to clipboard.', 'error');
    }
}

// --- Career Path Game ---

const cpState = {
    puzzles: [],
    currentRound: 0,
    totalRounds: 5,
    score: 0,       // sum of correct pairs earned
    maxScore: 0,    // sum of possible pairs across played rounds
    results: [],    // [{earned, possible, gaveUp?}]
    currentScrambled: []  // clubs shown this round (shuffled); DOM order = user's answer
};

function buildCareerPuzzles() {
    const puzzles = [];
    for (const [pid, stints] of Object.entries(TRIVIA_DATA.careers)) {
        if (!stints || stints.length < 4) continue;

        let selected = [...stints];
        if (selected.length > 5) {
            // Keep the 5 most-played clubs, then restore chronological order
            selected.sort((a, b) => b.apps - a.apps);
            selected = selected.slice(0, 5);
        }
        selected.sort((a, b) => a.start_year - b.start_year);

        puzzles.push({
            playerId: pid,
            playerName: TRIVIA_DATA.players[pid],
            clubs: selected
        });
    }
    return puzzles;
}

function startCareerPath() {
    const all = buildCareerPuzzles();
    shuffleArray(all);

    cpState.puzzles = all.slice(0, cpState.totalRounds);
    cpState.currentRound = 0;
    cpState.score = 0;
    cpState.maxScore = 0;
    cpState.results = [];

    document.getElementById('cp-game').classList.remove('hidden');
    document.getElementById('cp-results-panel').classList.add('hidden');
    document.querySelector('.score-panel').style.visibility = 'hidden';

    showView('careerPath');
    renderCPRound();
}

function renderCPRound() {
    const puzzle = cpState.puzzles[cpState.currentRound];

    document.getElementById('cp-round-num').textContent = cpState.currentRound + 1;
    document.getElementById('cp-round-total').textContent = cpState.totalRounds;
    document.getElementById('cp-score-display').textContent = cpState.score;
    document.getElementById('cp-max-score-display').textContent = cpState.maxScore;
    document.getElementById('cp-player-name').textContent = puzzle.playerName;

    // Scramble clubs for this round
    cpState.currentScrambled = [...puzzle.clubs];
    shuffleArray(cpState.currentScrambled);

    renderCPCards();

    document.getElementById('cp-feedback').innerHTML = '';
    document.getElementById('cp-submit-btn').disabled = false;
    document.getElementById('cp-submit-btn').style.display = '';
    document.getElementById('cp-give-up-btn').style.display = '';

    const nextBtn = document.getElementById('cp-next-btn');
    nextBtn.classList.add('hidden');
    nextBtn.onclick = null;
}

function renderCPCards() {
    const container = document.getElementById('cp-clubs');
    container.innerHTML = cpState.currentScrambled.map((stint, idx) => `
        <div class="cp-club-card" data-stintidx="${idx}">
            <span class="cp-drag-handle">⠿</span>
            <div class="cp-badge-wrap"><img class="cp-club-badge" id="cp-badge-${idx}" draggable="false" alt=""></div>
            <span class="cp-club-name">${stint.club}</span>
        </div>
    `).join('');
    initCPDragDrop(container);

    cpState.currentScrambled.forEach((stint, idx) => {
        const img = document.getElementById(`cp-badge-${idx}`);
        if (!img) return;
        const src = getClubBadge(stint.club);
        if (src) { img.src = src; img.classList.add('loaded'); }
    });
}

function initCPDragDrop(container) {
    let drag = null;

    container.addEventListener('pointerdown', e => {
        const card = e.target.closest('.cp-club-card');
        if (!card) return;
        e.preventDefault();

        const rect = card.getBoundingClientRect();
        const grabOffsetY = e.clientY - rect.top;

        // Fixed clone follows the pointer
        const ghost = card.cloneNode(true);
        Object.assign(ghost.style, {
            position: 'fixed',
            left:  rect.left + 'px',
            top:   (e.clientY - grabOffsetY) + 'px',
            width: rect.width + 'px',
            margin: '0',
            zIndex: '9999',
            opacity: '0.9',
            pointerEvents: 'none',
            boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
            transform: 'scale(1.03)',
            transition: 'none',
        });
        document.body.appendChild(ghost);
        card.classList.add('cp-card-dragging');

        drag = { card, ghost, grabOffsetY };
        container.setPointerCapture(e.pointerId);
    });

    container.addEventListener('pointermove', e => {
        if (!drag) return;
        drag.ghost.style.top = (e.clientY - drag.grabOffsetY) + 'px';

        // Find insertion point by scanning other cards' midpoints
        const others = [...container.querySelectorAll('.cp-club-card:not(.cp-card-dragging)')];
        let insertBefore = null;
        for (const c of others) {
            const r = c.getBoundingClientRect();
            if (e.clientY < r.top + r.height / 2) { insertBefore = c; break; }
        }
        if (insertBefore) container.insertBefore(drag.card, insertBefore);
        else              container.appendChild(drag.card);
    });

    const endDrag = () => {
        if (!drag) return;
        drag.ghost.remove();
        drag.card.classList.remove('cp-card-dragging');
        drag = null;
    };
    container.addEventListener('pointerup',     endDrag);
    container.addEventListener('pointercancel', endDrag);
}

function cpScorePositions(userOrder, correctOrder) {
    // 1 point for each club that lands in its exact correct position.
    return correctOrder.map((stint, i) => userOrder[i]?.club === stint.club);
}

function showCPFeedback(userOrder, correctOrder, hits) {
    const earned = hits.filter(Boolean).length;
    const possible = hits.length;

    let html = '<div class="cp-correct-order">';
    html += '<p class="cp-feedback-label">Correct order:</p>';

    correctOrder.forEach((stint, i) => {
        const correct = hits[i];
        html += `
            <div class="cp-correct-item ${correct ? 'pos-correct' : 'pos-wrong'}">
                <span class="cp-pos-icon">${correct ? '✓' : '✗'}</span>
                <div class="cp-badge-wrap"><img class="cp-club-badge" id="cp-fb-badge-${i}" draggable="false" alt=""></div>
                <div class="cp-item-info">
                    <span class="cp-item-club">${stint.club}</span>
                    <span class="cp-item-years">${stint.start_year}–${stint.end_year} · ${stint.apps} apps</span>
                </div>
            </div>`;
    });

    // Load badges into feedback rows after HTML is set
    setTimeout(() => {
        correctOrder.forEach((stint, i) => {
            const img = document.getElementById(`cp-fb-badge-${i}`);
            if (!img) return;
            const src = getClubBadge(stint.club);
            if (src) { img.src = src; img.classList.add('loaded'); }
        });
    }, 0);

    html += `<p class="cp-round-score">${earned}/${possible} clubs in the right position</p>`;
    html += '</div>';

    document.getElementById('cp-feedback').innerHTML = html;
}

function submitCPOrder() {
    const puzzle = cpState.puzzles[cpState.currentRound];
    const userOrder = [...document.querySelectorAll('#cp-clubs .cp-club-card')]
        .map(c => cpState.currentScrambled[parseInt(c.dataset.stintidx)]);
    const hits = cpScorePositions(userOrder, puzzle.clubs);
    const earned = hits.filter(Boolean).length;
    const possible = hits.length;

    cpState.score += earned;
    cpState.maxScore += possible;
    cpState.results.push({ earned, possible });

    document.getElementById('cp-score-display').textContent = cpState.score;
    document.getElementById('cp-max-score-display').textContent = cpState.maxScore;
    document.getElementById('cp-submit-btn').style.display = 'none';
    document.getElementById('cp-give-up-btn').style.display = 'none';
    document.querySelectorAll('.cp-club-card').forEach(c => c.style.pointerEvents = 'none');

    showCPFeedback(userOrder, puzzle.clubs, hits);
    advanceCPRound();
}

function handleCPGiveUp() {
    const puzzle = cpState.puzzles[cpState.currentRound];
    const possible = puzzle.clubs.length;

    cpState.maxScore += possible;
    cpState.results.push({ earned: 0, possible, gaveUp: true });

    document.getElementById('cp-max-score-display').textContent = cpState.maxScore;
    document.getElementById('cp-submit-btn').style.display = 'none';
    document.getElementById('cp-give-up-btn').style.display = 'none';
    document.querySelectorAll('.cp-club-card').forEach(c => c.style.pointerEvents = 'none');

    showCPFeedback(null, puzzle.clubs, new Array(puzzle.clubs.length).fill(false));
    advanceCPRound();
}

function advanceCPRound() {
    const nextBtn = document.getElementById('cp-next-btn');
    nextBtn.classList.remove('hidden');
    const isLast = cpState.currentRound === cpState.totalRounds - 1;
    nextBtn.textContent = isLast ? 'See Results →' : 'Next Round →';
    nextBtn.onclick = isLast ? showCPResults : () => { cpState.currentRound++; renderCPRound(); };
}

function showCPResults() {
    document.getElementById('cp-game').classList.add('hidden');
    document.getElementById('cp-results-panel').classList.remove('hidden');

    const score = cpState.score;
    const max = cpState.maxScore;
    const pct = max > 0 ? score / max : 0;

    const title = pct === 1    ? 'Perfect! 🎯'  :
                  pct >= 0.75  ? 'Great Work!'   :
                  pct >= 0.5   ? 'Not Bad!'      :
                  pct > 0      ? 'Keep Practising!' : 'Better Luck Next Time!';

    document.getElementById('cp-result-title').textContent = title;
    document.getElementById('cp-result-msg').textContent = `Career Path · ${score}/${max} clubs correct`;

    const emojis = cpState.results.map(r => {
        if (r.gaveUp) return '⬛';
        if (r.earned === r.possible) return '🟩';
        if (r.earned > 0) return '🟨';
        return '🟥';
    }).join('');
    document.getElementById('cp-emoji-grid').textContent = emojis;
}

async function handleCPShare() {
    const score = cpState.score;
    const max = cpState.maxScore;
    const emojis = document.getElementById('cp-emoji-grid').textContent;
    const text = `Club Combos – Career Path\n${emojis}\nScore: ${score}/${max} clubs correct\nhttps://konstantinoslaloudakis.github.io/ClubCombos/`;

    if (navigator.share) {
        try { await navigator.share({ text }); return; } catch(e) {}
    }
    try {
        await navigator.clipboard.writeText(text);
        showToast('Result copied to clipboard!', 'success');
    } catch(e) {
        showToast('Could not copy to clipboard.', 'error');
    }
}

// Start
document.addEventListener('DOMContentLoaded', init);
