from utils import MeowEncoderDecoder, ConfigLoader
import os
import asyncio
import random
import discord
import yt_dlp as youtube_dl
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from discord.ext import commands, tasks
encoder_decoder = MeowEncoderDecoder()

class Commands_Cog(commands.Cog, name="Commands"):
    def __init__(self, bot, config_directory, facts_directory, *args, **kwargs):
        self.bot = bot
        self.config_directory = config_directory
        self.facts_directory = facts_directory
        self.last_encoded_message = None
        self.last_decoded_message = None

    @commands.command()
    async def encode(self, ctx, *words):
        to_encode = ""
        for word in words:
            to_encode = to_encode + word + " "

        if to_encode != self.last_encoded_message:
            encoded_message = encoder_decoder.encode_message(to_encode)
            await ctx.send(encoded_message)
            self.last_encoded_message = to_encode

    @commands.command()
    async def decode(self, ctx, *words):
        to_decode = ""
        for word in words:
            to_decode = to_decode + word + " "

        if to_decode != self.last_decoded_message:
            decoded_message = encoder_decoder.decode_message(to_decode)
            await ctx.send(decoded_message)
            self.last_decoded_message = to_decode

    @commands.command(alias=['car'])
    async def randomcar(self, ctx):
        base_url = "https://cataas.com/cat?html=true"

        try:
            response = requests.get(base_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")
            img_element = soup.find("img")

            if img_element:
                image_url = img_element["src"]
                await ctx.send(image_url)
            else:
                await ctx.send("Sorry, couldn't find an image in the response")

        except requests.exceptions.RequestException as e:
            print(f"An error occurred fetching a cat image: {e}")
            await ctx.send("Sorry, there was an error fetching a cat image")

    @commands.command()
    async def carfact(self, ctx):
        facts = ConfigLoader(self.facts_directory).load_config()

        await ctx.send(random.choice(facts["facts"]))

    async def setup(self, bot):
        await bot.add_cog(self)


class Music_Cog(commands.Cog, name="Music"):
    def __init__(self, bot):
        self.bot = bot
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'extract_flat': 'in_playlist',
            'outtmpl': 'downloads/%(id)s.%(ext)s'
        }

        self.ffmpeg_opts = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }

        self.current_message = None
        self.current_start_time = None
        self.current_duration = None
        self.current_title = None
        self.current_artist = None
        self.song_queue = asyncio.Queue()
        self.current_song_info = None
        self.time_cap = 10 * 60

        self.check_empty_vc.start()
        self.update_playbar.start()


    @commands.command()
    async def play(self, ctx, channel_name: str, song_url: str):
        # Find the voice channel by name
        channel = discord.utils.get(ctx.guild.voice_channels, name=channel_name)
        if not channel:
            await ctx.send(f'Voice channel "{channel_name}" not found')
            return

        # Check if the user is in the voice channel, else tell the user to join it
        if ctx.author.voice and ctx.author.voice.channel == channel:
            pass
        else:
            await ctx.send('You need to join the voice channel first!')
            return

        # Connect to the voice channel if not already connected
        """
        if not ctx.voice_client or not ctx.voice_client.is_connected():
            vc = await channel.connect()
        else:
            vc = ctx.voice_client
        """



        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)
            title = info.get('title', 'Unknown Title')
            artist = info.get('uploader', 'Unknown Artist')
            duration = info.get('duration', 0)

        if duration > self.time_cap:
            await ctx.send(f'The video ``{title}`` is too long ({self.format_duration(duration)}). Maximum allowed duration is 10 minutes.')
            return

        await self.song_queue.put((ctx, channel, song_url, title, artist))

        await ctx.send(f'Added to queue: ``{title}`` by ``{artist}``')

        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await self.play_next_song()

    async def play_next_song(self):
        # Play the music

        if self.song_queue.empty():
            return

        ctx, channel, song_url, title, artist = await self.song_queue.get()

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            vc = await channel.connect()
        else:
            vc = ctx.voice_client

        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(song_url, download=False)
            url2 = info['url']
            duration = info.get('duration', 0)
            file_path = ydl.prepare_filename(info)

            self.current_duration = duration
            self.current_start_time = datetime.now()
            self.current_title = title
            self.current_artist = artist
            self.current_song_info = (title, artist, file_path)




            vc.play(discord.FFmpegPCMAudio(url2, **self.ffmpeg_opts), after=lambda e: self.bot.loop.create_task(self.song_finished(ctx)))

        playbar_message = await ctx.send(f'Now playing: ``{title}``\n By: ``{artist}``\n **{"—" * 30}** ``[0:00/{self.format_duration(duration)}]``')
        self.current_message = playbar_message
        #await ctx.send(f'Now playing: {info["title"]}')

    async def song_finished(self, ctx):
        if self.current_song_info:
            file_path = self.current_song_info[2]
            if os.path.exists(file_path):
                os.remove(file_path)

        self.current_song_info = None
        await self.play_next_song()

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send('Paused the current song.')

    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('Resumed the current song,')

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send('Skipped the current song.')

    @commands.command()
    async def queue(self, ctx):
        if self.song_queue.empty():
            await ctx.send('The queue is empty.')
            return

        queue_list = list(self.song_queue._queue)
        current_song = f"> Now playing: {self.current_title} by {self.current_artist}\n"
        upcoming_songs = "\n".join(
            [f"``{i + 1}``. **{title}** by **{artist}**" for i, (ctx, channel, url, title, artist) in enumerate(queue_list)])
        await ctx.send(current_song + "Upcoming songs:\n" + upcoming_songs)

    @commands.command()
    async def remove(self, ctx, index: int):
        queue_list = list(self.song_queue._queue)
        if 0 <= index < len(queue_list):
            del queue_list[index]
            self.song_queue = asyncio.Queue()
            for item in queue_list:
                await self.song_queue.put(item)
            await ctx.send(f'Removed song at position {index + 1} from the queue')
        else:
            await ctx.send(f'No song at position {index + 1} in the queue')

    @tasks.loop(seconds=1)
    async def update_playbar(self):
        if self.current_message and self.current_start_time and self.current_duration:
            elapsed_time = (datetime.now() - self.current_start_time).seconds
            if elapsed_time > self.current_duration:
                self.current_message = None
                self.current_start_time = None
                self.current_duration = None
                self.current_title = None
                self.current_artist = None
                return

            playbar = self.create_playbar(elapsed_time, self.current_duration)
            await self.current_message.edit(content=playbar)

    def create_playbar(self, elapsed, duration):
        elapsed_str = self.format_duration(elapsed)
        duration_str = self.format_duration(duration)
        bar_length = 30
        progress = int(bar_length * (elapsed / duration))
        playbar = f'{"=" * progress}{"-" * (bar_length - progress)}'
        return f'Now playing: ``{self.current_title}``\n``{self.current_artist}``\n**{playbar}** ``[{elapsed_str}/{duration_str}]``'

    def format_duration(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        return f'{minutes}:{seconds:02d}'

    @tasks.loop(seconds=60)
    async def check_empty_vc(self):
        for vc in self.bot.voice_clients:
            if len(vc.channel.members) == 1:
                await asyncio.sleep(60)
                if len(vc.channel.members) == 1:
                    await vc.disconnect()

    @commands.Cog.listener()
    async def on_state_update(self, member, before, after):
        if not before.channel:
            return

        voice_client = discord.utils.get(self.bot.voice_clients, guild=before.channel.guild)
        if voice_client and len(voice_client.channel.members) == 1:
            await asyncio.sleep(60)
            if len(voice_client.channel.members) == 1:
                await voice_client.disconnect()

    async def setup(self, bot):
        await bot.add_cog(self)





