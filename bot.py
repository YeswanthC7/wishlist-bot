import discord
import re
import os
import json
import io
import math
from urllib.parse import urlparse, urlunparse
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from scraper import scrape

from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError

from db.session import SessionLocal
from db.models import ChannelConfig, WishlistItem

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

# If true, the bot will sync slash commands on startup.
# Prefer leaving this OFF in production unless you are intentionally syncing. :contentReference[oaicite:1]{index=1}
SYNC_COMMANDS = os.getenv("SYNC_COMMANDS", "false").lower() in ("1", "true", "yes")

# Optional: if set, sync commands instantly to a single guild (fast iteration).
# Provide a guild ID string like "123456789012345678".
SYNC_GUILD_ID = os.getenv("SYNC_GUILD_ID")

URL_REGEX = r"https?://[^\s]+"

intents = discord.Intents.default()
intents.message_content = True  # needed for URL capture from messages
intents.messages = True


def normalize_url(raw: str) -> str:
    """
    Normalize URL for duplicate detection:
    - lower scheme/host
    - strip fragments
    - strip trailing slash
    - keep query
    """
    try:
        raw = raw.strip()
        p = urlparse(raw)
        scheme = (p.scheme or "https").lower()
        netloc = p.netloc.lower()
        path = p.path.rstrip("/")
        return urlunparse((scheme, netloc, path, p.params, p.query, ""))  # strip fragment
    except Exception:
        return raw.strip()


def is_admin_member(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return perms.administrator or perms.manage_messages


def is_capture_enabled(guild_id: str, channel_id: str) -> bool:
    """
    If no row exists, default to enabled (preserve current behavior).
    """
    with SessionLocal() as db:
        row = db.execute(
            select(ChannelConfig.enabled).where(
                ChannelConfig.guild_id == str(guild_id),
                ChannelConfig.channel_id == str(channel_id),
            )
        ).first()
        return True if row is None else bool(row[0])


def set_capture_enabled(guild_id: str, channel_id: str, enabled: bool) -> None:
    with SessionLocal() as db:
        row = db.execute(
            select(ChannelConfig).where(
                ChannelConfig.guild_id == str(guild_id),
                ChannelConfig.channel_id == str(channel_id),
            )
        ).scalar_one_or_none()

        if row is None:
            db.add(ChannelConfig(guild_id=str(guild_id), channel_id=str(channel_id), enabled=enabled))
        else:
            row.enabled = enabled
        db.commit()


def has_duplicate_db(channel_id: str, url: str) -> bool:
    n = normalize_url(url)
    with SessionLocal() as db:
        row = db.execute(
            select(WishlistItem.id).where(
                WishlistItem.channel_id == str(channel_id),
                WishlistItem.url_norm == n,
            )
        ).first()
        return row is not None


def save_item_db(
    guild_id: str,
    channel_id: str,
    url: str,
    title: str,
    price: Optional[str],
    user_tag: Optional[str],
) -> None:
    with SessionLocal() as db:
        try:
            db.add(
                WishlistItem(
                    guild_id=str(guild_id),
                    channel_id=str(channel_id),
                    url=url,
                    url_norm=normalize_url(url),
                    title=title or "Unknown",
                    price=price,
                    user_tag=user_tag,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise


def count_items_db(guild_id: str, channel_id: str) -> int:
    with SessionLocal() as db:
        n = db.execute(
            select(func.count()).select_from(WishlistItem).where(
                WishlistItem.guild_id == str(guild_id),
                WishlistItem.channel_id == str(channel_id),
            )
        ).scalar_one()
        return int(n)


def get_latest_items_db(guild_id: str, channel_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            select(
                WishlistItem.title,
                WishlistItem.price,
                WishlistItem.url,
                WishlistItem.user_tag,
                WishlistItem.created_at,
            )
            .where(
                WishlistItem.guild_id == str(guild_id),
                WishlistItem.channel_id == str(channel_id),
            )
            .order_by(WishlistItem.created_at.desc())
            .limit(limit)
        ).all()

        out: List[Dict[str, Any]] = []
        for title, price, url, user_tag, created_at in rows:
            out.append(
                {
                    "title": title,
                    "price": price,
                    "url": url,
                    "user": user_tag,
                    "timestamp": created_at.isoformat() if created_at else None,
                }
            )
        return out


def get_page_items_db(
    guild_id: str,
    channel_id: str,
    page: int,
    items_per_page: int = 5,
) -> tuple[List[Dict[str, Any]], int]:
    total_items = count_items_db(guild_id, channel_id)
    total_pages = max(1, math.ceil(total_items / items_per_page))
    page = max(0, min(page, total_pages - 1))
    offset = page * items_per_page

    with SessionLocal() as db:
        rows = db.execute(
            select(
                WishlistItem.title,
                WishlistItem.price,
                WishlistItem.url,
                WishlistItem.user_tag,
                WishlistItem.created_at,
            )
            .where(
                WishlistItem.guild_id == str(guild_id),
                WishlistItem.channel_id == str(channel_id),
            )
            .order_by(WishlistItem.created_at.desc())
            .offset(offset)
            .limit(items_per_page)
        ).all()

        items: List[Dict[str, Any]] = []
        for title, price, url, user_tag, created_at in rows:
            items.append(
                {
                    "title": title,
                    "price": price,
                    "url": url,
                    "user": user_tag,
                    "timestamp": created_at.isoformat() if created_at else None,
                }
            )

    return items, total_pages


def export_channel_db(guild_id: str, channel_id: str) -> List[Dict[str, Any]]:
    with SessionLocal() as db:
        rows = db.execute(
            select(
                WishlistItem.title,
                WishlistItem.price,
                WishlistItem.url,
                WishlistItem.user_tag,
                WishlistItem.created_at,
            )
            .where(
                WishlistItem.guild_id == str(guild_id),
                WishlistItem.channel_id == str(channel_id),
            )
            .order_by(WishlistItem.created_at.asc())
        ).all()

        out: List[Dict[str, Any]] = []
        for title, price, url, user_tag, created_at in rows:
            out.append(
                {
                    "title": title,
                    "price": price,
                    "url": url,
                    "user": user_tag,
                    "timestamp": created_at.isoformat() if created_at else None,
                }
            )
        return out


def clear_channel_db(guild_id: str, channel_id: str) -> int:
    with SessionLocal() as db:
        res = db.execute(
            delete(WishlistItem).where(
                WishlistItem.guild_id == str(guild_id),
                WishlistItem.channel_id == str(channel_id),
            )
        )
        db.commit()
        return int(res.rowcount or 0)


def render_items(items: List[Dict[str, Any]], page: int, total_pages: int) -> str:
    if not items:
        return "**🛒 This channel wishlist is empty.**"
    msg = f"**🛒 Wishlist Page {page + 1} of {total_pages} (This Channel)**\n\n"
    for it in items:
        title = it.get("title") or "Unknown"
        price = it.get("price") or "N/A"
        url = it.get("url") or ""
        msg += f"• **{title}** – {price}\n<{url}>\n\n"
    return msg


class WishlistPager(discord.ui.View):
    """
    Button-based pagination for /wishlist all.
    Uses interaction edits, with a simple interaction check so only the requester can paginate.
    (Pattern: interaction_check + edit_message) :contentReference[oaicite:2]{index=2}
    """
    def __init__(
        self,
        requester_id: int,
        guild_id: str,
        channel_id: str,
        page: int,
        total_pages: int,
        items_per_page: int = 5,
        timeout: float = 180.0,
    ):
        super().__init__(timeout=timeout)
        self.requester_id = requester_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.page = page
        self.total_pages = total_pages
        self.items_per_page = items_per_page
        self._refresh_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester_id:
            await interaction.response.send_message("You can’t control someone else’s wishlist view.", ephemeral=True)
            return False
        return True

    def _refresh_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "prev":
                    child.disabled = self.page <= 0
                elif child.custom_id == "next":
                    child.disabled = self.page >= (self.total_pages - 1)

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        items, total_pages = get_page_items_db(self.guild_id, self.channel_id, self.page, self.items_per_page)
        self.total_pages = total_pages
        self._refresh_buttons()
        await interaction.response.edit_message(content=render_items(items, self.page, self.total_pages), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.total_pages - 1, self.page + 1)
        items, total_pages = get_page_items_db(self.guild_id, self.channel_id, self.page, self.items_per_page)
        self.total_pages = total_pages
        self._refresh_buttons()
        await interaction.response.edit_message(content=render_items(items, self.page, self.total_pages), view=self)

    async def on_timeout(self) -> None:
        # disable buttons on timeout
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        # If you want, you can also attempt to edit the message here,
        # but we don't store the message object to keep it minimal.


class WishlistGroup(discord.app_commands.Group):
    """
    /wishlist ... command group (subcommands). :contentReference[oaicite:3]{index=3}
    """
    def __init__(self):
        super().__init__(name="wishlist", description="Wishlist commands for this channel")

    @discord.app_commands.command(name="latest", description="Show the latest wishlist items for this channel")
    @discord.app_commands.guild_only()
    async def latest(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        items = get_latest_items_db(guild_id, channel_id, limit=5)
        if not items:
            await interaction.response.send_message("📝 This channel wishlist is currently empty.")
            return

        # Show oldest->newest within the last 5
        msg = "**🛒 Latest Wishlist Items (This Channel):**\n\n"
        for it in reversed(items):
            title = it.get("title") or "Unknown"
            price = it.get("price") or "N/A"
            url = it.get("url") or ""
            msg += f"• **{title}** – {price}\n<{url}>\n\n"
        await interaction.response.send_message(msg)

    @discord.app_commands.command(name="all", description="Browse all wishlist items for this channel")
    @discord.app_commands.guild_only()
    async def all(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        items, total_pages = get_page_items_db(guild_id, channel_id, page=0, items_per_page=5)
        if not items:
            await interaction.response.send_message("📝 This channel wishlist is currently empty.")
            return

        view = WishlistPager(
            requester_id=interaction.user.id,
            guild_id=guild_id,
            channel_id=channel_id,
            page=0,
            total_pages=total_pages,
            items_per_page=5,
        )
        await interaction.response.send_message(content=render_items(items, 0, total_pages), view=view)

    @discord.app_commands.command(name="export", description="Export this channel wishlist as a JSON file")
    @discord.app_commands.guild_only()
    async def export(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        data = export_channel_db(guild_id, channel_id)
        if not data:
            await interaction.response.send_message("📝 This channel wishlist is currently empty.")
            return

        payload = json.dumps(data, indent=2).encode("utf-8")
        buf = io.BytesIO(payload)
        filename = f"wishlist-{channel_id}.json"

        await interaction.response.send_message(
            content="📦 Export for this channel:",
            file=discord.File(fp=buf, filename=filename),
        )

    @discord.app_commands.command(name="clear", description="Admin-only: clear this channel wishlist")
    @discord.app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_admin_member(interaction.user):
            await interaction.response.send_message(
                "⛔ You don’t have permission to clear this channel’s wishlist.",
                ephemeral=True,
            )
            return

        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)
        deleted = clear_channel_db(guild_id, channel_id)
        await interaction.response.send_message(f"🧹 Cleared this channel’s wishlist. ({deleted} items removed)")

    @discord.app_commands.command(name="enable", description="Admin-only: enable wishlist capture in this channel")
    @discord.app_commands.guild_only()
    async def enable(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_admin_member(interaction.user):
            await interaction.response.send_message("⛔ Admin-only command.", ephemeral=True)
            return
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)
        set_capture_enabled(guild_id, channel_id, True)
        await interaction.response.send_message("✅ Wishlist capture enabled for this channel.", ephemeral=True)

    @discord.app_commands.command(name="disable", description="Admin-only: disable wishlist capture in this channel")
    @discord.app_commands.guild_only()
    async def disable(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not is_admin_member(interaction.user):
            await interaction.response.send_message("⛔ Admin-only command.", ephemeral=True)
            return
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)
        set_capture_enabled(guild_id, channel_id, False)
        await interaction.response.send_message("🛑 Wishlist capture disabled for this channel.", ephemeral=True)


class WishlistBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        # Add /wishlist group + subcommands. :contentReference[oaicite:4]{index=4}
        self.tree.add_command(WishlistGroup())

        if SYNC_COMMANDS:
            # Sync commands either globally (slow propagation) or to a single guild (fast). :contentReference[oaicite:5]{index=5}
            if SYNC_GUILD_ID:
                guild = discord.Object(id=int(SYNC_GUILD_ID))
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                print(f"✅ Synced commands to guild {SYNC_GUILD_ID}")
            else:
                await self.tree.sync()
                print("✅ Synced commands globally")

    async def on_ready(self):
        print(f"✅ Bot is live as {self.user}")

    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore DMs
        if message.guild is None:
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        # Capture gating (default enabled)
        if not is_capture_enabled(guild_id, channel_id):
            return

        urls = re.findall(URL_REGEX, message.content)
        if not urls:
            return

        for url in urls:
            # DB duplicate check before scraping
            if has_duplicate_db(channel_id, url):
                await message.channel.send(f"🔁 Already in this channel wishlist:\n<{url}>")
                continue

            info = scrape(url)

            try:
                save_item_db(
                    guild_id=guild_id,
                    channel_id=channel_id,
                    url=url,
                    title=info.get("title", "Unknown"),
                    price=info.get("price"),
                    user_tag=str(message.author),
                )
            except IntegrityError:
                # Race condition between check and insert
                await message.channel.send(f"🔁 Already in this channel wishlist:\n<{url}>")
                continue

            embed = discord.Embed(
                title=info.get("title", "Item"),
                description=f"Posted by {message.author}",
                color=0x00FF00,
            )
            embed.add_field(name="Price", value=info.get("price", "N/A"), inline=True)
            embed.add_field(name="Link", value=f"[View Product]({url})", inline=False)
            await message.channel.send(embed=embed)


bot = WishlistBot()
bot.run(TOKEN)
