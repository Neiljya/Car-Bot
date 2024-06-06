import random
from utils import MeowEncoderDecoder, ConfigLoader
from discord.ext import commands

encoder_decoder = MeowEncoderDecoder()

class Events_Cog(commands.Cog, name="Events"):
    def __init__(self, bot, config_directory, *args, **kwargs):
        self.bot = bot
        self.config_directory = config_directory

    #@commands.Cog.listener()







