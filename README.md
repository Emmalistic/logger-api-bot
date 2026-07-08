# 📝 Discord Logger Bot

A powerful Discord bot that logs all messages, edits, deletions, and attachments to a PostgreSQL database with a REST API for querying logs.

[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## ✨ Features

- 📨 **Message Logging** - Logs all messages with metadata (author, channel, guild, timestamp)
- ✏️ **Edit Tracking** - Tracks message edits with full history
- 🗑️ **Delete Logging** - Stores deleted messages for auditing
- 📎 **Attachment Storage** - Logs all attachments with URLs and metadata
- 🔍 **REST API** - Query logs via HTTP endpoints
- 📊 **Statistics** - Get insights about server activity
- 🗄️ **PostgreSQL** - Uses Neon for reliable, free database hosting

## 🏗️ Architecture

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Discord Bot Token ([Get it here](https://discord.com/developers/applications))
- Neon PostgreSQL Database ([Sign up here](https://neon.tech))

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/discord-logger-bot.git
cd discord-logger-bot
