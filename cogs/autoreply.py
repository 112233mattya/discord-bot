# cogs/autoreply.py
from discord.ext import commands

class AutoReply(commands.Cog):
    """簡単な自動返信 Cog（挨拶系）"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # 他の Cog やコマンド処理を邪魔しないために最初にチェック
        if message.author.bot:
            return

        text = message.content.strip().lower()

        # 完全一致の短い挨拶群（UI は変えない）
        if text == "おはよう":
            await message.channel.send("おっは〜！")
        elif text == "おやすみ":
            await message.channel.send("おっや〜！")
        elif text == "こんにちは":
            await message.channel.send("こんちゃ〜！")
        elif text == "こんばんは":
            await message.channel.send("ばんちゃ〜！")
        elif text == "ただいま":
            await message.channel.send("おかえり〜！")
        elif text == "いってきます":
            await message.channel.send("いってら〜！")

        # これがないとコマンドが処理されない（重要）
        await self.bot.process_commands(message)

def setup(bot):
    bot.add_cog(AutoReply(bot))
