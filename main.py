import discord
from discord.commands import Option, OptionChoice
from datetime import datetime
import aiohttp
import dotenv
import os
import sys
import json

API_URL = "https://api.fubi.ca"
dotenv.load_dotenv()
secret = os.getenv("DISCORD_SECRET")
server_id = os.getenv("SERVER_ID")
session = None
client = discord.Bot(debug_guilds=[server_id])

if not os.path.exists("db.json"):
        with open("db.json", "w") as f:
            json.dump({"players": {}}, f)

grades = {
    "X": "<:ss:1015053217157095595>",
    "XH": "<:ssh:1015053219262627950>",
    "S": "<:s_:1015053213965221999>",
    "SH": "<:sh:1015053215991091321>",
    "A": "<:a_:1015053206205767701>",
    "B": "<:b_:1015053207745081444>",
    "C": "<:c_:1015053209112420393>",
    "D": "<:d_:1015053210630766603>",
    "F": "<:f_:1015053211981328515>",
}

async def from_iso_with_offset_to_unix(_time: str) -> float:
    """Transform an ISO date to unix timestamp.

    Args:
        _time (str): the ISO date.

    Returns:
        float: unix timestamp
    """
    iso = datetime.fromisoformat(_time).timestamp()
    return int(iso - 10800)

def num_to_mod(mod_sum_integer:int)->list[str]:
    mod_list:list[str] = []
    mod_sum_integer = int(mod_sum_integer)

    mods = [
        'NF','EZ','TD','HD','HR','SD','DT','RX','HT','NC','FL','Auto',
        'SO','AP','PF','4K','5K','6K','7K','8K','FI','RDM','CI','TG',
        '9K','10K','1K','3K','2K','V2','MI'
    ]
    
    current_number = int(mod_sum_integer)

    for mod_index in range(len(mods)-1, -1, -1): # Stole from owo-bot lmao https://github.com/AznStevy/owo-bot/blob/f7651f3cb7d67ba4d93e8ffa96d7a1d3120b2bd8/cogs/osu/osu_utils/utils.py#L270
        mod = mods[mod_index]

        if mod == "NC":
            if current_number >= 576:
                current_number -= 576
                mod_list.append(mod)
                continue
        
        elif mod == "PF":
            if current_number >= 16416:
                current_number -= 16416
                mod_list.append(mod)

        if current_number >= 2**mod_index:
            current_number -= 2**mod_index
            mod_list.append(mod)
        

    return mod_list

async def create_embed_scores_json(response_json: dict, embed: discord.Embed):
    i = 0
    for score in response_json["scores"]:
        if i == 0:
            embed.set_thumbnail(url=f"https://b.ppy.sh/thumb/{score['beatmap']['set_id']}l.jpg")
            i = 1
        
        diff = f"{int(score['beatmap']['diff']*100)/100}🌟"
        mods = ""

        for mod in num_to_mod(score['mods']):
            mods += mod
        if mods != "":
            mods = f" +{mods}"

        embed.add_field(
            name=f"{score['beatmap']['artist']} - {score['beatmap']['title']} [{score['beatmap']['version']}]{mods}",
            value=f"{grades.get(score['grade'])} - **{score['pp']}pp** - {score['score']} - {score['max_combo']}x/{score['beatmap']['max_combo']}x\n**{diff}** - {int(score['acc']*100)/100}% - {score['n300']}/{score['n100']}/{score['n50']}/{score['nmiss']} - <t:{await from_iso_with_offset_to_unix(score['play_time'])}:R>",
            inline=False
        )
        
    return embed
    

@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))
    print(
        "\nInvite the bot: https://discord.com/api/oauth2/authorize?client_id="
        "{0.user.id}&permissions=8&scope=bot%20applications.commands".format(client)
    )
    global session
    session = aiohttp.ClientSession()

@client.slash_command()
async def recent(ctx: discord.ApplicationContext,
             username: Option(str, max_length=15, required=False),
             modo: Option(int, choices=[
                 OptionChoice("osu!standard", value=0),
                 OptionChoice("Taiko", value=1),
                 OptionChoice("Catch the Beat!", value=2),
                 OptionChoice("osu!mania", value=3),
                 OptionChoice("osu!standard Relax", value=4),
                 OptionChoice("Taiko Relax", value=5),
                 OptionChoice("Catch the Beat! Relax", value=6),
                 OptionChoice("osu!standard Autopiloy", value=8),
             ]) = 0,
             quantos: Option(int, min_value=1, max_value=5, default=1) = 1,
             mods: Option(str, min_length=2) = "",
             passes: Option(int, choices=[
                 OptionChoice("Sim", value=0),
                 OptionChoice("Não", value=1),
             ]) = 0
             ):
    await rs(ctx, username, modo, quantos, mods, passes)

@client.slash_command()
async def rs(ctx: discord.ApplicationContext,
             username: Option(str, max_length=15, required=False),
             modo: Option(int, choices=[
                 OptionChoice("osu!standard", value=0),
                 OptionChoice("Taiko", value=1),
                 OptionChoice("Catch the Beat!", value=2),
                 OptionChoice("osu!mania", value=3),
                 OptionChoice("osu!standard Relax", value=4),
                 OptionChoice("Taiko Relax", value=5),
                 OptionChoice("Catch the Beat! Relax", value=6),
                 OptionChoice("osu!standard Autopiloy", value=8),
             ]) = 0,
             quantos: Option(int, min_value=1, max_value=5, default=1) = 1,
             mods: Option(str, min_length=2) = "",
             passes: Option(int, choices=[
                 OptionChoice("Sim", value=0),
                 OptionChoice("Não", value=1),
             ]) = 1
             ):
    await ctx.defer()
    
    if not username:
        with open("db.json", "r") as f:
            contents = json.load(f)
            
        username = contents["players"].get(str(ctx.author.id))
        if username is None:
            await ctx.send_followup("Conecte sua conta para usar o comando sem username. `/link`.")
            return
    
    params = {
        "scope": "recent",
        "name": username,
        "mode": modo,
        "limit": quantos,
        "include_failed": passes
    }
    if mods:
        params["mods"] = mods
        
    response = await session.request(method="GET", url=API_URL+"/get_player_scores", params=params)
    response_json = await response.json()
    if response_json['status'] != "success":
        await ctx.send_followup(content=response_json["status"])
        return
    
    embed = discord.Embed(title=f"Jogadas recentes para {response_json['player']['name']}", color=discord.Colour(0).from_rgb(0, 0, 255))
    embed = await create_embed_scores_json(response_json, embed)
    await ctx.send_followup(embed=embed)
    
@client.slash_command()
async def tops(ctx: discord.ApplicationContext,
             username: Option(str, max_length=15, required=False),
             modo: Option(int, choices=[
                 OptionChoice("osu!standard", value=0),
                 OptionChoice("Taiko", value=1),
                 OptionChoice("Catch the Beat!", value=2),
                 OptionChoice("osu!mania", value=3),
                 OptionChoice("osu!standard Relax", value=4),
                 OptionChoice("Taiko Relax", value=5),
                 OptionChoice("Catch the Beat! Relax", value=6),
                 OptionChoice("osu!standard Autopiloy", value=8),
             ]) = 0,
             mods: Option(str, min_length=2) = "",
             ):
    await ctx.defer()
    
    if not username:
        with open("db.json", "r") as f:
            contents = json.load(f)
        
        username = contents["players"].get(str(ctx.author.id))
        if username is None:
            await ctx.send_followup("Conecte sua conta para usar o comando sem username. `/link`.")
            return
    
    params = {
        "scope": "best",
        "name": username,
        "mode": modo,
        "limit": 5,
        "include_failed": 0
    }
    if mods:
        params["mods"] = mods
        
        
    response = await session.request(method="GET", url=API_URL+"/get_player_scores", params=params)
    response_json = await response.json()
    if response_json['status'] != "success":
        await ctx.send_followup(content=response_json["status"])
        return
    
    embed = discord.Embed(title=f"Melhores jogadas do {response_json['player']['name']}", color=discord.Colour(0).from_rgb(0, 0, 255))
    embed = await create_embed_scores_json(response_json, embed)
    await ctx.send_followup(embed=embed)
    
@client.slash_command()
async def link(ctx: discord.ApplicationContext, username: Option(str, max_length=15)):
    await ctx.defer()
        
    with open("db.json", "r") as f:
        contents: dict = json.load(f)
        
    contents["players"].pop(str(ctx.author.id), None)
    contents["players"][str(ctx.author.id)] = username
    
    with open("db.json", "w") as f:
            json.dump(contents, f)
            
    await ctx.send_followup(f"voce e o {username}")
    


client.run(secret)
