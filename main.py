import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

# ===== .env 読み込み =====
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# 設定ファイルロード
def load_config():
    if not os.path.exists("config.json"):
        with open("config.json", "w", encoding="utf8") as f:
            json.dump({"verify_role": None, "verify_log": None}, f)
    with open("config.json", "r", encoding="utf8") as f:
        return json.load(f)

def save_config(cfg):
    with open("config.json", "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=4)

config = load_config()

@bot.event
async def on_ready():
    print("🚀 BOT起動しました")

# Cogs 読み込み
async def setup():
    await bot.load_extension("cogs.verify")

bot.loop.run_until_complete(setup())

print("🔌 TOKEN 読み込み確認:", "成功" if TOKEN else "失敗（.env確認しろ）")

bot.run(TOKEN)
