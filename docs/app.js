// ─── Storage ─────────────────────────────────────
const STORAGE_KEY = 'cagnotte_data';

function loadData() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (_) {}
  return { pot: 0, specialPot: 0, history: [] };
}

function saveData(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

// ─── DOM refs ─────────────────────────────────────
const betForm       = document.getElementById('betForm');
const playerName    = document.getElementById('playerName');
const betBtn        = document.getElementById('betBtn');
const potBar        = document.getElementById('potBar');
const specialPotBar = document.getElementById('specialPotBar');
const specialAmt    = document.getElementById('specialPotAmount');
const notification  = document.getElementById('notification');
const historyList   = document.getElementById('historyList');
const winOverlay    = document.getElementById('winOverlay');
const winEmoji      = document.getElementById('winEmoji');
const winTitle      = document.getElementById('winTitle');
const winMsg        = document.getElementById('winMsg');

// ─── Helpers ──────────────────────────────────────
function fmt(n) { return n.toFixed(2) + '€'; }

function updateBars(pot, specialPot) {
  potBar.style.width        = Math.min((pot / 10) * 100, 100) + '%';
  specialPotBar.style.width = Math.min((specialPot / 100) * 100, 100) + '%';
  specialAmt.textContent    = fmt(specialPot);
}

function showNotif(msg, isError = false) {
  notification.textContent = msg;
  notification.className   = 'notification' + (isError ? ' error' : '');
  notification.classList.remove('hidden');
  setTimeout(() => notification.classList.add('hidden'), 5000);
}

function showWin(emoji, title, msg) {
  winEmoji.textContent = emoji;
  winTitle.textContent = title;
  winMsg.textContent   = msg;
  winOverlay.classList.remove('hidden');
}

window.closeOverlay = function () {
  winOverlay.classList.add('hidden');
};

function escHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function addHistoryEntry(player, potWin, specialWin, timestamp) {
  const li   = document.createElement('li');
  const time = new Date(timestamp).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });

  let winHtml = '';
  if (specialWin > 0) {
    winHtml = `<span class="jackpot">🏆 JACKPOT +${fmt(specialWin)}</span>`;
  } else if (potWin > 0) {
    winHtml = `<span class="win">🎉 +${fmt(potWin)}</span>`;
  }

  li.innerHTML = `
    <span><span class="player">${escHtml(player)}</span> — misé 2€ ${winHtml}</span>
    <span class="time">${time}</span>
  `;
  historyList.prepend(li);

  while (historyList.children.length > 10) {
    historyList.removeChild(historyList.lastChild);
  }
}

// ─── Bet logic (sans serveur) ──────────────────────
function placeBet(name) {
  const data = loadData();

  data.pot += 2;

  let potWin     = 0;
  let specialWin = 0;

  if (data.pot >= 10) {
    potWin      = 9;
    data.pot   -= 10;
    data.specialPot += 1;

    if (data.specialPot >= 100) {
      specialWin       = 100;
      data.specialPot -= 100;
    }
  }

  const entry = {
    timestamp:  new Date().toISOString(),
    player:     name,
    potWin,
    specialWin,
    potAfter:        data.pot,
    specialPotAfter: data.specialPot
  };
  data.history.push(entry);
  if (data.history.length > 100) data.history = data.history.slice(-100);

  saveData(data);

  return { pot: data.pot, specialPot: data.specialPot, potWin, specialWin };
}

// ─── Init ─────────────────────────────────────────
function init() {
  const data = loadData();
  updateBars(data.pot, data.specialPot);
  data.history.slice(-10).reverse().forEach(h => {
    addHistoryEntry(h.player, h.potWin, h.specialWin, h.timestamp);
  });
}

// ─── Form handler ─────────────────────────────────
betForm.addEventListener('submit', (e) => {
  e.preventDefault();

  const name = playerName.value.trim();
  if (!name) {
    playerName.classList.add('shake');
    setTimeout(() => playerName.classList.remove('shake'), 300);
    return;
  }

  betBtn.disabled = true;

  const result = placeBet(name);
  updateBars(result.pot, result.specialPot);
  addHistoryEntry(name, result.potWin, result.specialWin, new Date().toISOString());

  if (result.specialWin > 0) {
    showWin('🏆', 'JACKPOT !!!', `Félicitations ${name} ! La cagnotte spéciale a atteint 100€, vous remportez 100€ !`);
  } else if (result.potWin > 0) {
    showWin('🎉', 'Vous avez gagné !', `Bravo ${name} ! La cagnotte a atteint 10€, vous remportez 9€ !`);
  } else {
    showNotif(`Mise de 2€ enregistrée. Cagnotte secrète : ${fmt(result.pot)}`);
  }

  betBtn.disabled = false;
});

init();
