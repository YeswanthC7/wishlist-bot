# WishlistBot

WishlistBot is a Discord bot designed to help users curate, manage, and track their product wishlists directly within a Discord channel. Users can drop product links, and the bot will scrape essential details such as the product title and price, storing them in a persistent wishlist. It also supports easy retrieval and browsing of saved wishlist items with intuitive pagination.

---

## Features

- **Add Wishlist Items**  
  Drop any product URL (Amazon, Puma, Nike, or any website). The bot automatically scrapes product information and saves it.

- **View Latest Wishlist Items**  
  Use the command `!wishlist` to view the latest 5 items you added to your wishlist.

- **View Full Wishlist with Pagination**  
  Use `!wishlist all` to view your entire wishlist, displayed in pages of 5 items each. Navigate pages using reactions ⏮️ (previous) and ⏭️ (next).

- **Clean Discord Embeds**  
  When you add a product link, the bot replies with a neat embedded message showing the product title, price, and link.

- **User-specific Pagination**  
  Pagination sessions are tracked per user to ensure that only the requester can navigate through their wishlist pages.

---

## How to Use

### Step 1: Set up your Discord Bot and Environment

1. **Create a Discord bot application**  
   - Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.  
   - Add a bot user to your application and get the bot token.

2. **Invite the bot to your server**  
   - Generate an OAuth2 invite URL with the `bot` scope and the permissions to read/send messages, embed links, and add reactions.  
   - Use this URL to invite the bot to your desired Discord server.

3. **Enable Developer Mode on Discord** (to get Channel ID)  
   - Go to User Settings → Advanced → Enable Developer Mode.  
   - Right-click your target wishlist channel and click "Copy ID".

4. **Create a `.env` file in your project root** with these entries:  

DISCORD_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here

---

### Step 2: Install dependencies

Make sure you have Python 3.8+ installed, then install required packages:

```bash
pip install -r requirements.txt


(Requirements include: discord.py, requests, beautifulsoup4, python-dotenv)


Step 3: Run the bot

Simply run:

python bot.py

The bot will connect to Discord and be ready to use in your specified channel.

⸻

Step 4: Interact with the bot
	•	Add wishlist items:
Paste any product URL in the wishlist channel. The bot will scrape and confirm it with an embedded message.
	•	Show last 5 wishlist items:
Type: !wishlist


	•	Show entire wishlist with pagination:
Type: !wishlist all

Navigate pages by clicking the ⏮️ and ⏭️ reactions on the bot’s message.

⸻

Project Structure
	•	bot.py — main Discord bot logic, message handling, commands, pagination
	•	scraper.py — generic web scraper for product titles and prices
	•	.env — environment variables for Discord token and channel ID
	•	wishlist.json — persistent JSON file storing wishlist items
