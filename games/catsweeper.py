import discord
import random
from discord.ext import commands

class CatsweeperGame:
    def __init__(self, size=5, bombs=5):
        self.size = size
        self.bombs = bombs
        self.board = [[0 for _ in range(size)] for _ in range(size)]
        self.mask = [[False for _ in range(size)] for _ in range(size)]
        self.place_bombs()
        self.calculate_numbers()

    def place_bombs(self):
        placed_bombs = 0
        while placed_bombs < self.bombs:
            x = random.randint(0, self.size - 1)
            y = random.randint(0, self.size - 1)
            if self.board[y][x] == 0:
                self.board[y][x] = -1
                placed_bombs += 1

    def calculate_numbers(self):
        for y in range(self.size):
            for x in range(self.size):
                if self.board[y][x] == -1:
                    continue
                count = 0
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if 0 <= x + dx < self.size and 0 <= y + dy < self.size:
                            if self.board[y + dy][x + dx] == -1:
                                count += 1
                self.board[y][x] = count

    def reveal(self, x, y):
        if self.mask[y][x]:
            return
        self.mask[y][x] = True
        if self.board[y][x] == 0:
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if 0 <= x + dx < self.size and 0 <= y + dy < self.size:
                        self.reveal(x + dx, y + dy)

    def check_win(self):
        for y in range(self.size):
            for x in range(self.size):
                if self.board[y][x] != -1 and not self.mask[y][x]:
                    return False
        return True

    def get_board_view(self):
        emojis = {
            -1: '💣',
            0: '⬜',
            1: '1️⃣',
            2: '2️⃣',
            3: '3️⃣',
            4: '4️⃣',
            5: '5️⃣',
            6: '6️⃣',
            7: '7️⃣',
            8: '8️⃣',
        }
        return [[emojis[self.board[y][x]] if self.mask[y][x] else '⬛' for x in range(self.size)] for y in range(self.size)]

class CatsweeperButton(discord.ui.Button):
    def __init__(self, x, y, game):
        super().__init__(style=discord.ButtonStyle.grey, label='⬛', row=y, custom_id=f"{x},{y}")
        self.x = x
        self.y = y
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if self.game.mask[self.y][self.x]:
            await interaction.response.send_message("This cell is already revealed!", ephemeral=True)
            return

        self.game.reveal(self.x, self.y)
        board_view = self.game.get_board_view()

        if self.game.board[self.y][self.x] == -1:
            await interaction.response.edit_message(content="💥 Boom! You hit a bomb! Game over.", view=None)
            self.view.stop()
            return

        if self.game.check_win():
            await interaction.response.edit_message(content="🎉 Congratulations! You won the game!", view=None)
            self.view.stop()
            return

        for item in self.view.children:
            if isinstance(item, CatsweeperButton):
                item.label = board_view[item.y][item.x]
                item.disabled = self.game.mask[item.y][item.x]

        await interaction.response.edit_message(view=self.view)

class CatsweeperView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
        for y in range(game.size):
            for x in range(game.size):
                self.add_item(CatsweeperButton(x, y, game))
