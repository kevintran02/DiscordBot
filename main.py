import discord
import os
import yt_dlp
import asyncio
import logging
import time
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

class MyBot(commands.Bot):
    async def setup_hook(self):
        # Start the cleanup task
        asyncio.create_task(cleanup_expired_events())

bot = MyBot(command_prefix='!', intents=intents)

GUILD_ID = 1397065582880493618


@bot.event
async def on_ready():
    await bot.tree.clear_commands()
    await bot.tree.sync()

    print("Global slash commands synchronized!")
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

# Music commands

@bot.tree.command(name="play", description="add it to the queue.")
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
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")


    # Log the audio URL for debugging
    print(f"🔊 Playing URL: {audio_url}")
    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
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


@bot.tree.command(name="leave", description="Disconnect the bot from the voice channel.")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await interaction.response.send_message("Disconnected.")
    else:
        await interaction.response.send_message("I'm not connected to any voice channel.")

@bot.tree.command(name="join", description="Make the bot join your voice channel.")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
        await interaction.response.send_message(f"Joined {voice_channel.name}.")
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)
        await interaction.response.send_message(f"Moved to {voice_channel.name}.")
    else:
        await interaction.response.send_message("I'm already in that channel.")

## Event attendance tracking
attendees = {}
event_names = {}
event_expiry = {}
event_counter = {}
event_messages = {}
attendance_messages = {}

@bot.command()
async def event(ctx, *, event_name):
    # Delete the user's message
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages.")

    # Check if the event name already exists
    if event_name in attendees:
        count = 2
        while f"{event_name} #{count}" in attendees:
            count += 1
        unique_event_name = f"{event_name} #{count}"
    else:
        unique_event_name = event_name

    
    embed = discord.Embed(
        title="📢 New Event Created!",
        color=discord.Color.dark_gray()
    )

    embed.add_field(
        name="🎟️ Event Name",
        value=f"**{unique_event_name}**",
        inline=False
    )

    
    embed.add_field(
        name="✅ How to Join",
        value="React with ✅ if you're attending.",
        inline=False
    )

    embed.add_field(
        name="📃 See Attendees",
        value="React with 📃 to see who is attending.",
        inline=False
    )

    # Footer
    embed.set_footer(text="Organized by BJJ/MAA Club • Expires in 48 hours")

    event_message = await ctx.send(embed=embed)
    await event_message.add_reaction("✅")
    await event_message.add_reaction("📃")

    # Store event details
    attendees[unique_event_name] = {}
    event_names[event_message.id] = unique_event_name
    event_expiry[unique_event_name] = time.time() + 48 * 60 * 60
    event_messages[unique_event_name] = event_message.id



@bot.event
async def on_raw_reaction_add(payload):
    # Check if the reaction is on an event message
    message_id = payload.message_id
    if message_id not in event_names:
        return

    unique_event_name = event_names[message_id]
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    channel = bot.get_channel(payload.channel_id)

    # Handle ✅ reaction (join the event)
    if payload.emoji.name == '✅':
        # Prompt the user for their first name
        try:
            await member.send(f"Hi {member.name}, please reply with your name to join the event '{unique_event_name}'.")
            
            def check(dm_message):
                return dm_message.author == member and isinstance(dm_message.channel, discord.DMChannel)

            # Wait for the user's response
            dm_message = await bot.wait_for('message', check=check, timeout=60)  # 60 seconds timeout
            first_name = dm_message.content.strip()

            # Add the user's ID and first name to the attendees list
            attendees[unique_event_name][member.id] = first_name
        except asyncio.TimeoutError:
            await member.send("You did not respond in time. Please react again and reply with your name.")
        except Exception as e:
            print(f"Error while collecting first name: {e}")

    # Handle 📃 reaction (show attendance)
    elif payload.emoji.name == '📃':
        attending_members = attendees[unique_event_name]
        if not attending_members:
            attendance_message = await channel.send(f"No one is attending the event '{unique_event_name}'.")
        else:
            names = "\n".join(attending_members.values())  # Get first names from the dictionary
            attendance_message = await channel.send(f"Attendees for '{unique_event_name}':\n{names}")

        # Track the attendance message
        if unique_event_name not in attendance_messages:
            attendance_messages[unique_event_name] = []
        attendance_messages[unique_event_name].append(attendance_message.id)

@bot.event
async def on_raw_reaction_remove(payload):
    # Check if the reaction is on an event message
    message_id = payload.message_id
    if message_id not in event_names:
        return

    unique_event_name = event_names[message_id]
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    channel = bot.get_channel(payload.channel_id)

    # Handle ✅ reaction removal (leave the event)
    if payload.emoji.name == '✅':
        if member.id in attendees[unique_event_name]:
            attendees[unique_event_name].pop(member.id)  # Remove by user ID
    elif payload.emoji.name == '📃':
            if unique_event_name in attendance_messages:
            # Delete all attendance messages for this event
                for message_id in attendance_messages[unique_event_name]:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                    except discord.NotFound:
                        continue  # Skip if the message is not found
                    except discord.Forbidden:
                        print(f"Could not delete attendance message in {channel.name}.")
                # Clear the attendance messages for this event
                attendance_messages[unique_event_name] = []

# Background task to clean up expired events
async def cleanup_expired_events():
    while True:
        current_time = time.time()
        expired_events = [name for name, expiry in event_expiry.items() if expiry < current_time]

        for event_name in expired_events:
            del attendees[event_name]
            del event_expiry[event_name]
            del event_counter[event_name]

            # Remove the event from the event_names dictionary
            message_ids_to_remove = [msg_id for msg_id, name in event_names.items() if name == event_name]
            for msg_id in message_ids_to_remove:
                del event_names[msg_id]

        # Reset the event counter if all events are cleared
        if not attendees:
            event_counter.clear()

        await asyncio.sleep(60)  # Check every minute

@bot.command(name="clear")
async def clear(ctx):
    # Delete the user's message
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("I don't have permission to delete messages.")

    # Clear all event-related data
    for event_name, message_id in event_messages.items():
        # Attempt to delete the event message
        deleted = False
        for channel in ctx.guild.text_channels:
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
                deleted = True
                break  # Exit the loop once the message is deleted
            except discord.NotFound:
                continue  # Skip if the message is not found
            except discord.Forbidden:
                await ctx.send(f"I don't have permission to delete messages in {channel.name}.")
                continue

        if not deleted:
            await ctx.send(f"Could not find or delete the event message for '{event_name}'.")

    # Delete all attendance messages
    for event_name, message_ids in attendance_messages.items():
        for message_id in message_ids:
            for channel in ctx.guild.text_channels:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    break  # Exit the loop once the message is deleted
                except discord.NotFound:
                    continue  # Skip if the message is not found
                except discord.Forbidden:
                    await ctx.send(f"I don't have permission to delete messages in {channel.name}.")
                    continue

    # Clear the event data
    attendees.clear()
    event_names.clear()
    event_expiry.clear()
    event_counter.clear()
    event_messages.clear()  # Clear the event messages dictionary
    attendance_messages.clear()  # Clear the attendance messages dictionary

    await ctx.send("All events and attendance messages have been cleared.")
    


bot.run(token, log_handler=handler, log_level=logging.DEBUG)

