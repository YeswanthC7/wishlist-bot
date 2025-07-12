import discord
import re
import os
import json
from scraper import scrape
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
WISHLIST_FILE = "wishlist.json"

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True  # Required for emoji pagination
intents.messages = True
client = discord.Client(intents=intents)

URL_REGEX = r"https?://[^\s]+"

# Save wishlist item
def save_item(data):
    wishlist = []
    if os.path.exists(WISHLIST_FILE):
        try:
            with open(WISHLIST_FILE, "r") as f:
                contents = f.read().strip()
                if contents:
                    wishlist = json.loads(contents)
        except json.JSONDecodeError:
            print("⚠️ Invalid JSON. Starting fresh.")
    data["timestamp"] = datetime.now().isoformat()
    wishlist.append(data)
    with open(WISHLIST_FILE, "w") as f:
        json.dump(wishlist, f, indent=2)

# In-memory page trackers
pagination_sessions = {}

# Format wishlist page
def get_page_content(wishlist, page, items_per_page=5):
    start = page * items_per_page
    end = start + items_per_page
    items = wishlist[start:end]
    total_pages = (len(wishlist) - 1) // items_per_page + 1

    if not items:
        return "**🛒 Your wishlist is empty.**", total_pages

    msg = f"**🛒 Wishlist Page {page + 1} of {total_pages}**\n"
    for item in items:
        title = item.get("title", "Unknown")
        price = item.get("price", "N/A")
        url = item.get("url", "")
        msg += f"• **{title}** – {price}\n<{url}>\n\n"
    return msg, total_pages

@client.event
async def on_ready():
    print(f"✅ Bot is live as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != CHANNEL_ID or message.author == client.user:
        return

    # ==== !wishlist latest ====
    if message.content.strip().lower() == "!wishlist":
        if not os.path.exists(WISHLIST_FILE):
            await message.channel.send("📝 Your wishlist is currently empty.")
            return
        with open(WISHLIST_FILE, "r") as f:
            wishlist = json.load(f)
        last_items = wishlist[-5:]
        msg = "**🛒 Your Latest Wishlist Items:**\n"
        for item in last_items:
            title = item.get("title", "Unknown")
            price = item.get("price", "N/A")
            url = item.get("url", "")
            msg += f"• **{title}** – {price}\n<{url}>\n\n"
        await message.channel.send(msg)
        return

    # ==== !wishlist all ====
    if message.content.strip().lower() == "!wishlist all":
        if not os.path.exists(WISHLIST_FILE):
            await message.channel.send("📝 Your wishlist is currently empty.")
            return
        with open(WISHLIST_FILE, "r") as f:
            wishlist = json.load(f)

        page = 0
        content, total_pages = get_page_content(wishlist, page)

        bot_msg = await message.channel.send(content)
        if total_pages > 1:
            await bot_msg.add_reaction("⏮️")
            await bot_msg.add_reaction("⏭️")

            pagination_sessions[bot_msg.id] = {
                "user": message.author.id,
                "wishlist": wishlist,
                "page": page,
                "total_pages": total_pages,
                "message": bot_msg
            }
        return

    # ==== Scrape product URLs ====
    urls = re.findall(URL_REGEX, message.content)
    if not urls:
        return
    for url in urls:
        info = scrape(url)
        save_item({
            **info,
            "url": url,
            "user": str(message.author)
        })
        embed = discord.Embed(
            title=info["title"],
            description=f"Posted by {message.author}",
            color=0x00ff00
        )
        embed.add_field(name="Price", value=info["price"], inline=True)
        embed.add_field(name="Link", value=f"[View Product]({url})", inline=False)
        await message.channel.send(embed=embed)

# ==== Pagination reaction handling ====
@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return

    message = reaction.message
    if message.id not in pagination_sessions:
        return

    session = pagination_sessions[message.id]
    if user.id != session["user"]:
        return  # Only the requester can paginate their session

    if reaction.emoji == "⏭️" and session["page"] < session["total_pages"] - 1:
        session["page"] += 1
    elif reaction.emoji == "⏮️" and session["page"] > 0:
        session["page"] -= 1
    else:
        return

    new_content, _ = get_page_content(session["wishlist"], session["page"])
    await session["message"].edit(content=new_content)
    try:
        await message.remove_reaction(reaction.emoji, user)
    except discord.Forbidden:
        pass

client.run(TOKEN)
