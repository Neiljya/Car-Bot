from games import catsweeper
from discord.ext import commands
import random

class Games_Cog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {}

    @commands.command()
    async def catsweeper(self, ctx, size: int = 5, bombs: int = 5):
        if size < 2 or size > 10 or bombs < 1 or bombs >= size * size:
            await ctx.send("Invalid size or number of bombs. Size must be between 2 and 10, and bombs must be at least 1 and less than size*size.")
            return

        game = catsweeper.CatsweeperGame(size, bombs)
        self.games[ctx.author.id] = game

        view = catsweeper.CatsweeperView(game)
        await ctx.send("Catsweeper Game", view=view)

    async def setup(self, bot):
        await bot.add_cog(self)