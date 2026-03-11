const express = require('express');
const path    = require('path');
const crypto  = require('crypto');
const { MongoClient } = require('mongodb');

const app  = express();
const PORT = process.env.PORT || 3000;

const MONGO_URI = process.env.MONGODB_URI;
let db;

function hashPassword(password) {
  return crypto.createHash('sha256').update(password + 'cagnotte_secret_salt').digest('hex');
}

function generateToken() {
  return crypto.randomBytes(32).toString('hex');
}

async function connectDB() {
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  db = client.db('cagnotte');
  console.log('Connecté à MongoDB Atlas');

  const col = db.collection('gamestate');
  await col.updateOne(
    { _id: 'main' },
    { $setOnInsert: { pot: 0, specialPot: 0, history: [] } },
    { upsert: true }
  );
}

async function getState() {
  return db.collection('gamestate').findOne({ _id: 'main' });
}

async function setState(pot, specialPot, historyEntry) {
  await db.collection('gamestate').updateOne(
    { _id: 'main' },
    {
      $set:  { pot, specialPot },
      $push: { history: { $each: [historyEntry], $slice: -100 } }
    }
  );
}

async function getUserByToken(token) {
  if (!token) return null;
  return db.collection('users').findOne({ token });
}

app.use(express.json());
app.use(express.static(path.join(__dirname, 'docs')));

// ─── POST /api/register ────────────────────────────
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password || username.trim() === '') {
    return res.status(400).json({ error: 'Nom d\'utilisateur et mot de passe requis.' });
  }
  if (username.trim().length < 3) {
    return res.status(400).json({ error: 'Nom d\'utilisateur trop court (min 3 caractères).' });
  }
  if (password.length < 4) {
    return res.status(400).json({ error: 'Mot de passe trop court (min 4 caractères).' });
  }

  try {
    const existing = await db.collection('users').findOne({ username: username.trim().toLowerCase() });
    if (existing) {
      return res.status(409).json({ error: 'Ce nom d\'utilisateur est déjà pris.' });
    }

    const token = generateToken();
    await db.collection('users').insertOne({
      username:    username.trim().toLowerCase(),
      displayName: username.trim(),
      password:    hashPassword(password),
      balance:     20,
      token,
      createdAt:   new Date().toISOString()
    });

    res.json({ token, username: username.trim(), balance: 20 });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

// ─── POST /api/login ───────────────────────────────
app.post('/api/login', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Nom d\'utilisateur et mot de passe requis.' });
  }

  try {
    const user = await db.collection('users').findOne({ username: username.trim().toLowerCase() });
    if (!user || user.password !== hashPassword(password)) {
      return res.status(401).json({ error: 'Identifiants incorrects.' });
    }

    const token = generateToken();
    await db.collection('users').updateOne({ _id: user._id }, { $set: { token } });

    res.json({ token, username: user.displayName, balance: user.balance });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

// ─── GET /api/me ───────────────────────────────────
app.get('/api/me', async (req, res) => {
  const token = (req.headers.authorization || '').replace('Bearer ', '');
  const user  = await getUserByToken(token);
  if (!user) return res.status(401).json({ error: 'Non authentifié.' });
  res.json({ username: user.displayName, balance: user.balance });
});

// ─── GET /api/status (historique uniquement) ───────
app.get('/api/status', async (req, res) => {
  try {
    const state = await getState();
    res.json({ history: (state.history || []).slice(-10) });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

// ─── POST /api/bet ─────────────────────────────────
app.post('/api/bet', async (req, res) => {
  const token = (req.headers.authorization || '').replace('Bearer ', '');
  const user  = await getUserByToken(token);
  if (!user) return res.status(401).json({ error: 'Veuillez vous connecter pour miser.' });

  if (user.balance < 2) {
    return res.status(400).json({ error: 'Solde insuffisant pour miser 2€.' });
  }

  try {
    const state = await getState();
    let pot        = state.pot + 2;
    let specialPot = state.specialPot;
    let potWin     = 0;
    let specialWin = 0;

    if (pot >= 10) {
      potWin      = 9;
      pot        -= 10;
      specialPot += 1;

      if (specialPot >= 100) {
        specialWin  = 100;
        specialPot -= 100;
      }
    }

    await setState(pot, specialPot, {
      timestamp:  new Date().toISOString(),
      player:     user.displayName,
      potWin,
      specialWin
    });

    const newBalance = Math.round((user.balance - 2 + potWin + specialWin) * 100) / 100;
    await db.collection('users').updateOne({ _id: user._id }, { $set: { balance: newBalance } });

    res.json({ potWin, specialWin, balance: newBalance });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

// ─── POST /api/reset (admin) ───────────────────────
app.post('/api/reset', async (req, res) => {
  try {
    await db.collection('gamestate').updateOne(
      { _id: 'main' },
      { $set: { pot: 0, specialPot: 0, history: [] } }
    );
    res.json({ message: 'Remise à zéro effectuée.' });
  } catch (err) {
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

connectDB()
  .then(() => {
    app.listen(PORT, () => console.log(`Serveur démarré sur http://localhost:${PORT}`));
  })
  .catch(err => {
    console.error('Impossible de se connecter à MongoDB :', err.message);
    process.exit(1);
  });
