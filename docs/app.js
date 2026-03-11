// ─── State ──────────────────────────────────────
let pot = 0;
let specialPot = 0;

// ─── DOM refs ───────────────────────────────────
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

// ─── Helpers ────────────────────────────────────
function fmt(n) { return n.toFixed(2) + '€'; }

function updateBars(newPot, newSpecialPot) {
  pot = newPot;
  specialPot = newSpecialPot;
  potBar.style.width = Math.min((pot / 10) * 100, 100) + '%';
  specialPotBar.style.width = Math.min((specialPot / 100) * 100, 100) + '%';
  specialAmt.textContent = fmt(specialPot);
}

function showNotif(msg, isError = false) {
  notification.textContent = msg;
  notification.className = 'notification' + (isError ? ' error' : '');
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

function addHistoryEntry(player, potWin, specialWin, timestamp) {
  const li = document.createElement('li');
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

  // Keep max 10 entries visible
  while (historyList.children.length > 10) {
    historyList.removeChild(historyList.lastChild);
  }
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Load initial status ─────────────────────────
async function loadStatus() {
  try {
    const res  = await fetch('/api/status');
    const data = await res.json();
    updateBars(data.pot, data.specialPot);

    data.history.slice().reverse().forEach(h => {
      addHistoryEntry(h.player, h.potWin, h.specialWin, h.timestamp);
    });
  } catch (e) {
    showNotif('Impossible de charger le statut du serveur.', true);
  }
}

// ─── Bet handler ────────────────────────────────
betForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  const name = playerName.value.trim();
  if (!name) {
    playerName.classList.add('shake');
    setTimeout(() => playerName.classList.remove('shake'), 300);
    return;
  }

  betBtn.disabled = true;
  betBtn.querySelector('.btn-text').hidden = true;
  betBtn.querySelector('.btn-spinner').hidden = false;

  try {
    const res  = await fetch('/api/bet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });

    const data = await res.json();

    if (!res.ok) {
      showNotif(data.error || 'Une erreur est survenue.', true);
      return;
    }

    updateBars(data.pot, data.specialPot);
    addHistoryEntry(name, data.potWin, data.specialWin, new Date().toISOString());

    if (data.specialWin > 0) {
      showWin('🏆', 'JACKPOT !!!', `Félicitations ${name} ! La cagnotte spéciale a atteint 100€ et vous remporte 100€ !`);
    } else if (data.potWin > 0) {
      showWin('🎉', 'Vous avez gagné !', `Bravo ${name} ! La cagnotte a atteint 10€, vous remportez 9€ !`);
    } else {
      const msgs = data.events.map(ev => ev.message).join(' ');
      showNotif(msgs || `Mise de 2€ enregistrée. Cagnotte actuelle : ${fmt(data.pot)}`);
    }

  } catch (err) {
    showNotif('Erreur réseau. Veuillez réessayer.', true);
  } finally {
    betBtn.disabled = false;
    betBtn.querySelector('.btn-text').hidden = false;
    betBtn.querySelector('.btn-spinner').hidden = true;
  }
});

// ─── Init ────────────────────────────────────────
loadStatus();
