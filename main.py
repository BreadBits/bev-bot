import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import json
import datetime
import random

DISCORD_TOKEN = os.environ('discordkey')

def load_data():
    try:
        with open("bev.json","r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_data(data):
    with open("bev.json","w") as f:
        json.dump(data, f, indent=4)

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
data = load_data()

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

    global data
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    data.setdefault("users", {})
    data.setdefault("servers",{})
    data["servers"].setdefault(guild_id,{"places":{}})

    user = data["users"].setdefault(user_id,{
        "profile":{
            "fav_bev": None,
            "fav_spot": None,
            "rank_name": "Newbie"
        },
        "stats": {"total_bevs": 0},
        "places": {},
        "entries": [],
    })

    server = data["servers"][guild_id]

    entry_number = len(user["entries"]) + 1
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    user["entries"].append({
        "id": entry_number,
        "name": bevname,
        "place": place,
        "rating": rating,
        "time": current_time
    })

    user["stats"]["total_bevs"] += 1
    total = user["stats"]["total_bevs"]
    user["places"][place] = user["places"].get(place, 0) + 1

    if place not in server["places"]:
        server["places"][place] = {
            "visits": 0,
            "regions": []
        }

    server["places"][place]["visits"] += 1

    user["profile"]["fav_bev"] = bevname
    user["profile"]["fav_spot"] = place

    save_data(data)

    await ctx.send(
        f"{ctx.author.mention} logged {bevname} from {place} ({rating}/20)\n"
        f"Total Drinks: {total}"
    )

@bot.command(aliases=['d','remove'])
async def delete(ctx,arg1):
    global data
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    if "users" not in data or user_id not in data["users"]:
        await ctx.send("No entries found.")
        return

    user = data["users"][user_id]
    entries = user["entries"]

    if not entries:
        await ctx.send("No entries found.")
        return

    removed = None

    if arg1.lower() == "last":
        removed = entries.pop()
        entry_id_used = removed["id"]
    else:
        try:
            entry_id = int(arg1)
        except:
            await ctx.send("Use `!d last` or `!d <id>`")
            return

        for i, e in enumerate(entries):
            if e["id"] == entry_id:
                removed = entries.pop(i)
                entry_id_used = entry_id
                break

    if not removed:
        await ctx.send("No entries found.")
        return



    for i, e in enumerate(entries, start=1):
        e["id"] = i

    user["stats"]["total_bevs"] -= 1

    place = removed["place"]

    if place in user["places"]:
        user["places"][place] -= 1

        if user["places"][place] <= 0:
            del user["places"][place]

    if guild_id in data["servers"]:
        server_places = data["servers"][guild_id]["places"]

        if place in server_places:
            server_places[place]["visits"] -= 1

            if server_places[place]["visits"] <= 0:
                del server_places[place]

    save_data(data)

    await ctx.send(
        f"Deleted entry #{entry_id_used} "
        f"{removed['name']} from {removed['place']}"
    )

#local leaderboard
@bot.command(aliases=['lb'])
async def leaderboard(ctx):
    global data


    if "users" not in data:
        await ctx.send("No data yet.")
        return

    scores = {}

    for user_id, user_data in data["users"].items():
        member = ctx.guild.get_member(int(user_id))

        if member is None:
            continue

        total_bevs = user_data.get("stats", {}).get("total_bevs", 0)
        scores[user_id] = total_bevs

    sorted_scores = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    lbmessage = "Local Bev Leaderboard (Total Bevs)\n"
    personal_rank = 0;
    personal_count = 0;

    for i, (user_id, count) in enumerate(sorted_scores[:10], start=1):
        member = ctx.guild.get_member(int(user_id))
        if member is None:
            continue

        if member == ctx.author:
            lbmessage += f"{i}. {member.name} — {count} :star:\n"
            personal_rank = i
            personal_count = count
        else:
            lbmessage += f"{i}. {member.name} — {count} \n"

    lbmessage += f"===================\n{personal_rank}. {ctx.author} — {personal_count} "

    lbembed = discord.Embed(color=5763719,title="Leaderboard",description=lbmessage)
    leaderb = await ctx.send(embed=lbembed)

@bot.command()
async def roll(ctx, region):
    global data
    guild_id = str(ctx.guild.id)

    if "servers" not in data or guild_id not in data["servers"]:
        await ctx.send("No places found.")
        return

    places = data["servers"][guild_id]["places"]

    matches = [
        name for name, info in places.items()
        if region in info["regions"]
    ]

    if not matches:
        await ctx.send("No places in this region.")
        return

    choice = random.choice(matches)

    await ctx.send(
        f" Rolling from **{region}**...\n"
        f" You got: **{choice}**"
    )

@bot.command()
async def rolladd(ctx, region, *places):
    global data

    region = region.lower()

    guild_id = str(ctx.guild.id)

    data.setdefault("servers", {})
    data["servers"].setdefault(guild_id, {"places": {}})

    server = data["servers"][guild_id]

    added = []
    for place in places:
        place = place.lower()

        if place not in server["places"]:
            server["places"][place] = {
                "visits": 0,
                "regions": []
            }

        if region not in server["places"][place]["regions"]:
            server["places"][place]["regions"].append(region)
            added.append(place)

    save_data(data)

    await ctx.send(
        f"➕ Added to **{region}**: {', '.join(added)}")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
