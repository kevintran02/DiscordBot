import discord
import os
import yt_dlp
import asyncio
import logging
from discord.ext import commands
from dotenv import load_dotenv
from discord import app_commands

load_dotenv()

token = os.getenv('DISCORD_TOKEN')

async def search_youtube(query,ydl_options):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query,ydl_options))

def _extract(query, ydl_options):
    with yt_dlp.YoutubeDL(ydl_options) as ydl:
        return ydl.extract_info(query, download = False)

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents) 

Guild_ID = 760782863963521034


@bot.event
async def on_ready():
    test_guild = discord.Object(id=Guild_ID)
    await bot.tree.sync()
    print(f"Slash commands synchronized! Commands: {bot.tree.get_commands()}")

    print("Bot is ready!")

@bot.event
async def on_member_join(member):
    await member.send(f"Welcome to the server {member.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "sup" in message.content.lower():
        await message.channel.send(f"stfu {message.author.name}")
    await bot.process_commands(message)

    if "bhris" in message.content.lower():
        await message.channel.send("I'm toired")
    

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.command()
async def hello(ctx):
    await ctx.send(f'Hello {ctx.author.name}!')

@bot.command()
async def test(ctx, arg):
    await ctx.send(arg)


@bot.tree.command(name="play", description="Play a song or add it to the queue.")
@app_commands.describe(song="The song to play or add to the queue.")
async def play(interaction: discord.Interaction, song: str):
    await interaction.response.defer()

    # Check voice connection
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("You are not connected to a voice channel.")
        return

    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
    }

    query = f"ytsearch1:{song}"
    results = await search_youtube(query, ydl_options)
    tracks = results.get("entries", [])
    if not tracks:
        await interaction.followup.send("No results found.")
        return

    first_track = tracks[0]
    title = first_track.get("title", "Untitled")

    # Select audio-only stream
    formats = first_track.get("formats", [])
    audio_url = None
    for f in formats:
        if f.get("acodec") != "none" and f.get("vcodec") == "none":
            audio_url = f.get("url")
            break

    if not audio_url:
        await interaction.followup.send("Could not find a valid audio stream.")
        return

    # Log the audio URL for debugging
    print(f"🔊 Playing URL: {audio_url}")
    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin",
        "options": "-vn",
    }

    try:
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                audio_url,
                **ffmpeg_options,   
                executable="bin\\ffmpeg.exe"
            )
        )
        if not voice_client.is_playing():
            voice_client.play(source)
            await interaction.followup.send(f"Now playing: **{title}**")
        else:
            await interaction.followup.send("Already playing something.")

        # Wait until playback finishes
        while voice_client.is_playing():
            await asyncio.sleep(1)

    except Exception as e:
        await interaction.followup.send(f"Playback error: {str(e)}")

    # Delay disconnect slightly to avoid race condition
    await asyncio.sleep(0.5)
    # Only disconnect after playback completes
    if voice_client.is_connected():
        await voice_client.disconnect()




attendees = {}
@bot.command()
async def create_event(ctx, *, event_name): 
    event_message = await ctx.send(f"Event: '{event_name}'\nReact with ✅ if you're attending.")
    await event_message.add_reaction('✅')
    attendees[event_message.id] = set()
    await ctx.send(f"Use !attendance {event_message.id} to see who is attending.")

@bot.event
async def on_raw_reaction_add(payload):
    if payload.emoji.name != '✅':
        return

    message_id = payload.message_id
    if message_id not in attendees:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    attendees[message_id].add(member.name)
    channel = bot.get_channel(payload.channel_id)
    if channel:
        await channel.send(f"{member.name} is attending the event!")

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.emoji.name != '✅':
        return

    message_id = payload.message_id
    if message_id not in attendees:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    attendees[message_id].discard(member.name)
    channel = bot.get_channel(payload.channel_id)
    if channel:
        await channel.send(f"{member.name} is no longer attending the event!")
    
@bot.command()
async def attendance(ctx, message_id: int):
    if message_id not in attendees:
        await ctx.send("No event found with that ID.")
        return
    
    attending_members = attendees[message_id]
    if not attending_members:
        await ctx.send("No one is attending this event.")
    else:
        names = "\n".join(attending_members)
        await ctx.send(f"Attendees: \n{names}")

bot.run(token, log_handler=handler, log_level=logging.DEBUG)

