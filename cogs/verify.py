import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import os

def load_config():
    if not os.path.exists("config.json"):
        with open("config.json", "w", encoding="utf8") as f:
            json.dump({"verify_role": None, "verify_log": None}, f)

    with open("config.json", "r", encoding="utf8") as f:
        return json.load(f)

def save_config(cfg):
    with open("config.json", "w", encoding="utf8") as f:
        json.dump(cfg, f, indent=4)

class VerifyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 認証ロール設定
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setverifyrole(self, ctx, role: discord.Role):
        cfg = load_config()
        cfg["verify_role"] = role.id
        save_config(cfg)
        await ctx.reply(f"✅ 認証ロールを **{role.name}** に設定しました！")

    # ログチャンネル設定
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def verifylogset(self, ctx, ch: discord.TextChannel):
        cfg = load_config()
        cfg["verify_log"] = ch.id
        save_config(cfg)
        await ctx.reply(f"📘 認証ログチャンネルを **{ch.mention}** に設定しました！")

    # 認証パネル設置
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setverify(self, ctx):
        embed = discord.Embed(
            title="🔐 認証パネル",
            description="下のボタンを押して認証を完了してください！",
            color=0x00ffcc
        )

        button = Button(label="認証する", style=discord.ButtonStyle.green)
        
        async def button_callback(interaction: discord.Interaction):
            cfg = load_config()

            role_id = cfg.get("verify_role")
            if role_id is None:
                return await interaction.response.send_message("❌ 認証ロールが設定されていません！", ephemeral=True)

            role = interaction.guild.get_role(role_id)
            await interaction.user.add_roles(role)

            # ログ
            log_ch = cfg.get("verify_log")
            if log_ch:
                channel = interaction.guild.get_channel(log_ch)
                if channel:
                    await channel.send(f"✅ {interaction.user.mention} が認証しました。")

            await interaction.response.send_message("🎉 認証成功しました！", ephemeral=True)

        button.callback = button_callback
        view = View(timeout=None)
        view.add_item(button)

        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(VerifyCog(bot))
