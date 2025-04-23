CREATE TABLE IF NOT EXISTS players (
  user_id TEXT PRIMARY KEY,
  rating INTEGER NOT NULL DEFAULT 1500,
  matches INTEGER NOT NULL DEFAULT 0,
  streak INTEGER NOT NULL DEFAULT 0,
  last_active DATETIME
);
CREATE TABLE IF NOT EXISTS duels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_a TEXT, user_b TEXT,
  winner TEXT, loser TEXT,
  is_draw BOOLEAN,
  team_size_a INT, team_size_b INT,
  margin INT DEFAULT 1,
  flagged BOOLEAN DEFAULT 0,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS monthly_top (
  month TEXT,
  user_id TEXT,
  rating INTEGER,
  PRIMARY KEY(month, user_id)
);
