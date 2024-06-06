import discord
import json
from discord.ext import commands, tasks
from pymongo import MongoClient
from datetime import datetime, timedelta
from utils import simulate_stock_price, load_initial_stocks

class StockMarket:
    def __init__(self, economy_cog, stock_file, min_investment):
        self.economy_cog = economy_cog
        self.stock_file = stock_file
        self.min_investment = min_investment
        self.update_stocks.start()

    # Updates the stocks every 15 minutes to simulate market volatility
    @tasks.loop(minutes=15)
    async def update_stocks(self):
        all_stocks = self.economy_cog.get_all_stock_symbols()
        for symbol in all_stocks:
            stock_data = self.economy_cog.get_stock_price(symbol)
            if stock_data is not None:
                current_price = stock_data["price"]
                new_price = simulate_stock_price(current_price)
                self.economy_cog.update_stock_price(symbol, new_price)

    def invest(self, user_id, symbol, amount):
        if amount < self.min_investment:
            return f"The minimum investment is ${self.min_investment}."

        stock_price = self.economy_cog.get_stock_price(symbol)
        if stock_price is None:
            return "Invalid stock symbol or unable to fetch stock data."

        shares = amount / stock_price
        self.economy_cog.update_user_balance(user_id, -amount)
        self.economy_cog.add_to_stock_portfolio(user_id, symbol, shares)
        return f"You have invested ${amount} in {symbol}. You now own {shares:.2f} shares."

    # Add all values of stocks in portfolio
    def get_portfolio_value(self, user_id):
        portfolio = self.economy_cog.get_stock_portfolio(user_id)
        total_value = 0
        for symbol, shares in portfolio.items():
            stock_price = self.economy_cog.get_stock_price(symbol)
            total_value += shares * stock_price
        return total_value

class Economy_Cog(commands.Cog):
    def __init__(self, bot, mongo_uri, shop_file, stock_file, min_investment):
        self.bot = bot
        self.client = MongoClient(mongo_uri)
        self.db = self.client["users"]
        self.users = self.db["users"]
        self.stocks = self.db["stocks"]
        self.trades = self.db["trades"]
        self.daily_amount = 500
        self.shop_file = shop_file
        self.load_shop_items()
        self.stock_market = StockMarket(self, stock_file, min_investment)
        self.initialize_stocks(stock_file)

    def load_shop_items(self):
        with open(self.shop_file, 'r') as f:
            self.shop_items = json.load(f)["items"]

    def save_shop_items(self):
        with open(self.shop_file, 'w') as f:
            json.dump({"items": self.shop_items}, f, indent=4)

    def get_user_data(self, user_id):
        user_data = self.users.find_one({"user_id": user_id})
        if not user_data:
            user_data = {"user_id": user_id, "balance": 0, "last_daily": None, "inventory": {}, "portfolio": {}}
            self.users.insert_one(user_data)
        return user_data

    def update_user_balance(self, user_id, amount):
        self.users.update_one({"user_id": user_id}, {"$inc": {"balance": amount}})

    def update_last_daily(self, user_id):
        self.users.update_one({"user_id": user_id}, {"$set": {"last_daily": datetime.utcnow()}})

    def add_to_inventory(self, user_id, item_name, amount=1):
        self.users.update_one({"user_id": user_id}, {"$inc": {f"inventory.{item_name}": amount}})

    def remove_from_inventory(self, user_id, item_name, amount=1):
        user_data = self.get_user_data(user_id)
        if user_data["inventory"].get(item_name, 0) <= amount:
            self.users.update_one({"user_id": user_id}, {"$unset": {f"inventory.{item_name}": ""}})
        else:
            self.users.update_one({"user_id": user_id}, {"$inc": {f"inventory.{item_name}": -amount}})

    def add_to_stock_portfolio(self, user_id, symbol, shares):
        self.users.update_one({"user_id": user_id}, {"$inc": {f"portfolio.{symbol}": shares}})

    def get_stock_portfolio(self, user_id):
        user_data = self.get_user_data(user_id)
        return user_data.get("portfolio", {})

    def get_all_stock_symbols(self):
        return [stock["symbol"] for stock in self.stocks.find()]

    def get_stock_price(self, symbol):
        stock_data = self.stocks.find_one({"symbol": symbol})
        return stock_data["price"] if stock_data else None

    def update_stock_price(self, symbol, new_price):
        self.stocks.update_one({"symbol": symbol}, {"$set": {"price": new_price}}, upsert=True)

    def initialize_stocks(self, stock_file):
        initial_prices = load_initial_stocks(stock_file)
        for symbol, price in initial_prices.items():
            self.update_stock_price(symbol, price)

    @commands.command()
    async def balance(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        await ctx.send(f"{ctx.author.mention}, you have ${user_data['balance']}")

    @commands.command()
    async def daily(self, ctx):
        user_data = self.get_user_data(ctx.author.id) # Ensures the data exists
        last_daily = user_data.get("last_daily") 

        # If there is a logged date
        if last_daily:
            # Check the time difference
            elapsed_time = datetime.utcnow() - last_daily

            # If its less than 24 hours then deny the command
            if elapsed_time < timedelta(hours=24):
                await ctx.send(f"{ctx.author.mention}, you've already claimed your daily reward.")
                return

        self.update_user_balance(ctx.author.id, self.daily_amount)
        self.update_last_daily(ctx.author.id)
        await ctx.send(f"{ctx.author.mention}, you have claimed your daily reward of ${self.daily_amount}")

    @commands.command()
    async def give(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send("You must give a positive amount.")
            return

        user_data = self.get_user_data(ctx.author.id)
        if user_data["balance"] < amount:
            await ctx.send("You don't have enough money to give.")
            return

        self.update_user_balance(ctx.author.id, -amount)
        self.update_user_balance(member.id, amount)
        await ctx.send(f"{ctx.author.mention} has given ${amount} to {member.mention}.")

    @commands.command()
    async def leaderboard(self, ctx):
        leaderboard = self.users.find().sort("balance", -1).limit(10)
        leaderboard_text = "Leaderboard: \n"
        for idx, user_data in enumerate(leaderboard):
            user = self.bot.get_user(user_data["user_id"])
            if user:
                leaderboard_text += f"**{idx + 1}. {user.name}** - ``${user_data['balance']}``\n"
            else:
                leaderboard_text += f"{idx + 1}. Unknown User - ${user_data['balance']}\n"
        await ctx.send(leaderboard_text)

    @commands.command()
    async def shop(self, ctx, page: int = 1):
        items_per_page = 15
        pages = (len(self.shop_items) - 1) // items_per_page + 1
        if page < 1 or page > pages:
            await ctx.send(f"Page number must be between 1 and {pages}")
            return

        start = (page - 1) * items_per_page
        end = start + items_per_page
        items = self.shop_items[start:end]

        embed = discord.Embed(title="Shop", description=f"Page {page}/{pages}")
        for item in items:
            embed.add_field(name=item.get("name", "Unknown"), value=f"Price: ${item.get('price', 'Unknown')}, Type: {item.get('type', 'Unknown')}\nDescription: {item.get('description', 'No description')}", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def buy(self, ctx, *, item_name: str, amount: int = 1):
        item = next((item for item in self.shop_items if item["name"].lower() == item_name.lower()), None)
        if not item:
            await ctx.send("Item not found.")
            return

        total_price = item["price"] * amount
        user_data = self.get_user_data(ctx.author.id)
        if user_data["balance"] < total_price:
            await ctx.send("You don't have enough money to buy this item.")
            return

        if item["type"] == "role":
            role = discord.utils.get(ctx.guild.roles, id=item["role_id"])
            if role:
                await ctx.author.add_roles(role)
                await ctx.send(f"You have bought the role {role.name}.")
            else:
                await ctx.send("Role not found in the server.")
        elif item["type"] == "product":
            self.add_to_inventory(ctx.author.id, item["name"], amount)
            await ctx.send(f"You have bought {amount} x {item['name']}.")

        self.update_user_balance(ctx.author.id, -total_price)

    @commands.command()
    async def inventory(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        inventory = user_data.get("inventory", {})
        if not inventory:
            await ctx.send("Your inventory is empty.")
            return

        inventory_text = "Your inventory:\n" + "\n".join([f"{item}: {amount}" for item, amount in inventory.items()])
        await ctx.send(inventory_text)

    @commands.command()
    async def sell(self, ctx, *, item_name: str, amount: int = 1):
        user_data = self.get_user_data(ctx.author.id)
        inventory = user_data.get("inventory", {})
        if inventory.get(item_name, 0) < amount:
            await ctx.send("You don't have enough of this item in your inventory.")
            return

        item = next((item for item in self.shop_items if item["name"].lower() == item_name.lower()), None)
        if not item:
            await ctx.send("Item not found.")
            return

        if item["type"] == "role":
            await ctx.send("Roles cannot be sold.")
            return

        sell_price = item["price"] * amount // 2
        self.remove_from_inventory(ctx.author.id, item["name"], amount)
        self.update_user_balance(ctx.author.id, sell_price)
        await ctx.send(f"You have sold {amount} x {item_name} for ${sell_price}.")

    @commands.command()
    async def trade(self, ctx, member: discord.Member, item_name: str, amount: int = 1):
        user_data = self.get_user_data(ctx.author.id)
        inventory = user_data.get("inventory", {})
        if inventory.get(item_name, 0) < amount:
            await ctx.send("You don't have enough of this item in your inventory.")
            return

        item = next((item for item in self.shop_items if item["name"].lower() == item_name.lower()), None)
        if not item:
            await ctx.send("Item not found.")
            return

        if item["type"] == "role":
            await ctx.send("Roles cannot be traded.")
            return

        trade_request = {
            "from_user": ctx.author.id,
            "to_user": member.id,
            "item": item["name"],
            "amount": amount,
            "status": "pending"
        }
        self.trades.insert_one(trade_request)
        await ctx.send(f"{ctx.author.mention} has requested to trade {amount} x {item_name} with {member.mention}. {member.mention}, use `!accept_trade {ctx.author.id}` to accept the trade.")

    @commands.command()
    async def accept_trade(self, ctx, from_user_id: int):
        trade_request = self.trades.find_one({"from_user": from_user_id, "to_user": ctx.author.id, "status": "pending"})
        if not trade_request:
            await ctx.send("No pending trade request found.")
            return

        self.remove_from_inventory(trade_request["from_user"], trade_request["item"], trade_request["amount"])
        self.add_to_inventory(ctx.author.id, trade_request["item"], trade_request["amount"])
        self.trades.update_one({"_id": trade_request["_id"]}, {"$set": {"status": "accepted"}})
        await ctx.send(f"Trade accepted. You have received {trade_request['amount']} x {trade_request['item']} from {self.bot.get_user(from_user_id).mention}.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add_item(self, ctx, name: str, price: int, item_type: str, description: str, role_id: int = None):
        if item_type not in ["role", "product"]:
            await ctx.send("Invalid item type. Must be 'role' or 'product'.")
            return

        if item_type == "role" and not role_id:
            await ctx.send("Role ID is required for role items")
            return

        new_item = {
            "name": name,
            "price": price,
            "type": item_type,
            "description": description
        }
        if item_type == "role":
            new_item["role_id"] = role_id

        self.shop_items.append(new_item)
        self.save_shop_items()
        await ctx.send(f"Item ``{name}`` has been added to the shop.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def remove_item(self, ctx, name: str):
        item = next((item for item in self.shop_items if item["name"].lower() == name.lower()), None)
        if not item:
            await ctx.send("Item not found.")
            return

        self.shop_items = [item for item in self.shop_items if item["name"].lower() != name.lower()]
        self.save_shop_items()
        await ctx.send(f"Item '{name}' removed from the shop.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def modify_item(self, ctx, name: str, price: int = None, description: str = None):
        item = next((item for item in self.shop_items if item["name"].lower() == name.lower()), None)
        if not item:
            await ctx.send("Item not found.")
            return

        if price is not None:
            item["price"] = price
        if description is not None:
            item["description"] = description

        self.save_shop_items()
        await ctx.send(f"Item '{name}' modified in the shop.")

    @commands.command()
    async def invest(self, ctx, symbol: str, amount: int):
        """Invest in the stock market"""
        result = self.stock_market.invest(ctx.author.id, symbol, amount)
        await ctx.send(result)

    @commands.command()
    async def portfolio(self, ctx):
        # Check the stock portfolio
        portfolio_value = self.stock_market.get_portfolio_value(ctx.author.id)
        await ctx.send(f"{ctx.author.mention}, your portfolio is currently valued at ${portfolio_value:.2f}.")

    @commands.command()
    async def stock_performance(self, ctx):
        # Display stocks and their performances
        stocks = self.stocks.find()
        embed = discord.Embed(title="Stock Performance")
        for stock in stocks:
            name = stock.get("name", "Unknown Name")
            symbol = stock.get("symbol", "Unknown Symbol")
            price = stock.get("price", "Unknown Price")
            embed.add_field(name=f"{symbol} ({name})", value=f"Price: ${price}", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    async def sell_shares(self, ctx, symbol: str, shares: float):
        user_data = self.get_user_data(ctx.author.id)
        portfolio = user_data.get("portfolio", {})
        if portfolio.get(symbol, 0) < shares:
            await ctx.send("You don't have enough shares to sell.")
            return

        stock_price = self.get_stock_price(symbol)
        if stock_price is None:
            await ctx.send("Invalid stock symbol.")
            return

        total_sale = shares * stock_price
        self.users.update_one({"user_id": ctx.author.id}, {"$inc": {f"portfolio.{symbol}": -shares}})
        self.update_user_balance(ctx.author.id, total_sale)
        await ctx.send(f"You have sold {shares} shares of {symbol} for ${total_sale:.2f}.")
