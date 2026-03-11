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
    usedPlayers: new Set() // Prevent using the same player twice
};

// DOM Elements
const views = {
    start: document.getElementById('start-screen'),
    game: document.getElementById('game-screen'),
    end: document.getElementById('game-over-screen')
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
    
    // End screen
    endTitle: document.getElementById('end-title'),
    endMsg: document.getElementById('end-message')
};

// --- Initialization ---

function init() {
    state.focusTeams = TRIVIA_DATA.focus_teams;
    
    // Bind buttons
    document.querySelectorAll('[data-size]').forEach(btn => {
        btn.addEventListener('click', (e) => startGame(parseInt(e.target.dataset.size)));
    });
    
    document.getElementById('btn-give-up').addEventListener('click', gameOver);
    document.getElementById('btn-restart').addEventListener('click', resetToStart);
    document.getElementById('btn-play-again').addEventListener('click', resetToStart);
    
    // Modal events
    dom.btnCloseModal.addEventListener('click', closeModal);
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
    
    // Randomly select n valid target teams
    const allTargets = [...TRIVIA_DATA.valid_target_teams];
    shuffleArray(allTargets);
    state.columns = allTargets.slice(0, columns);
    
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
                imgContainer.innerHTML = `<div class="no-image-placeholder">No Image</div>`;
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
    
    // Reveal missing answers
    Object.keys(state.cells).forEach(cellId => {
        if(state.cells[cellId] === 'empty') {
            const [r, c] = cellId.split('-');
            const valid = TRIVIA_DATA.matrix[r][c];
            const cellEl = document.querySelector(`.grid-cell[data-id="${cellId}"]`);
            cellEl.className = 'grid-cell failed';
            
            if(valid && valid.length > 0) {
                // Show all valid answers
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
}

function resetToStart() {
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

// Start
document.addEventListener('DOMContentLoaded', init);
