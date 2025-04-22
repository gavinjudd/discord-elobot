# RequiemEloBot

RequiemEloBot is a self-hosted Discord bot written in Python 3.  
It manages an advanced Elo system for 1 v 1 and team duels, assigns rank roles
(Novice → Grand Master), logs matches to SQLite, applies inactivity decay,
and gives admins full control via force-duel and Elo-maintenance commands.

## Features
- Enhanced Elo: provisional K-factor, upset & margin bonuses, solo-vs-team logic
- Automatic role tiers (Novice, Competitor, Pro, Master, Grand Master)
- Monthly leaderboard snapshot and partial rating reset
- Rematch-cooldown + anti-abuse protections
- Admin commands: set/add/reset Elo, force-duel entry, clear flags, manual reset
- Simple SQLite backend—no external DB required

## Quick Start

```bash
# clone and enter
git clone https://github.com/<your-org>/RequiemEloBot.git
cd RequiemEloBot

# create venv
python3 -m venv venv
source venv/bin/activate

# install deps
pip install -r requirements.txt

# initialise DB
sqlite3 elo.db < schema.sql   # or let bot auto-create

# add your Discord token
export DISCORD_TOKEN="PASTE_TOKEN_HERE"

# run
python3 bot.py
