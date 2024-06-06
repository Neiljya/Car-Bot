import discord
import random
from utils import ConfigLoader, MeowEncoderDecoder
from discord.ext import commands
from command_cog import Commands_Cog, Music_Cog
from event_cog import Events_Cog
from games_cog import Games_Cog
from economy import Economy_Cog
import os

TOKEN = os.environ.get('BOT_TOKEN')

intents = discord.Intents.all()
intents.members = True

client = commands.Bot(command_prefix='-', intents=intents)


encoder_decoder = MeowEncoderDecoder()
config_directory = 'config/config.json'
facts_directory = 'config/facts.json'
config_loader = ConfigLoader(config_directory)
config = config_loader.load_config()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    config = ConfigLoader(config_directory).load_config()
    msg = message.content.lower()

    if any(word in msg for word in config['filter_words']) and not message.content.startswith('-'):
        response = random.choice(config['responses'])
        print(response)

        await message.channel.send(f'{message.author.mention} {encoder_decoder.encode_message(response)}')

    await client.process_commands(message)


db = os.environ.get('MONGO_URI')

stock_data = "shopdata/stocks.json"
shop_file = "shopdata/shopdata.json"

async def load_extensions():
    await client.add_cog(Events_Cog(client, config_directory))
    await client.add_cog(Commands_Cog(client, config_directory, facts_directory))
    await client.add_cog(Music_Cog(client))
    await client.add_cog(Games_Cog(client))
    await client.add_cog(Economy_Cog(client, db, shop_file, stock_data, 2000))


@client.event
async def on_ready():
    print(f'Logged in as: {client.user}')
    await load_extensions()



client.run(TOKEN)

