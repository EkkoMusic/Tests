const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = 3000;
const DATA_FILE = path.join(__dirname, 'data.json');

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function loadData() {
  if (!fs.existsSync(DATA_FILE)) {
    const initial = { pot: 0, specialPot: 0, history: [] };
    fs.writeFileSync(DATA_FILE, JSON.stringify(initial, null, 2));
    return initial;
  }
  return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
}

function saveData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// GET current state
app.get('/api/status', (req, res) => {
  const data = loadData();
  res.json({
    pot: data.pot,
    specialPot: data.specialPot,
    history: data.history.slice(-10)
  });
});

// POST place a bet of 2€
app.post('/api/bet', (req, res) => {
  const { name } = req.body;
  if (!name || name.trim() === '') {
    return res.status(400).json({ error: 'Veuillez entrer votre prénom.' });
  }

  const data = loadData();
  const playerName = name.trim();
  const events = [];

  // Add 2€ to the pot
  data.pot += 2;
  events.push({ type: 'bet', message: `${playerName} a misé 2€. Cagnotte : ${data.pot.toFixed(2)}€` });

  let potWin = 0;
  let specialWin = 0;

  // Check if pot reaches 10€
  if (data.pot >= 10) {
    potWin = 9;
    data.pot -= 10;
    data.specialPot += 1;
    events.push({
      type: 'pot_win',
      message: `La cagnotte a atteint 10€ ! ${playerName} remporte 9€ ! 1€ ajouté à la cagnotte spéciale.`
    });

    // Check if special pot reaches 100€
    if (data.specialPot >= 100) {
      specialWin = 100;
      data.specialPot -= 100;
      events.push({
        type: 'special_win',
        message: `JACKPOT ! La cagnotte spéciale a atteint 100€ ! ${playerName} remporte 100€ !!!`
      });
    }
  }

  // Add to history
  const historyEntry = {
    timestamp: new Date().toISOString(),
    player: playerName,
    potWin,
    specialWin,
    potAfter: data.pot,
    specialPotAfter: data.specialPot
  };
  data.history.push(historyEntry);
  if (data.history.length > 100) data.history = data.history.slice(-100);

  saveData(data);

  res.json({
    pot: data.pot,
    specialPot: data.specialPot,
    events,
    potWin,
    specialWin
  });
});

// Reset (admin only - remove in production)
app.post('/api/reset', (req, res) => {
  const fresh = { pot: 0, specialPot: 0, history: [] };
  saveData(fresh);
  res.json({ message: 'Remise à zéro effectuée.', ...fresh });
});

app.listen(PORT, () => {
  console.log(`Serveur démarré sur http://localhost:${PORT}`);
});
