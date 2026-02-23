import discord
import re
import os
import json
import io
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from scraper import scrape
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
WISHLIST_FILE = "/data/wishlist.json"

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True
client = discord.Client(intents=intents)

URL_REGEX = r"https?://[^\s]+"

# In-memory page trackers (per bot message)
pagination_sessions = {}


def normalize_url(raw: str) -> str:
    """
    Normalize URL for duplicate detection:
    - lower scheme/host
    - strip fragments
    - strip trailing slash
    - keep query (because it can matter for product variants)
    """
    try:
        raw = raw.strip()
        p = urlparse(raw)
        scheme = (p.scheme or "https").lower()
        netloc = p.netloc.lower()
        path = p.path.rstrip("/")  # remove trailing slash
        # strip fragment
        return urlunparse((scheme, netloc, path, p.params, p.query, ""))
    except Exception:
        return raw.strip()


def _load_store() -> dict:
    """
    Store shape:
      {
        "<channel_id>": [ {item}, {item}, ... ],
        ...
      }
    """
    if not os.path.exists(WISHLIST_FILE):
        return {}

    try:
        with open(WISHLIST_FILE, "r") as f:
            contents = f.read().strip()
            if not contents:
                return {}
            data = json.loads(contents)
            if isinstance(data, dict):
                return data
            # If old format was a list, don't crash; start fresh dict.
            return {}
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in wishlist store. Starting fresh.")
        return {}


def _save_store(store: dict) -> None:
    os.makedirs(os.path.dirname(WISHLIST_FILE), exist_ok=True)
    with open(WISHLIST_FILE, "w") as f:
        json.dump(store, f, indent=2)


def get_channel_wishlist(channel_id: int) -> list:
    store = _load_store()
    return store.get(str(channel_id), [])


def set_channel_wishlist(channel_id: int, wishlist: list) -> None:
    store = _load_store()
    store[str(channel_id)] = wishlist
    _save_store(store)


def clear_channel_wishlist(channel_id: int) -> None:
    store = _load_store()
    store[str(channel_id)] = []
    _save_store(store)


def has_duplicate(channel_id: int, url: str) -> bool:
    n = normalize_url(url)
    wishlist = get_channel_wishlist(channel_id)
    for item in wishlist:
        if normalize_url(item.get("url", "")) == n:
            return True
    return False


def save_item(channel_id: int, item: dict) -> None:
    wishlist = get_channel_wishlist(channel_id)

    item["timestamp"] = datetime.now().isoformat()
    wishlist.append(item)

    set_channel_wishlist(channel_id, wishlist)


def get_page_content(wishlist: list, page: int, items_per_page: int = 5):
    start = page * items_per_page
    end = start + items_per_page
    items = wishlist[start:end]
    total_pages = (len(wishlist) - 1) // items_per_page + 1 if wishlist else 1

    if not items:
        return "**🛒 This channel wishlist is empty.**", total_pages

    msg = f"**🛒 Wishlist Page {page + 1} of {total_pages} (This Channel)**\n"
    for item in items:
        title = item.get("title", "Unknown")
        price = item.get("price", "N/A")
        url = item.get("url", "")
        msg += f"• **{title}** – {price}\n<{url}>\n\n"
    return msg, total_pages


def is_admin_user(member: discord.Member) -> bool:
    # Admin-only as requested; using Manage Messages OR Administrator is practical.
    perms = member.guild_permissions
    return perms.administrator or perms.manage_messages


@client.event
async def on_ready():
    print(f"✅ Bot is live as {client.user}")


@client.event
async def on_message(message: discord.Message):
    # Ignore bot messages (including itself)
    if message.author.bot:
        return

    # Ignore DMs (server-only)
    if message.guild is None:
        return

    channel_id = message.channel.id
    content = message.content.strip()
    content_lower = content.lower()

    # ============ Commands (per-channel) ============

    # !wishlist (latest 5)
    if content_lower == "!wishlist":
        wishlist = get_channel_wishlist(channel_id)
        if not wishlist:
            await message.channel.send("📝 This channel wishlist is currently empty.")
            return

        last_items = wishlist[-5:]
        msg = "**🛒 Latest Wishlist Items (This Channel):**\n"
        for item in last_items:
            title = item.get("title", "Unknown")
            price = item.get("price", "N/A")
            url = item.get("url", "")
            msg += f"• **{title}** – {price}\n<{url}>\n\n"

        await message.channel.send(msg)
        return

    # !wishlist all (paginate)
    if content_lower == "!wishlist all":
        wishlist = get_channel_wishlist(channel_id)
        if not wishlist:
            await message.channel.send("📝 This channel wishlist is currently empty.")
            return

        page = 0
        page_content, total_pages = get_page_content(wishlist, page)

        bot_msg = await message.channel.send(page_content)
        if total_pages > 1:
            await bot_msg.add_reaction("⏮️")
            await bot_msg.add_reaction("⏭️")

            pagination_sessions[bot_msg.id] = {
                "user": message.author.id,
                "channel_id": channel_id,
                "page": page,
                "total_pages": total_pages,
                "message": bot_msg,
            }
        return

    # !wishlist export (uploads JSON file for THIS channel)
    if content_lower == "!wishlist export":
        wishlist = get_channel_wishlist(channel_id)
        if not wishlist:
            await message.channel.send("📝 This channel wishlist is currently empty.")
            return

        payload = json.dumps(wishlist, indent=2).encode("utf-8")
        buf = io.BytesIO(payload)
        filename = f"wishlist-{channel_id}.json"
        # Requires the bot to have permission to attach files in the channel
        await message.channel.send(
            content="📦 Export for this channel:",
            file=discord.File(fp=buf, filename=filename),
        )
        return

    # !wishlist clear (admin-only, clears THIS channel wishlist)
    if content_lower == "!wishlist clear":
        if not isinstance(message.author, discord.Member) or not is_admin_user(message.author):
            await message.channel.send("⛔ You don’t have permission to clear this channel’s wishlist.")
            return

        clear_channel_wishlist(channel_id)
        await message.channel.send("🧹 Cleared this channel’s wishlist.")
        return

    # ============ Link capture (per-channel, with duplicate detection) ============

    urls = re.findall(URL_REGEX, message.content)
    if not urls:
        return

    for url in urls:
        # Duplicate check per channel
        if has_duplicate(channel_id, url):
            await message.channel.send(f"🔁 Already in this channel wishlist:\n<{url}>")
            continue

        info = scrape(url)
        save_item(
            channel_id,
            {
                **info,
                "url": url,
                "user": str(message.author),
            },
        )

        embed = discord.Embed(
            title=info.get("title", "Item"),
            description=f"Posted by {message.author}",
            color=0x00FF00,
        )
        embed.add_field(name="Price", value=info.get("price", "N/A"), inline=True)
        embed.add_field(name="Link", value=f"[View Product]({url})", inline=False)
        await message.channel.send(embed=embed)


@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    if user.bot:
        return

    message = reaction.message
    if message.id not in pagination_sessions:
        return

    session = pagination_sessions[message.id]
    if user.id != session["user"]:
        return  # Only requester can paginate

    page = session["page"]
    total_pages = session["total_pages"]

    if reaction.emoji == "⏭️" and page < total_pages - 1:
        page += 1
    elif reaction.emoji == "⏮️" and page > 0:
        page -= 1
    else:
        return

    # Reload current channel wishlist (stays current)
    wishlist = get_channel_wishlist(session["channel_id"])
    new_content, new_total_pages = get_page_content(wishlist, page)

    session["page"] = page
    session["total_pages"] = new_total_pages

    await session["message"].edit(content=new_content)

    try:
        await message.remove_reaction(reaction.emoji, user)
    except discord.Forbidden:
        pass


client.run(TOKEN)
