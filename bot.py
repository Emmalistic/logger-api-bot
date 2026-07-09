"""
Discord Bot - Message Logger with Neon PostgreSQL
"""

import discord
from discord import Intents
from datetime import datetime
import json
import logging
import os
import threading
import sys
import traceback
from flask import Flask, jsonify
from database import Message, Attachment, EditedMessage, DeletedMessage, get_db, close_db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Check for required environment variables
if not os.environ.get('DISCORD_TOKEN'):
    logger.error("❌ DISCORD_TOKEN not found! Please add it to Render environment variables.")
    # Don't exit, let it try to run anyway

if not os.environ.get('DATABASE_URL'):
    logger.warning("⚠️ DATABASE_URL not found! Using SQLite fallback.")

# Flask app for health checks
app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        'service': 'Discord Logger Bot',
        'status': 'running',
        'database': 'Neon PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite (fallback)',
        'version': '1.0.0',
        'python_version': sys.version.split()[0]
    })

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'Discord Bot',
        'database': 'Neon PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite (fallback)',
        'timestamp': datetime.utcnow().isoformat()
    })

def run_web_server():
    """Run Flask web server for health checks"""
    port = int(os.environ.get('PORT', 10000))
    try:
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Web server error: {e}")


class MessageLoggerBot(discord.Client):
    """Discord bot that logs all messages to database"""

    def __init__(self):
        # Enable required intents
        intents = Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True
        intents.reactions = True
        
        super().__init__(intents=intents)
        self.db_initialized = False

    async def on_ready(self):
        """Called when bot is ready"""
        try:
            # Initialize database
            if not self.db_initialized:
                success = init_db()
                self.db_initialized = True
                if success:
                    logger.info('✅ Database initialized successfully')
                else:
                    logger.warning('⚠️ Database initialization failed, continuing anyway')
        except Exception as e:
            logger.error(f'❌ Database init error: {e}')
        
        logger.info(f'✅ Bot logged in as {self.user} (ID: {self.user.id})')
        logger.info(f'📊 Connected to {len(self.guilds)} servers')
        logger.info(f'🐍 Python version: {sys.version.split()[0]}')
        logger.info('🚀 Bot is ready and listening for messages!')

    async def on_message(self, message):
        """Called when a message is sent"""
        # Ignore bot messages and system messages
        if message.author.bot:
            return
        if message.type != discord.MessageType.default:
            return

        if not self.db_initialized:
            logger.warning("⚠️ Database not initialized, skipping message log")
            return

        db = get_db()
        try:
            # Extract mentions
            mentioned_users = [str(m.id) for m in message.mentions]
            mentioned_roles = [str(r.id) for r in message.role_mentions]

            # Create message record
            msg_record = Message(
                message_id=str(message.id),
                channel_id=str(message.channel.id),
                channel_name=getattr(message.channel, 'name', None),
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None,
                author_id=str(message.author.id),
                author_name=message.author.name,
                author_discriminator=getattr(message.author, 'discriminator', '0'),
                author_nickname=getattr(message.author, 'nick', None),
                content=message.content if message.content else None,
                timestamp=message.created_at,
                is_bot=message.author.bot,
                mentions=json.dumps(mentioned_users) if mentioned_users else None,
                mentioned_roles=json.dumps(mentioned_roles) if mentioned_roles else None,
                has_attachments=len(message.attachments) > 0,
                has_embed=len(message.embeds) > 0,
                has_reactions=len(message.reactions) > 0,
            )
            db.add(msg_record)

            # Store attachments
            for attachment in message.attachments:
                att_record = Attachment(
                    message_id=str(message.id),
                    attachment_id=str(attachment.id),
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    url=attachment.url,
                    size=attachment.size,
                    proxy_url=attachment.proxy_url
                )
                db.add(att_record)

            db.commit()
            logger.info(f'📝 Logged message {message.id} from {message.author}')

        except Exception as e:
            logger.error(f'❌ Error logging message: {e}')
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            close_db(db)

    async def on_message_edit(self, before, after):
        """Called when a message is edited"""
        if before.content == after.content:
            return
        if after.type != discord.MessageType.default:
            return

        if not self.db_initialized:
            return

        db = get_db()
        try:
            msg_record = db.query(Message).filter_by(message_id=str(after.id)).first()
            if msg_record:
                msg_record.content = after.content
                msg_record.edited_timestamp = discord.utils.utcnow()

                edit_record = EditedMessage(
                    message_id=str(after.id),
                    old_content=before.content,
                    new_content=after.content,
                    edited_at=discord.utils.utcnow()
                )
                db.add(edit_record)
                db.commit()
                logger.info(f'✏️ Logged edit for message {after.id}')
        except Exception as e:
            logger.error(f'❌ Error logging edit: {e}')
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            close_db(db)

    async def on_message_delete(self, message):
        """Called when a message is deleted"""
        if message.type != discord.MessageType.default:
            return

        if not self.db_initialized:
            return

        db = get_db()
        try:
            msg_record = db.query(Message).filter_by(message_id=str(message.id)).first()

            deleted_record = DeletedMessage(
                message_id=str(message.id),
                channel_id=str(message.channel.id),
                channel_name=getattr(message.channel, 'name', None),
                guild_id=str(message.guild.id) if message.guild else None,
                guild_name=message.guild.name if message.guild else None,
                author_id=str(message.author.id),
                author_name=message.author.name,
                author_discriminator=getattr(message.author, 'discriminator', '0'),
                content=message.content,
                original_timestamp=message.created_at,
                has_attachments=len(message.attachments) > 0,
            )
            db.add(deleted_record)

            if msg_record:
                msg_record.content = "[MESSAGE DELETED]"

            db.commit()
            logger.info(f'🗑️ Logged deletion of message {message.id}')

        except Exception as e:
            logger.error(f'❌ Error logging deletion: {e}')
            logger.error(traceback.format_exc())
            db.rollback()
        finally:
            close_db(db)


def run_bot():
    """Run the Discord bot"""
    try:
        # Start web server in background thread
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        logger.info(f'✅ Web server started on port {os.environ.get("PORT", "10000")}')

        # Run Discord bot
        bot = MessageLoggerBot()
        logger.info('🚀 Starting Discord bot...')
        
        token = os.environ.get('DISCORD_TOKEN')
        if not token:
            logger.error('❌ DISCORD_TOKEN not set!')
            return
        
        bot.run(token)

    except discord.LoginFailure:
        logger.error('❌ Invalid Discord token! Please check your DISCORD_TOKEN.')
        sys.exit(1)
    except Exception as e:
        logger.error(f'❌ Bot crashed: {e}')
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    run_bot()
