"""
Discord Bot - Simple Logger
Just logs messages, edits, deletions, and attachments
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

# Flask app for health checks
app = Flask(__name__)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'Discord Bot'})

@app.route('/')
def index():
    return jsonify({'service': 'Discord Bot', 'status': 'running'})

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

class MessageLoggerBot(discord.Client):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True
        intents.reactions = True
        super().__init__(intents=intents)

    async def on_ready(self):
        logger.info(f'✅ Bot logged in as {self.user}')
        logger.info(f'📊 Connected to {len(self.guilds)} servers')
        logger.info('🚀 Bot is ready!')

    async def on_message(self, message):
        if message.author.bot:
            return
        if message.type != discord.MessageType.default:
            return

        db = get_db()
        try:
            mentioned_users = [str(m.id) for m in message.mentions]
            mentioned_roles = [str(r.id) for r in message.role_mentions]

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
                reply_to_message_id=str(message.reference.message_id) if message.reference else None,
            )
            db.add(msg_record)

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
            logger.info(f'📝 Logged message {message.id}')

        except Exception as e:
            logger.error(f'❌ Error: {e}')
            db.rollback()
        finally:
            close_db(db)

    async def on_message_edit(self, before, after):
        if before.content == after.content:
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
                logger.info(f'✏️ Edit logged for {after.id}')
        except Exception as e:
            logger.error(f'❌ Error: {e}')
            db.rollback()
        finally:
            close_db(db)

    async def on_message_delete(self, message):
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
                reply_to_message_id=msg_record.reply_to_message_id if msg_record else None
            )
            db.add(deleted_record)

            if msg_record:
                msg_record.content = "[MESSAGE DELETED]"

            db.commit()
            logger.info(f'🗑️ Deletion logged for {message.id}')
        except Exception as e:
            logger.error(f'❌ Error: {e}')
            db.rollback()
        finally:
            close_db(db)

def run_bot():
    init_db()
    logger.info('✅ Database initialized')
    
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info('✅ Web server started')
    
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        logger.error('❌ No token!')
        return
    
    bot = MessageLoggerBot()
    bot.run(token)

if __name__ == '__main__':
    run_bot()