import discord
import os
import yt_dlp
import asyncio
import logging
import time
from discord.ext import commands
from dotenv import load_dotenv
from discord import app_commands
from collections import deque



load_dotenv()

token = os.getenv('DISCORD_TOKEN')

SONG_QUEUE = {}

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
    

    if "bhris" in message.content.lower():
        await message.channel.send("I'm toired")
    
    await bot.process_commands(message)
    

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.command()
async def instagram(ctx):
    """Sends the team Instagram link."""
    url = "https://www.instagram.com/beavsknowbjj"
    embed = discord.Embed(
        title="📸 Beavs Know BJJ Instagram",
        url=url,
        description="Follow us on Instagram!",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command()
async def hello(ctx):
    await ctx.send(f'Hello {ctx.author.name}!')

@bot.command()
async def test(ctx, arg):
    await ctx.send(arg)

# Music commands
NOW_PLAYING = {}


def play_next(interaction, voice_client):
    guild_id = interaction.guild.id
    if SONG_QUEUE[guild_id]:
        title, url = SONG_QUEUE[guild_id].popleft()

        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }

        source = discord.FFmpegOpusAudio(
            url,
            **ffmpeg_options,
            executable="bin\\ffmpeg.exe"
        )

        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            play_next(interaction, voice_client)

        voice_client.play(source, after=after_playing)

        # ✅ Update Now Playing message
        async def update_message():
            view = MusicControls(voice_client, guild_id)
            if guild_id in NOW_PLAYING:
                try:
                    await NOW_PLAYING[guild_id].edit(content=f"🎶 Now playing: **{title}**", view=view)
                except Exception:
                    pass
            else:
                msg = await interaction.followup.send(f"🎶 Now playing: **{title}**", view=view)
                NOW_PLAYING[guild_id] = msg

        asyncio.run_coroutine_threadsafe(update_message(), interaction.client.loop)


@bot.tree.command(name="play", description="Add a song to the queue.")
@app_commands.describe(song="The song to play or add to the queue.")
async def play(interaction: discord.Interaction, song: str):
    await interaction.response.defer(thinking=True)

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ You must be in a voice channel.")
        return

    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    # search YT
    ydl_options = {"format": "bestaudio/best", "noplaylist": True, "quiet": True}
    query = f"ytsearch1:{song}"
    results = await search_youtube(query, ydl_options)
    tracks = results.get("entries", [])
    if not tracks:
        await interaction.followup.send("No results found.")
        return

    first_track = tracks[0]
    title = first_track.get("title", "Untitled")
    url = first_track["url"]

    guild_id = interaction.guild.id
    if guild_id not in SONG_QUEUE:
        SONG_QUEUE[guild_id] = deque()

    SONG_QUEUE[guild_id].append((title, url))

    if not voice_client.is_playing() and not voice_client.is_paused():
        play_next(interaction, voice_client)
        await interaction.followup.send(f"🎶 Added and now playing: **{title}**")
    else:
        await interaction.followup.send(f"➕ Queued: **{title}**")




class MusicControls(discord.ui.View):
    def __init__(self, voice_client, guild_id):
        super().__init__(timeout=None)  # persistent until manually removed
        self.voice_client = voice_client
        self.guild_id = guild_id

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.secondary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            await interaction.response.send_message("⏸ Paused.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Nothing is playing.", ephemeral=True)

    @discord.ui.button(label="▶ Resume", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.response.send_message("▶ Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Nothing is paused.", ephemeral=True)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.primary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()  # triggers play_next automatically
            await interaction.response.send_message("⏭ Skipped.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Nothing to skip.", ephemeral=True)

    @discord.ui.button(label="🛑 Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.voice_client and self.voice_client.is_connected():
            SONG_QUEUE[self.guild_id].clear()
            self.voice_client.stop()
            await self.voice_client.disconnect()
            await interaction.response.send_message("🛑 Stopped playback and left channel.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Not connected.", ephemeral=True)

    @discord.ui.button(label="📜 Queue", style=discord.ButtonStyle.secondary)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.guild_id not in SONG_QUEUE or not SONG_QUEUE[self.guild_id]:
            await interaction.response.send_message("📭 The queue is empty.", ephemeral=True)
        else:
            queue_list = [f"{i+1}. {title}" for i, (title, _) in enumerate(SONG_QUEUE[self.guild_id])]
            queue_text = "\n".join(queue_list)
            await interaction.response.send_message(f"🎶 **Queue:**\n{queue_text}", ephemeral=True)



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
@commands.has_permissions(administrator=True)
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

@event.error
async def event_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 You don’t have permission to create events!", delete_after=5)



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

            channel = bot.get_channel(payload.channel_id)
            try:
                event_message = await channel.fetch_message(payload.message_id)
                await event_message.remove_reaction('✅', member)
            except Exception as e:
                print(f"Error while removing reaction: {e}")
        except Exception as e:
            print(f"Error while collecting first name: {e}")

    # Handle 📃 reaction (show attendance)
    elif payload.emoji.name == '📃':
        
        try:
            message = await channel.fetch_message(message_id)
            await message.remove_reaction('📃', member)
        except Exception as e:
            print(f"Error while removing reaction: {e}")

        attending_members = attendees[unique_event_name]
        try:
            if not attending_members:
                await member.send(f"📭 Nobody has joined **{unique_event_name}** yet.")
            else:
                names = "\n".join(attending_members.values())  
                await member.send(f"👥 **Attendees for {unique_event_name}:**\n{names}")
        except discord.Forbidden:
            await channel.send(f"{member.mention}, I can't send you a DM. Please check your privacy settings.", delete_after=10)
            return

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

    


bot.run(token, log_handler=handler, log_level=logging.DEBUG)