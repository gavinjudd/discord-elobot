import discord
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions, MissingPermissions
import sqlite3
import datetime
from elo import expected_score, new_rating

# ── CONFIG ────────────────────────────────────────────────────────────────
BOT_PREFIX             = '!'
COMMAND_PREFIX         = 'D'
BASE_RATING            = 1500
PROVISIONAL_MATCHES    = 10
K_STANDARD             = 20
K_PROVISIONAL          = 40
SOLO_VS_TEAM_BONUS     = 50
TEAM_LOSS_K            = 40
INACTIVITY_DECAY_WEEK  = 10    # Elo lost per week of inactivity
MONTHLY_RESET_HOUR     = 0     # midnight UTC
ROLE_THRESHOLDS        = {
    0:    'Novice',
    1600: 'Competitor',
    1800: 'Pro',
    2000: 'Master',
    2200: 'Grand Master'
}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=BOT_PREFIX+COMMAND_PREFIX, intents=intents)

# ── DATABASE SETUP ─────────────────────────────────────────────────────────
conn = sqlite3.connect('elo.db')
c    = conn.cursor()
c.executescript("""
CREATE TABLE IF NOT EXISTS players (
  user_id     TEXT PRIMARY KEY,
  rating      INTEGER NOT NULL DEFAULT 1500,
  matches     INTEGER NOT NULL DEFAULT 0,
  streak      INTEGER NOT NULL DEFAULT 0,
  last_active DATETIME
);
CREATE TABLE IF NOT EXISTS duels (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_a        TEXT, 
  user_b        TEXT,
  winner        TEXT, 
  loser         TEXT,
  is_draw       BOOLEAN,
  team_size_a   INT, 
  team_size_b   INT,
  margin        INT DEFAULT 1,
  flagged       BOOLEAN DEFAULT 0,
  timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS monthly_top (
  month     TEXT,
  user_id   TEXT,
  rating    INTEGER,
  PRIMARY KEY(month, user_id)
);
"""
)
conn.commit()

# ── ELO UTILITIES ───────────────────────────────────────────────────────────
def decay_inactivity(user_id):
    c.execute("SELECT last_active, rating FROM players WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row or not row[0]:
        return
    last = datetime.datetime.fromisoformat(row[0])
    weeks = (datetime.datetime.utcnow() - last).days // 7
    if weeks > 0:
        new_r = max(100, row[1] - weeks * INACTIVITY_DECAY_WEEK)
        c.execute("UPDATE players SET rating=?, last_active=CURRENT_TIMESTAMP WHERE user_id=?",
                  (new_r, user_id))
        conn.commit()

def get_player(user_id):
    c.execute("SELECT rating, matches, streak FROM players WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row:
        decay_inactivity(user_id)
        return row
    c.execute("INSERT INTO players(user_id, last_active) VALUES(?, CURRENT_TIMESTAMP)", (user_id,))
    conn.commit()
    return (BASE_RATING, 0, 0)

def set_player(user_id, rating, matches, streak):
    c.execute("""
      UPDATE players
      SET rating=?, matches=?, streak=?, last_active=CURRENT_TIMESTAMP
      WHERE user_id=?
    """, (rating, matches, streak, user_id))
    conn.commit()

async def assign_roles(member, rating):
    for role in list(member.roles):
        if role.name in ROLE_THRESHOLDS.values():
            await member.remove_roles(role)
    for thresh, role_name in sorted(ROLE_THRESHOLDS.items()):
        if rating >= thresh:
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role:
                await member.add_roles(role)

# ── DUEL COMMAND ───────────────────────────────────────────────────────────
@bot.command(name='Duel')
async def duel(ctx, opponents: commands.Greedy[discord.Member], result: str, margin: int = 1):
    challenger_ids = [ctx.author.id]
    opponent_ids   = [m.id for m in opponents]
    is_solo_vs_team = (len(challenger_ids) == 1 and len(opponent_ids) > 1)

    uid_str = str(ctx.author.id)
    opp_str = str(opponent_ids[0])
    r_u, m_u, s_u = get_player(uid_str)
    r_o, m_o, s_o = get_player(opp_str)

    c.execute("""
      SELECT timestamp FROM duels
      WHERE ((user_a=? AND user_b=?) OR (user_a=? AND user_b=?))
      ORDER BY id DESC LIMIT 1
    """, (ctx.author.id, opponent_ids[0], opponent_ids[0], ctx.author.id))
    last = c.fetchone()
    if last and (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last[0])).seconds < 3600:
        return await ctx.send("Rematch too soon—no Elo change.")

    if result.lower() == 'win':    su, so = 1, 0
    elif result.lower() == 'lose': su, so = 0, 1
    else:                           su, so = 0.5, 0.5

    eu = expected_score(r_u, r_o)
    eo = expected_score(r_o, r_u)

    ku = K_PROVISIONAL if m_u < PROVISIONAL_MATCHES else K_STANDARD
    ko = K_PROVISIONAL if m_o < PROVISIONAL_MATCHES else K_STANDARD

    if is_solo_vs_team:
        if su == 1:
            ku += SOLO_VS_TEAM_BONUS
        elif so == 1:
            ko = TEAM_LOSS_K

    if su == 1:
        s_u = s_u + 1 if s_u >= 0 else 1
        s_o = 0
    elif so == 1:
        s_o = s_o + 1 if s_o >= 0 else 1
        s_u = 0
    else:
        s_u = s_o = 0

    if su == 1 and r_u < r_o: ku += 10
    if so == 1 and r_o < r_u: ko += 10

    ku += margin
    ko += margin

    new_u = round(r_u + ku * (su - eu))
    new_o = round(r_o + ko * (so - eo))

    set_player(uid_str, new_u, m_u + 1, s_u)
    set_player(opp_str, new_o, m_o + 1, s_o)

    c.execute("""
      INSERT INTO duels
        (user_a, user_b, winner, loser, is_draw, team_size_a, team_size_b, margin)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
      ctx.author.id, opponent_ids[0],
      ctx.author.id if su == 1 else opponent_ids[0],
      opponent_ids[0] if su == 1 else ctx.author.id,
      su == so,
      len(challenger_ids), len(opponent_ids), margin
    ))
    conn.commit()

    await assign_roles(ctx.author, new_u)
    opp_member = ctx.guild.get_member(opponent_ids[0])
    if opp_member:
        await assign_roles(opp_member, new_o)

    await ctx.send(f"{ctx.author.display_name}: {r_u}→{new_u} vs {opp_member.display_name}: {r_o}→{new_o}")

# ── USER COMMANDS ───────────────────────────────────────────────────────────
@bot.command(name='Elo')
async def elo(ctx, member: discord.Member = None):
    member = member or ctx.author
    decay_inactivity(str(member.id))
    rating, _, _ = get_player(str(member.id))
    await ctx.send(f"{member.display_name}’s Elo: {rating}")

@bot.command(name='Leaderboard')
async def leaderboard(ctx, top_n: int = 10):
    c.execute("SELECT user_id, rating FROM players ORDER BY rating DESC LIMIT ?", (top_n,))
    rows = c.fetchall()
    msg = "**Dueling Leaderboard**\n"
    for i, (uid, rt) in enumerate(rows, start=1):
        user = await bot.fetch_user(uid)
        msg += f"{i}. {user.display_name}: {rt}\n"
    await ctx.send(msg)

@bot.command(name='FlagDuel')
async def flagduel(ctx, duel_id: int):
    c.execute("UPDATE duels SET flagged=1 WHERE id=?", (duel_id,))
    conn.commit()
    await ctx.send(f"Duel #{duel_id} flagged for review.")

@bot.command(name='History')
async def history(ctx, member: discord.Member = None):
    member = member or ctx.author
    c.execute("""
      SELECT id, winner, loser, is_draw, timestamp
      FROM duels
      WHERE user_a=? OR user_b=?
      ORDER BY timestamp DESC LIMIT 10
    """, (str(member.id), str(member.id)))
    rows = c.fetchall()
    msg = f"Last 10 duels for {member.display_name}:\n"
    for r in rows:
        outcome = "Draw" if r[3] else ("Win" if r[1] == str(member.id) else "Loss")
        msg += f"#{r[0]} {outcome} at {r[4]}\n"
    await ctx.send(msg)

# ── ADMIN COMMANDS ────────────────────────────────────────────────────────────
@bot.command(name='SetElo')
@has_permissions(administrator=True)
async def set_elo(ctx, member: discord.Member, rating: int):
    """Set a user’s Elo to exactly <rating>."""
    old, m, s = get_player(str(member.id))
    set_player(str(member.id), rating, m, s)
    await ctx.send(f"{member.mention}’s Elo set to {rating}.")

@bot.command(name='AddElo')
@has_permissions(administrator=True)
async def add_elo(ctx, member: discord.Member, delta: int):
    """Add (or subtract) Elo points."""
    r, m, s = get_player(str(member.id))
    new_r = max(0, r + delta)
    set_player(str(member.id), new_r, m, s)
    await ctx.send(f"{member.mention}’s Elo adjusted by {delta} → {new_r}.")

@bot.command(name='ResetElo')
@has_permissions(administrator=True)
async def reset_elo(ctx, member: discord.Member):
    """Reset a user’s Elo to base rating."""
    set_player(str(member.id), BASE_RATING, 0, 0)
    await ctx.send(f"{member.mention}’s Elo reset to {BASE_RATING}.")

@bot.command(name='ClearFlag')
@has_permissions(administrator=True)
async def clear_flag(ctx, duel_id: int):
    """Clear flagged status on a duel."""
    c.execute("UPDATE duels SET flagged=0 WHERE id=?", (duel_id,))
    conn.commit()
    await ctx.send(f"Duel #{duel_id} un-flagged.")

@bot.command(name='ForceDuel')
@has_permissions(administrator=True)
async def force_duel(ctx, winner: discord.Member, loser: discord.Member, result: str, margin: int = 1):
    """Manually log a duel between two users."""
    res = result.lower()
    if res == 'win':    su, so = 1, 0
    elif res == 'lose': su, so = 0, 1
    else:               su, so = 0.5, 0.5

    w_id, l_id = str(winner.id), str(loser.id)
    r_w, m_w, s_w = get_player(w_id)
    r_l, m_l, s_l = get_player(l_id)

    e_w = expected_score(r_w, r_l)
    e_l = expected_score(r_l, r_w)

    k_w = K_PROVISIONAL if m_w < PROVISIONAL_MATCHES else K_STANDARD
    k_l = K_PROVISIONAL if m_l < PROVISIONAL_MATCHES else K_STANDARD

    if su == 1 and r_w < r_l: k_w += 10
    if so == 1 and r_l < r_w: k_l += 10

    k_w += margin
    k_l += margin

    new_w = round(r_w + k_w * (su - e_w))
    new_l = round(r_l + k_l * (so - e_l))

    set_player(w_id, new_w, m_w + 1, s_w + (1 if su==1 else 0))
    set_player(l_id, new_l, m_l + 1, s_l + (1 if so==1 else 0))

    c.execute("""
      INSERT INTO duels
        (user_a, user_b, winner, loser, is_draw, team_size_a, team_size_b, margin)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
      winner.id, loser.id,
      winner.id if su==1 else loser.id,
      loser.id if su==1 else winner.id,
      su==so,
      1, 1, margin
    ))
    conn.commit()

    await assign_roles(winner, new_w)
    await assign_roles(loser, new_l)

    await ctx.send(
      f"{winner.display_name}: {r_w}→{new_w} vs {loser.display_name}: {r_l}→{new_l}"
    )

@bot.command(name='MonthlyReset')
@has_permissions(administrator=True)
async def monthly_reset_now(ctx):
    """Trigger monthly reset immediately."""
    await ctx.send("Running monthly reset…")
    await monthly_reset()
    await ctx.send("Monthly reset complete.")

@set_elo.error
@add_elo.error
@reset_elo.error
@clear_flag.error
@force_duel.error
@monthly_reset_now.error
async def admin_cmd_error(ctx, error):
    if isinstance(error, MissingPermissions):
        await ctx.send("Administrator permission required for that command.")

# ── MONTHLY RESET ─────────────────────────────────────────────────────────────
@tasks.loop(hours=24)
async def monthly_reset():
    now = datetime.datetime.utcnow()
    if now.day == 1 and now.hour == MONTHLY_RESET_HOUR:
        month = now.strftime("%Y-%m")
        c.execute(
          "INSERT INTO monthly_top SELECT ?, user_id, rating FROM players ORDER BY rating DESC LIMIT 3",
          (month,)
        )
        c.execute("UPDATE players SET rating = ROUND(rating * 0.8)")
        conn.commit()

@bot.event
async def on_ready():
    monthly_reset.start()
    print(f"Logged in as {bot.user}")

# ── RUN THE BOT ─────────────────────────────────────────────────────────────
import os
bot.run(os.getenv("DISCORD_TOKEN"))