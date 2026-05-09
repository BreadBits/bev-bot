import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import json
import datetime
import random


import sqlite3

conn = sqlite3.connect("bev.db")
cursor = conn.cursor()

print("DB CREATED AT:", os.path.abspath("bev.db"))

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    fav_bev TEXT,
    fav_spot TEXT,
    rank_name TEXT,
    total_bevs INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    guild_id TEXT,
    name TEXT,
    place TEXT,
    rating INTEGER,
    time TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS server_places (
    guild_id TEXT,
    place TEXT,
    visits INTEGER,
    UNIQUE(guild_id, place)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS place_regions (
    guild_id TEXT,
    place TEXT,
    region TEXT,
    UNIQUE(guild_id, place, region)
)
""")

conn.commit()

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

REGIONS = {
    "socal": [
        "smokingtiger",
        "7leaves",
        "omomo",
        "sunright",
        "bobatime",
    ],

    "norcal": [
        "philz",
        "blue bottle",
        "tpumps"
    ]
}

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if "beverage" in message.content.lower():
        await message.channel.send(f"{message.author.mention} - hmm i love bevs")

    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f"Error: {error}")
    print("ERROR:", error)

@bot.command()
async def test(ctx,arg1,arg2):
    await ctx.send(f"Hello {ctx.author.mention}, you logged {arg1} from {arg2}")

@bot.command()
async def bev(ctx,*args):
    if not args:
        await ctx.send("Please enter some arguments")
        return

    if len(args) < 2:
        await ctx.send("Usage: !bev drink place rating (e.g. 8/10)")
        return

    ratingraw = args[-1]

    try:
        rating = int(ratingraw.split("/")[0])#last argument
    except (ValueError, IndexError):
        await ctx.send("Please enter a valid rating")
        return

    place = args[-2].lower()
    bevname = " ".join(args[:-2])

    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO users (user_id, fav_bev, fav_spot, rank_name, total_bevs)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(user_id) DO NOTHING
    """, (user_id, None, None, "Newbie"))

    cursor.execute("""
        INSERT INTO entries (user_id, guild_id, name, place, rating, time)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, guild_id, bevname, place, rating, current_time))

    cursor.execute("""
        UPDATE users
        SET total_bevs = COALESCE(total_bevs, 0) + 1,
            fav_bev = ?,
            fav_spot = ?
        WHERE user_id = ?
    """, (bevname, place, user_id))

    cursor.execute("""
        INSERT INTO server_places (guild_id, place, visits)
        VALUES (?, ?, 1)
        ON CONFLICT(guild_id, place)
        DO UPDATE SET visits = visits + 1
    """, (guild_id, place))

    conn.commit()

    cursor.execute("""
        SELECT total_bevs FROM users WHERE user_id = ?
    """, (user_id,))

    total = cursor.fetchone()[0]

    await ctx.send(
        f"{ctx.author.mention} logged {bevname} from {place} ({rating}/20)\n"
        f"Total Drinks: {total}"
    )

@bot.command(aliases=['d','remove'])
async def delete(ctx, arg1):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    cursor.execute("""
        SELECT id, name, place FROM entries
        WHERE user_id = ? AND guild_id = ?
        ORDER BY id DESC
    """, (user_id, guild_id))

    entries = cursor.fetchall()

    if not entries:
        await ctx.send("No entries found.")
        return

    if arg1.lower() == "last":
        entry = entries[0]
    else:
        try:
            entry_id = int(arg1)
        except:
            await ctx.send("Use `!d last` or `!d <id>`")
            return

        entry = None
        for e in entries:
            if e[0] == entry_id:
                entry = e
                break

        if not entry:
            await ctx.send("No entry found.")
            return

    entry_id, name, place = entry

    cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    cursor.execute("""
        UPDATE users
        SET total_bevs = MAX(total_bevs - 1, 0)
        WHERE user_id = ?
    """, (user_id,))

    cursor.execute("""
        UPDATE server_places
        SET visits = MAX(visits - 1, 0)
        WHERE guild_id = ? AND place = ?
    """, (guild_id, place))

    conn.commit()

    await ctx.send(f"Deleted entry #{entry_id} {name} from {place}")

@bot.command(aliases=['lb'])
async def leaderboard(ctx):

    cursor.execute("""
        SELECT user_id, total_bevs
        FROM users
        ORDER BY total_bevs DESC
        LIMIT 10
    """)

    rows = cursor.fetchall()

    if not rows:
        await ctx.send("No data yet.")
        return

    lbmessage = "Local Bev Leaderboard (Total Bevs)\n"

    for i, (user_id, count) in enumerate(rows, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.name if member else "Unknown"

        if member == ctx.author:
            lbmessage += f"{i}. {member.name} — {count} :star:\n"
            personal_rank = i
            personal_count = count
        else:
            lbmessage += f"{i}. {member.name} — {count} \n"

    lbmessage += f"===================\n{personal_rank}. {ctx.author} — {personal_count} "

    lbembed = discord.Embed(color=5763719, title="Leaderboard", description=lbmessage)
    leaderb = await ctx.send(embed=lbembed)

@bot.command()
async def roll(ctx, region):
    guild_id = str(ctx.guild.id)
    region = region.lower()

    cursor.execute("""
        SELECT place
        FROM place_regions
        WHERE guild_id = ? AND region = ?
    """, (guild_id, region))

    results = cursor.fetchall()

    if not results:
        await ctx.send("No places in this region.")
        return

    choice = random.choice([r[0] for r in results])

    await ctx.send(
        f"Rolling from **{region}**...\n"
        f"You got: **{choice}**"
    )

@bot.command()
async def rolladd(ctx, region, *places):
    guild_id = str(ctx.guild.id)
    region = region.lower()

    if not places:
        await ctx.send("Provide at least one place.")
        return

    added = []

    for place in places:
        place = place.lower()

        # insert region mapping (ignore duplicates)
        cursor.execute("""
            INSERT INTO place_regions (guild_id, place, region)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, place, region) DO NOTHING
        """, (guild_id, place, region))

        added.append(place)

    conn.commit()

    await ctx.send(f"Added to **{region}**: {', '.join(added)}")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
