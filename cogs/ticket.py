# cogs/ticket.py
import discord
from discord.ext import commands
from discord.ui import View, Button
import json
import os
from datetime import datetime, timezone
import html
import pathlib
import traceback

CONFIG_FILE = "ticket_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default = {
            "log_channel_id": None,
            "ticket_count": 0,
            "tickets": {},  # channel_id -> {owner_id, number, state, created_at}
            "verify_role_id": None,
            "ticket_category_id": None,
            "admin_role_ids": [],  # 管理者ロールIDリスト
            "whitelist_user_ids": []  # 個別ホワイトリストユーID
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# -------------------------
# Embed デザイン（UI は変えない）
# -------------------------
def embed_ticket_created(owner: discord.Member, ticket_no: int):
    e = discord.Embed(
        title="📩 チケットが作成されました",
        description=f"{owner.mention} さんのサポートチケットです。\n運営が対応します。",
        color=0x5865F2
    )
    e.add_field(name="チケット番号", value=str(ticket_no))
    e.set_footer(text=f"作成: {datetime.now(timezone.utc).isoformat()} (UTC)")
    return e

def embed_ticket_closed(owner: discord.Member, ticket_no: int):
    e = discord.Embed(
        title="🔐 チケットがクローズされました",
        description=f"{owner.mention} さんのチケットはクローズされました。\n運営は保存/再開/削除ができます。",
        color=0xE67E22
    )
    e.add_field(name="チケット番号", value=str(ticket_no))
    e.set_footer(text=f"操作: {datetime.now(timezone.utc).isoformat()} (UTC)")
    return e

def embed_save_complete(owner: discord.Member, ticket_no: int):
    e = discord.Embed(
        title="💾 ログを保存しました",
        description=f"チケット {ticket_no} のログを保存・送信しました。",
        color=0x2ECC71
    )
    e.set_footer(text=f"保存: {datetime.now(timezone.utc).isoformat()} (UTC)")
    return e

def embed_log_notify(action: str, owner: discord.Member, ticket_no: int, channel: discord.TextChannel):
    e = discord.Embed(
        title=f"📤 Ticket Log - {action}",
        description=f"チケット {ticket_no} ({channel.mention}) にて `{action}` が実行されました。",
        color=0x95A5A6
    )
    e.add_field(name="ユーザー", value=f"{owner} ({owner.id})", inline=False)
    e.add_field(name="チャンネル", value=f"{channel.name} ({channel.id})", inline=False)
    e.set_footer(text=f"{datetime.now(timezone.utc).isoformat()} (UTC)")
    return e

# -------------------------
# Cog 実装
# -------------------------
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- helper ----------
    def has_admin_role_member(self, member: discord.Member):
        try:
            cfg = load_config()
            admin_ids = cfg.get("admin_role_ids", []) or []
            for r in member.roles:
                if r.id in admin_ids:
                    return True
            if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
                return True
            if member.id in cfg.get("whitelist_user_ids", []):
                return True
        except Exception:
            traceback.print_exc()
        return False

    # ---------- Views / Buttons ----------
    class VerifyButton(Button):
        def __init__(self):
            super().__init__(label="認証する", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            try:
                cfg = load_config()
                role_id = cfg.get("verify_role_id")
                if not role_id:
                    await interaction.response.send_message("認証ロールが未設定です。管理者に連絡してください。", ephemeral=True)
                    return
                role = interaction.guild.get_role(role_id)
                if role is None:
                    await interaction.response.send_message("認証ロールが見つかりません。管理者に連絡してください。", ephemeral=True)
                    return
                if role in interaction.user.roles:
                    await interaction.response.send_message("すでに認証済みです！", ephemeral=True)
                    return
                await interaction.user.add_roles(role)
                await interaction.response.send_message("認証しました！", ephemeral=True)
            except Exception:
                traceback.print_exc()
                await interaction.response.send_message("認証中にエラーが発生しました。", ephemeral=True)

    class VerifyView(View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(TicketCog.VerifyButton())

    class TicketCreateButton(Button):
        def __init__(self):
            super().__init__(label="🎫 チケットを作成", style=discord.ButtonStyle.blurple)

        async def callback(self, interaction: discord.Interaction):
            try:
                cfg = load_config()
                cat_id = cfg.get("ticket_category_id")
                if not cat_id:
                    await interaction.response.send_message("チケットカテゴリが未設定です。管理者に連絡してください。", ephemeral=True)
                    return
                guild = interaction.guild
                category = guild.get_channel(cat_id)
                if category is None or not isinstance(category, discord.CategoryChannel):
                    await interaction.response.send_message("チケットカテゴリが見つかりません。管理者に連絡してください。", ephemeral=True)
                    return

                # チケット番号
                cfg["ticket_count"] = cfg.get("ticket_count", 0) + 1
                ticket_no = cfg["ticket_count"]
                save_config(cfg)

                owner = interaction.user
                safe_name = owner.name.replace(" ", "-")[:20]
                channel_name = f"ticket-{ticket_no}-{safe_name}"

                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    owner: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                }
                for rid in cfg.get("admin_role_ids", []):
                    r = guild.get_role(rid)
                    if r:
                        overwrites[r] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

                channel = await category.create_text_channel(channel_name, overwrites=overwrites)

                # config 登録
                cfg = load_config()
                cfg.setdefault("tickets", {})
                cfg["tickets"][str(channel.id)] = {
                    "owner_id": owner.id,
                    "number": ticket_no,
                    "state": "open",
                    "created_at": datetime.utcnow().isoformat()
                }
                save_config(cfg)

                # チケット作成Embed + 管理View を送る
                embed = embed_ticket_created(owner, ticket_no)
                view = TicketCog.TicketManageView(is_open=True)
                await channel.send(embed=embed, view=view)

                # ログチャンネル通知（作成）
                await TicketCog.notify_log_channel_static(guild, "Ticket Created", owner, ticket_no, channel)

                await interaction.response.send_message("チケットを作成しました！", ephemeral=True)
            except Exception:
                traceback.print_exc()
                await interaction.response.send_message("チケット作成中にエラーが発生しました。", ephemeral=True)

    class TicketView(View):
        def __init__(self):
            super().__init__(timeout=None)
            self.add_item(TicketCog.TicketCreateButton())

    class CloseButton(Button):
        def __init__(self):
            super().__init__(label="🔐 クローズする", style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            self_cog = interaction.client.get_cog("TicketCog")
            try:
                if not self_cog.has_admin_role_member(interaction.user):
                    await interaction.response.send_message("管理者のみがクローズできます。", ephemeral=True)
                    return
                channel = interaction.channel
                cfg = load_config()
                ticket = cfg.get("tickets", {}).get(str(channel.id))
                if not ticket:
                    await interaction.response.send_message("これはチケットチャンネルではありません。", ephemeral=True)
                    return

                guild = interaction.guild
                owner = guild.get_member(ticket["owner_id"])
                try:
                    if owner:
                        await channel.set_permissions(owner, read_messages=False, send_messages=False)
                except Exception:
                    pass

                ticket["state"] = "closed"
                save_config(cfg)

                view = TicketCog.TicketManageView(is_open=False)
                embed = embed_ticket_closed(owner if owner else interaction.user, ticket["number"])
                await channel.send(embed=embed, view=view)

                await TicketCog.notify_log_channel_static(guild, "Ticket Closed", owner if owner else interaction.user, ticket["number"], channel)

                await interaction.response.send_message("チケットをクローズしました。", ephemeral=True)
            except Exception:
                traceback.print_exc()
                await interaction.response.send_message("クローズ中にエラーが発生しました。", ephemeral=True)

    class SaveButton(Button):
        def __init__(self):
            super().__init__(label="💾 保存（HTML）", style=discord.ButtonStyle.gray)

        async def callback(self, interaction: discord.Interaction):
            self_cog = interaction.client.get_cog("TicketCog")
            try:
                if not self_cog.has_admin_role_member(interaction.user):
                    await interaction.response.send_message("管理者のみが保存できます。", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                channel = interaction.channel
                cfg = load_config()
                ticket = cfg.get("tickets", {}).get(str(channel.id))
                if not ticket:
                    await interaction.followup.send("これはチケットチャンネルではありません。", ephemeral=True)
                    return
                try:
                    file_path = await TicketCog.generate_html_log_static(channel)
                    log_id = cfg.get("log_channel_id")
                    if log_id:
                        guild = interaction.guild
                        log_chan = guild.get_channel(log_id)
                        if log_chan:
                            await log_chan.send(file=discord.File(file_path), embed=embed_log_notify("Saved (HTML)", guild.get_member(ticket["owner_id"]) or interaction.user, ticket["number"], channel))
                    try:
                        owner = interaction.guild.get_member(ticket["owner_id"])
                    except Exception:
                        owner = interaction.user
                    await channel.send(embed=embed_save_complete(owner, ticket["number"]))
                    await interaction.followup.send("HTMLログを作成して送信しました。", ephemeral=True)
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                    await TicketCog.notify_log_channel_static(interaction.guild, "Ticket Saved", owner, ticket["number"], channel)
                except Exception:
                    traceback.print_exc()
                    await interaction.followup.send("ログ保存中にエラーが発生しました。", ephemeral=True)
            except Exception:
                traceback.print_exc()
                await interaction.response.send_message("保存処理でエラーが発生しました。", ephemeral=True)

    class ReopenButton(Button):
        def __init__(self):
            super().__init__(label="♻ 再開", style=discord.ButtonStyle.green)

        async def callback(self, interaction: discord.Interaction):
            self_cog = interaction.client.get_cog("TicketCog")
            try:
                if not self_cog.has_admin_role_member(interaction.user):
                    await interaction.response.send_message("管理者のみが再開できます。", ephemeral=True)
                    return
                channel = interaction.channel
                cfg = load_config()
                ticket = cfg.get("tickets", {}).get(str(channel.id))
                if not ticket:
                    await interaction.response.send_message("これはチケットチャンネルではありません。", ephemeral=True)
                    return
                guild = interaction.guild
                owner = guild.get_member(ticket["owner_id"])
                try:
                    if owner:
                        await channel.set_permissions(owner, read_messages=True, send_messages=True)
                except Exception:
                    pass
                ticket["state"] = "open"
                save_config(cfg)
                view = TicketCog.TicketManageView(is_open=True)
                await channel.send("チケットを再開しました。", view=view)
                await TicketCog.notify_log_channel_static(guild, "Ticket Reopened", owner if owner else interaction.user, ticket["number"], channel)
                await interaction.response.send_message("チケットを再開しました。", ephemeral=True)
            except Exception:
                traceback.print_exc()
                await interaction.response.send_message("再開処理でエラーが発生しました。", ephemeral=True)

    class DeleteButton(Button):
        def __init__(self):
            super().__init__(label="❌ 削除", style=discord.ButtonStyle.danger)

        async def callback(self, interaction: discord.Interaction):
            self_cog = interaction.client.get_cog("TicketCog")
            try:
                if not self_cog.has_admin_role_member(interaction.user):
                    await interaction.response.send_message("管理者のみが削除できます。", ephemeral=True)
                    return
                channel = interaction.channel
                cfg = load_config()
                ticket = cfg.get("tickets", {}).get(str(channel.id))
                if not ticket:
                    await interaction.response.send_message("これはチケットチャンネルではありません。", ephemeral=True)
                    return

                try:
                    file_path = await TicketCog.generate_html_log_static(channel)
                    log_id = cfg.get("log_channel_id")
                    if log_id:
                        log_chan = interaction.guild.get_channel(log_id)
                        if log_chan:
                            await log_chan.send(file=discord.File(file_path), embed=embed_log_notify("Deleted (Saved)", interaction.guild.get_member(ticket["owner_id"]) or interaction.user, ticket["number"], channel))
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                except Exception:
                    traceback.print_exc()

                try:
                    del cfg["tickets"][str(channel.id)]
                    save_config(cfg)
                except Exception:
                    pass

                await TicketCog.notify_log_channel_static(interaction.guild, "Ticket Deleted", interaction.guild.get_member(ticket["owner_id"]) or interaction.user, ticket["number"], channel)
                await channel.delete()
            except Exception:
                traceback.print_exc()
                await interaction.response.send_message("削除処理でエラーが発生しました。", ephemeral=True)

    class TicketManageView(View):
        def __init__(self, is_open: bool = True):
            super().__init__(timeout=None)
            if is_open:
                self.add_item(TicketCog.CloseButton())
            else:
                self.add_item(TicketCog.SaveButton())
                self.add_item(TicketCog.ReopenButton())
                self.add_item(TicketCog.DeleteButton())

    # -------------------------
    # static helper functions for use in inner classes
    # -------------------------
    @staticmethod
    async def generate_html_log_static(channel: discord.TextChannel) -> str:
        messages = []
        async for m in channel.history(limit=None, oldest_first=True):
            messages.append(m)
        safe_channel_name = f"{channel.name}-{int(datetime.utcnow().timestamp())}"
        filename = f"ticket_{safe_channel_name}.html"
        lines = []
        lines.append("<!doctype html>")
        lines.append("<html><head><meta charset='utf-8'><title>Ticket Log</title></head><body>")
        lines.append(f"<h2>Channel: {html.escape(channel.name)}</h2>")
        lines.append(f"<h3>Exported: {datetime.utcnow().isoformat()} (UTC)</h3>")
        lines.append("<hr>")
        for m in messages:
            t = m.created_at.isoformat()
            author = html.escape(f"{m.author} ({m.author.id})")
            content = html.escape(m.content) if m.content else ""
            att_html = ""
            if m.attachments:
                for a in m.attachments:
                    url = html.escape(a.url)
                    att_html += f"<div>Attachment: <a href='{url}' target='_blank'>{url}</a></div>"
            embed_info = ""
            if m.embeds:
                embed_info = "<div>Embed present</div>"
            lines.append("<div style='margin-bottom:12px;padding:8px;border:1px solid #ddd;'>")
            lines.append(f"<div style='color:#666;font-size:12px;'>[{t}] {author}</div>")
            if content:
                text_html = "<br>".join(html.escape(part) for part in m.content.splitlines())
                lines.append(f"<div style='margin-top:6px;'>{text_html}</div>")
            if att_html:
                lines.append(att_html)
            if embed_info:
                lines.append(embed_info)
            lines.append("</div>")
        lines.append("</body></html>")
        path = pathlib.Path(filename)
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path.resolve())

    @staticmethod
    async def notify_log_channel_static(guild: discord.Guild, action: str, owner: discord.Member, ticket_no: int, channel: discord.TextChannel):
        try:
            cfg = load_config()
            log_id = cfg.get("log_channel_id")
            if not log_id:
                return
            log_chan = guild.get_channel(log_id)
            if not log_chan:
                return
            embed = embed_log_notify(action, owner, ticket_no, channel)
            await log_chan.send(embed=embed)
        except Exception:
            traceback.print_exc()

    # -------------------------
    # 管理用コマンド群（ロール管理 / 設定）
    # -------------------------
    @commands.group(invoke_without_command=True)
    async def ticketadmin(self, ctx):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        await ctx.send("サブコマンド: addrole / removerole / list")

    @ticketadmin.command()
    async def addrole(self, ctx, role: discord.Role):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        rid = role.id
        if rid in cfg.get("admin_role_ids", []):
            await ctx.send("このロールはすでに管理者ロールです。")
            return
        cfg.setdefault("admin_role_ids", []).append(rid)
        save_config(cfg)
        await ctx.send(f"{role.mention} を管理者ロールに追加しました。")

    @ticketadmin.command()
    async def removerole(self, ctx, role: discord.Role):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        rid = role.id
        if rid not in cfg.get("admin_role_ids", []):
            await ctx.send("そのロールは管理者ロールではありません。")
            return
        cfg["admin_role_ids"].remove(rid)
        save_config(cfg)
        await ctx.send(f"{role.mention} を管理者ロールから削除しました。")

    @ticketadmin.command()
    async def list(self, ctx):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        ids = cfg.get("admin_role_ids", [])
        if not ids:
            await ctx.send("管理者ロールは未設定です。サーバー管理権限を持つユーザーはデフォルトで管理可能です。")
            return
        mentions = []
        for rid in ids:
            r = ctx.guild.get_role(rid)
            mentions.append(r.mention if r else f"(ID:{rid})")
        await ctx.send("管理者ロール: " + ", ".join(mentions))
    

    @commands.command()
    async def setticketcat(self, ctx, category: discord.CategoryChannel):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        cfg["ticket_category_id"] = category.id
        save_config(cfg)
        await ctx.send(f"チケットカテゴリを {category.name} に設定しました。")

    @commands.command()
    async def ticketlogset(self, ctx):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        cfg["log_channel_id"] = ctx.channel.id
        save_config(cfg)
        await ctx.send(f"このチャンネル ({ctx.channel.mention}) をチケットログ送信先に設定しました。")

    @commands.command()
    async def whitelist_add(self, ctx, member: discord.Member):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        if member.id in cfg.get("whitelist_user_ids", []):
            await ctx.send("既にホワイトリストに存在します。")
            return
        cfg.setdefault("whitelist_user_ids", []).append(member.id)
        save_config(cfg)
        await ctx.send(f"{member.mention} をホワイトリストに追加しました。")

    @commands.command()
    async def whitelist_remove(self, ctx, member: discord.Member):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        cfg = load_config()
        if member.id not in cfg.get("whitelist_user_ids", []):
            await ctx.send("ホワイトリストに存在しません。")
            return
        cfg["whitelist_user_ids"].remove(member.id)
        save_config(cfg)
        await ctx.send(f"{member.mention} をホワイトリストから削除しました。")

    @commands.command()
    async def setverify(self, ctx):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        embed = discord.Embed(title="認証パネル", description="下のボタンを押して認証してください！", color=0x00ff00)
        await ctx.channel.send(embed=embed, view=TicketCog.VerifyView())

    @commands.command()
    async def setticket(self, ctx):
        if not self.has_admin_role_member(ctx.author):
            await ctx.send("権限がありません。")
            return
        embed = discord.Embed(title="サポートチケット", description="チケットを作成するには下のボタンを押してください。", color=0x5865F2)
        await ctx.channel.send(embed=embed, view=TicketCog.TicketView())

# -------------------------
# Cog setup
# -------------------------
async def setup(bot):
    await bot.add_cog(TicketCog(bot))



