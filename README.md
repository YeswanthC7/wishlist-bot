# 🛒 Discord Wishlist Bot

A production-grade Discord bot that captures product URLs posted in server channels,
scrapes item details (title + price), and stores per-channel wishlists in Postgres.

Invite link: https://discord.com/oauth2/authorize?client_id=1393497189350637658&permissions=2147601472&integration_type=0&scope=bot

Deployed on Fly.io with Neon Postgres.

---

## 🚀 Features

### ✅ Link Capture
- Users paste product URLs in a channel
- Bot scrapes:
  - Title (OG tag / fallback)
  - Price
- Automatically stores in Postgres
- Duplicate detection per channel (DB-level unique constraint)

### ✅ Per-Channel Isolation
Each Discord channel has its own wishlist.
Data is separated by:
- `guild_id`
- `channel_id`

### ✅ Slash Commands (Modern UX)

All commands are slash-based:
/wishlist latest
/wishlist all
/wishlist export
/wishlist clear
/wishlist enable
/wishlist disable


---

## 📌 Slash Commands

### `/wishlist latest`
Shows the latest 5 wishlist items for the current channel.

### `/wishlist all`
Shows all wishlist items with button-based pagination.

### `/wishlist export`
Downloads the entire channel wishlist as a JSON file.

### `/wishlist clear`
Admin-only. Clears all wishlist items in the current channel.

### `/wishlist enable`
Admin-only. Enables wishlist capture in the current channel.

### `/wishlist disable`
Admin-only. Disables wishlist capture in the current channel.

---

## 🧠 Architecture

### Bot Layer
- discord.py 2.x
- Slash commands via `app_commands`
- Button-based pagination via `discord.ui.View`

### Database Layer
Postgres schema:

### `channel_config`
| column      | type    | description |
|------------|---------|------------|
| guild_id   | string  | Discord server ID |
| channel_id | string  | Discord channel ID |
| enabled    | boolean | Capture enabled flag |

### `wishlist_item`
| column      | type    |
|------------|---------|
| id         | serial PK |
| guild_id   | string |
| channel_id | string |
| url        | text |
| url_norm   | text |
| title      | text |
| price      | text |
| user_tag   | text |
| created_at | timestamp |

Unique constraint: (channel_id, url_norm)

---

## 🔐 Environment Variables

Required: DISCORD_TOKEN, DATABASE_URL


Optional (for slash command sync):
SYNC_COMMANDS=true
SYNC_GUILD_ID=123456789012345678


---

## 🏗 Deployment

### Fly.io (Worker App)

### Postgres
- Neon (free tier)
- DATABASE_URL stored in Fly secrets

---

## 🛡 Production Design Decisions

- No tokens stored in repo
- DB-level duplicate enforcement
- Channel-level isolation
- Admin-only destructive commands
- Default capture enabled unless configured
- Safe transaction rollback handling

---

## 📈 Future Enhancements

- Web dashboard (FastAPI + OAuth2)
- Server-level configuration UI
- Multi-process deployment (bot + web)
- Role-based capture controls
- Background price refresh worker

---

## 👨‍💻 Author

Built and maintained by Yeswanth.
Production deployed on Fly.io.
