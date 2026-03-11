const express = require('express');
const path    = require('path');
const { MongoClient } = require('mongodb');

const app  = express();
const PORT = process.env.PORT || 3000;

// MongoDB connection (set MONGODB_URI in environment variables)
const MONGO_URI = process.env.MONGODB_URI;
let db;

async function connectDB() {
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  db = client.db('cagnotte');
  console.log('Connecté à MongoDB Atlas');

  // Initialize state document if it doesn't exist
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
  const col = db.collection('gamestate');
  await col.updateOne(
    { _id: 'main' },
    {
      $set:  { pot, specialPot },
      $push: { history: { $each: [historyEntry], $slice: -100 } }
    }
  );
}

app.use(express.json());
app.use(express.static(path.join(__dirname, 'docs')));

// GET current state
app.get('/api/status', async (req, res) => {
  try {
    const state = await getState();
    res.json({
      pot:        state.pot,
      specialPot: state.specialPot,
      history:    (state.history || []).slice(-10)
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

// POST place a bet of 2€
app.post('/api/bet', async (req, res) => {
  const { name } = req.body;
  if (!name || name.trim() === '') {
    return res.status(400).json({ error: 'Veuillez entrer votre prénom.' });
  }

  try {
    const state      = await getState();
    const playerName = name.trim();

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

    const historyEntry = {
      timestamp:  new Date().toISOString(),
      player:     playerName,
      potWin,
      specialWin
    };

    await setState(pot, specialPot, historyEntry);

    res.json({ pot, specialPot, potWin, specialWin });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Erreur serveur.' });
  }
});

// POST reset (admin)
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

// Start server after DB connection
connectDB()
  .then(() => {
    app.listen(PORT, () => console.log(`Serveur démarré sur http://localhost:${PORT}`));
  })
  .catch(err => {
    console.error('Impossible de se connecter à MongoDB :', err.message);
    process.exit(1);
  });
