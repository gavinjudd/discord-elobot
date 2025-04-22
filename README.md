# RequiemEloBot

Advanced Discord bot that powers an Elo-based dueling system with  
auto-assigned rank roles, monthly leaderboard resets, and administrator tools.

---

## Features

* Enhanced Elo engine  
  * Provisional K-factor (40 for first 10 duels)  
  * Upset and margin bonuses, solo-vs-team logic  
  * 1-hour rematch cooldown and inactivity decay (-10 Elo per inactive week)
* Automatic rating roles  
  * Novice, Competitor, Pro, Master, Grand Master
* Duel formats  
  * 1 v 1, 2 v 2, 3 v 3, 4 v 4, solo-vs-team
* Monthly leaderboard snapshot  
  * Top-3 rewards, 20 % soft Elo reset for the new season
* SQLite backend – no external database required
* Admin toolkit – force-duel, set/add/reset Elo, manual monthly reset
* Anti-abuse protections – rematch window, proof requirement, collusion rules

---

## Quick Start

```bash
git clone https://github.com/<your-user>/RequiemEloBot.git
cd RequiemEloBot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # discord.py, aiohttp

# optional – create DB from schema
sqlite3 elo.db < schema.sql

export DISCORD_TOKEN="YOUR_TOKEN_HERE"
python3 bot.py

```
Invite URL = https://discord.com/oauth2/authorize?client_id=1363272857450315957
Be sure to enable Server Members Intent and Message Content Intent in the Developer Portal.

## Configuration Notes
* DISCORD_TOKEN - environment viariable or load from .env
* BOT_PREFIX / COMMAND_PREFIX - adjust in bot.py (defaults to !D)
* ROLE_THRESHOLDS - edit in bot.py if you want different elo bands
* elo.db - shipoped via SQLite; keep it in the repo root or set a full path

## User Commands
* !DDuel @Opponent (Challenger) win|lose|draw [margin] - record duel & adjust ratings
* !DElo [@Member] - show Elo (default = you)
* !DLeaderboard [N] - top N duelists
* !DHistory [@Member] - last 10 duels
* !DFlagDuel <duel_id> - flag a duel for staff review

# Administrator Only Commands
* !DSetElo @Member <rating> – force-set rating
* !DAddElo @Member <delta> – add or subtract Elo
* !DResetElo @Member – reset to base (1500)
* !DForceDuel @Winner @Loser win|lose|draw [margin] – log a match manually
* !DClearFlag <duel_id> – remove flag status
* !DMonthlyReset – run monthly snapshot + soft reset instantly

## Anti-Abuse Rules
1. All duels must use bot commands and include unedited video proof.
2. Match-fixing, Elo gifting, or alt-account boosting is banned.
3. Respect the 1-hour rematch cooldown.
4. Staff decisions on flagged duels and Elo adjustments are final.
5. Penalties range from Elo reset to permanent ban.

## Repository Structure
```bash
RequiemEloBot/
│  bot.py           # main bot source
│  elo.py           # Elo helper functions
│  schema.sql       # SQLite schema (players, duels, monthly_top)
│  requirements.txt # discord.py >= 2.3
│  elo.db           # generated database (add to .gitignore)
└─ .env             # optional token storage (never commit)
```

## Contributing
1. Fork, create a feature branch (git checkout -b feature/foo)
2. Run black. and isort . before committing
3. Opoen a pull request; CI must pass lint and startup tests

## License
Released under the MIT License – see LICENSE for details.
