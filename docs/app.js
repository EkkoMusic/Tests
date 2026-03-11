// ─── Auth state ────────────────────────────────────
let authToken   = localStorage.getItem('token');
let currentUser = null;

// ─── DOM refs ─────────────────────────────────────
const authSection   = document.getElementById('authSection');
const gameSection   = document.getElementById('gameSection');
const tabLogin      = document.getElementById('tabLogin');
const tabRegister   = document.getElementById('tabRegister');
const loginForm     = document.getElementById('loginForm');
const registerForm  = document.getElementById('registerForm');
const loginUsername = document.getElementById('loginUsername');
const loginPassword = document.getElementById('loginPassword');
const regUsername   = document.getElementById('regUsername');
const regPassword   = document.getElementById('regPassword');
const authNotif     = document.getElementById('authNotif');
const userNameEl    = document.getElementById('userName');
const userBalanceEl = document.getElementById('userBalance');
const logoutBtn     = document.getElementById('logoutBtn');
const betForm       = document.getElementById('betForm');
const betBtn        = document.getElementById('betBtn');
const notification  = document.getElementById('notification');
const historyList   = document.getElementById('historyList');
const winOverlay    = document.getElementById('winOverlay');
const winEmoji      = document.getElementById('winEmoji');
const winTitle      = document.getElementById('winTitle');
const winMsg        = document.getElementById('winMsg');

// ─── Helpers ──────────────────────────────────────
function fmt(n) { return Number(n).toFixed(2) + '€'; }

function showNotif(msg, isError = false) {
  notification.textContent = msg;
  notification.className   = 'notification' + (isError ? ' error' : '');
  notification.classList.remove('hidden');
  setTimeout(() => notification.classList.add('hidden'), 5000);
}

function showAuthNotif(msg, isError = false) {
  authNotif.textContent = msg;
  authNotif.className   = 'notification' + (isError ? ' error' : '');
  authNotif.classList.remove('hidden');
  setTimeout(() => authNotif.classList.add('hidden'), 5000);
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
    winHtml = `<span class="jackpot">🏆 JACKPOT</span>`;
  } else if (potWin > 0) {
    winHtml = `<span class="win">🎉 Gagné !</span>`;
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

// ─── Auth display ──────────────────────────────────
function showAuth() {
  authSection.classList.remove('hidden');
  gameSection.classList.add('hidden');
}

function showGame(user) {
  currentUser             = user;
  userNameEl.textContent  = user.username;
  userBalanceEl.textContent = fmt(user.balance);
  authSection.classList.add('hidden');
  gameSection.classList.remove('hidden');
  loadStatus();
}

// ─── Auth tab switching ────────────────────────────
tabLogin.addEventListener('click', () => {
  tabLogin.classList.add('active');
  tabRegister.classList.remove('active');
  loginForm.classList.remove('hidden');
  registerForm.classList.add('hidden');
  authNotif.classList.add('hidden');
});

tabRegister.addEventListener('click', () => {
  tabRegister.classList.add('active');
  tabLogin.classList.remove('active');
  registerForm.classList.remove('hidden');
  loginForm.classList.add('hidden');
  authNotif.classList.add('hidden');
});

// ─── Login ─────────────────────────────────────────
loginForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = loginUsername.value.trim();
  const password = loginPassword.value;
  if (!username || !password) return;

  try {
    const res  = await fetch('/api/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) { showAuthNotif(data.error || 'Erreur de connexion.', true); return; }
    authToken = data.token;
    localStorage.setItem('token', data.token);
    showGame({ username: data.username, balance: data.balance });
  } catch (err) {
    showAuthNotif('Erreur réseau.', true);
  }
});

// ─── Register ──────────────────────────────────────
registerForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = regUsername.value.trim();
  const password = regPassword.value;
  if (!username || !password) return;

  try {
    const res  = await fetch('/api/register', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) { showAuthNotif(data.error || 'Erreur d\'inscription.', true); return; }
    authToken = data.token;
    localStorage.setItem('token', data.token);
    showGame({ username: data.username, balance: data.balance });
  } catch (err) {
    showAuthNotif('Erreur réseau.', true);
  }
});

// ─── Logout ────────────────────────────────────────
logoutBtn.addEventListener('click', () => {
  authToken   = null;
  currentUser = null;
  localStorage.removeItem('token');
  historyList.innerHTML = '';
  showAuth();
});

// ─── Load status (history only) ────────────────────
async function loadStatus() {
  try {
    const res  = await fetch('/api/status');
    const data = await res.json();
    (data.history || []).slice().reverse().forEach(h => {
      addHistoryEntry(h.player, h.potWin, h.specialWin, h.timestamp);
    });
  } catch (e) { /* silent */ }
}

// ─── Bet handler ──────────────────────────────────
betForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (!authToken) { showNotif('Veuillez vous connecter.', true); return; }

  betBtn.disabled = true;
  betBtn.querySelector('.btn-text').hidden   = true;
  betBtn.querySelector('.btn-spinner').hidden = false;

  try {
    const res  = await fetch('/api/bet', {
      method:  'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({})
    });
    const data = await res.json();

    if (!res.ok) { showNotif(data.error || 'Une erreur est survenue.', true); return; }

    currentUser.balance       = data.balance;
    userBalanceEl.textContent = fmt(data.balance);
    addHistoryEntry(currentUser.username, data.potWin, data.specialWin, new Date().toISOString());

    if (data.specialWin > 0) {
      showWin('🏆', 'JACKPOT !!!', `Félicitations ! Vous remportez 100€ ! Votre solde : ${fmt(data.balance)}`);
    } else if (data.potWin > 0) {
      showWin('🎉', 'Vous avez gagné !', `Bravo ! Vous remportez 9€ ! Votre solde : ${fmt(data.balance)}`);
    } else {
      showNotif(`Mise de 2€ enregistrée. Votre solde : ${fmt(data.balance)}`);
    }

  } catch (err) {
    showNotif('Erreur réseau. Veuillez réessayer.', true);
  } finally {
    betBtn.disabled = false;
    betBtn.querySelector('.btn-text').hidden   = false;
    betBtn.querySelector('.btn-spinner').hidden = true;
  }
});

// ─── Init ──────────────────────────────────────────
async function init() {
  if (authToken) {
    try {
      const res = await fetch('/api/me', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (res.ok) {
        const data = await res.json();
        showGame({ username: data.username, balance: data.balance });
        return;
      }
    } catch (e) {}
    localStorage.removeItem('token');
    authToken = null;
  }
  showAuth();
}

init();
