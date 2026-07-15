"""
Discord Logger API - Simple, Clean, ID-Based
No names, no metadata, just the data you need
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import logging
import sys
from database import Message, Attachment, EditedMessage, DeletedMessage, SessionLocal, init_db

# Create Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
try:
    init_db()
    logger.info('✅ Database initialized')
except Exception as e:
    logger.error(f'❌ Database init failed: {e}')

def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db:
        db.close()

# ============ MAIN MESSAGES ENDPOINT ============

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """
    Get messages with filters
    Example: /api/messages?guild=123&channel=456&user=789&limit=50&before=1704067200
    """
    db = get_db()
    try:
        query = db.query(Message)
        
        # Apply filters (IDs only)
        if request.args.get('guild'):
            query = query.filter(Message.guild_id == request.args.get('guild'))
        if request.args.get('channel'):
            query = query.filter(Message.channel_id == request.args.get('channel'))
        if request.args.get('user'):
            query = query.filter(Message.author_id == request.args.get('user'))
        
        # Timestamp filter
        if request.args.get('before'):
            query = query.filter(Message.timestamp < datetime.fromtimestamp(int(request.args.get('before'))))
        if request.args.get('after'):
            query = query.filter(Message.timestamp > datetime.fromtimestamp(int(request.args.get('after'))))
        
        # Order and paginate
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        
        messages = query.all()
        
        # Format response - clean, simple, no names
        result = []
        for msg in messages:
            # Get attachments
            attachments = db.query(Attachment).filter_by(message_id=msg.message_id).all()
            attachment_urls = [att.url for att in attachments]
            
            # Get edit history
            edits = db.query(EditedMessage).filter_by(message_id=msg.message_id).order_by(EditedMessage.edited_at).all()
            edit_info = None
            if edits:
                last_edit = edits[-1]
                edit_info = {
                    "old": last_edit.old_content,
                    "new": last_edit.new_content,
                    "at": int(last_edit.edited_at.timestamp())
                }
            
            result.append({
                "message_id": msg.message_id,
                "guild_id": msg.guild_id,
                "channel_id": msg.channel_id,
                "user_id": msg.author_id,
                "content": msg.content,
                "timestamp": int(msg.timestamp.timestamp()),
                "attachments": attachment_urls,
                "replied_to": msg.reply_to_message_id,
                "edited": edit_info
            })
        
        return jsonify({
            "data": result,
            "count": len(result),
            "next_offset": offset + limit if len(result) == limit else None
        })
        
    except Exception as e:
        logger.error(f'Error: {e}')
        return jsonify({"error": str(e)}), 500

# ============ SINGLE MESSAGE ============

@app.route('/api/messages/<message_id>', methods=['GET'])
def get_message(message_id):
    """Get a single message by ID"""
    db = get_db()
    try:
        msg = db.query(Message).filter_by(message_id=message_id).first()
        if not msg:
            return jsonify({"error": "Message not found"}), 404
        
        # Get attachments
        attachments = db.query(Attachment).filter_by(message_id=msg.message_id).all()
        attachment_urls = [att.url for att in attachments]
        
        # Get edit history
        edits = db.query(EditedMessage).filter_by(message_id=msg.message_id).order_by(EditedMessage.edited_at).all()
        edit_info = None
        if edits:
            last_edit = edits[-1]
            edit_info = {
                "old": last_edit.old_content,
                "new": last_edit.new_content,
                "at": int(last_edit.edited_at.timestamp())
            }
        
        return jsonify({
            "data": {
                "message_id": msg.message_id,
                "guild_id": msg.guild_id,
                "channel_id": msg.channel_id,
                "user_id": msg.author_id,
                "content": msg.content,
                "timestamp": int(msg.timestamp.timestamp()),
                "attachments": attachment_urls,
                "replied_to": msg.reply_to_message_id,
                "edited": edit_info
            }
        })
        
    except Exception as e:
        logger.error(f'Error: {e}')
        return jsonify({"error": str(e)}), 500

# ============ SEARCH ============

@app.route('/api/search', methods=['GET'])
def search_messages():
    """
    Search messages by content
    Example: /api/search?q=hello&guild=123&limit=10
    """
    db = get_db()
    try:
        query_text = request.args.get('q', '')
        if not query_text:
            return jsonify({"error": "Search query required"}), 400
        
        query = db.query(Message)
        
        # Filter by guild if provided
        if request.args.get('guild'):
            query = query.filter(Message.guild_id == request.args.get('guild'))
        
        # Full-text search on content
        query = query.filter(Message.content.like(f'%{query_text}%'))
        
        # Order and paginate
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        
        messages = query.all()
        
        # Format response
        result = []
        for msg in messages:
            attachments = db.query(Attachment).filter_by(message_id=msg.message_id).all()
            attachment_urls = [att.url for att in attachments]
            
            result.append({
                "message_id": msg.message_id,
                "guild_id": msg.guild_id,
                "channel_id": msg.channel_id,
                "user_id": msg.author_id,
                "content": msg.content,
                "timestamp": int(msg.timestamp.timestamp()),
                "attachments": attachment_urls,
                "replied_to": msg.reply_to_message_id
            })
        
        return jsonify({
            "data": result,
            "count": len(result),
            "next_offset": offset + limit if len(result) == limit else None
        })
        
    except Exception as e:
        logger.error(f'Error: {e}')
        return jsonify({"error": str(e)}), 500

# ============ STATS ============

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get detailed statistics with IDs only"""
    db = get_db()
    try:
        from sqlalchemy import func
        
        total_messages = db.query(func.count(Message.id)).scalar() or 0
        total_users = db.query(func.count(func.distinct(Message.author_id))).scalar() or 0
        total_channels = db.query(func.count(func.distinct(Message.channel_id))).scalar() or 0
        total_guilds = db.query(func.count(func.distinct(Message.guild_id))).scalar() or 0
        
        # Today's messages
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        messages_today = db.query(func.count(Message.id)).filter(
            Message.timestamp >= today
        ).scalar() or 0
        
        # This week's messages
        week_ago = datetime.utcnow() - timedelta(days=7)
        messages_week = db.query(func.count(Message.id)).filter(
            Message.timestamp >= week_ago
        ).scalar() or 0
        
        # Most active user
        most_active = db.query(
            Message.author_id,
            func.count(Message.id).label('count')
        ).group_by(Message.author_id).order_by(func.count(Message.id).desc()).first()
        
        most_active_user = {
            "user_id": most_active[0],
            "message_count": most_active[1]
        } if most_active else None
        
        # Most active channel
        most_active_channel = db.query(
            Message.channel_id,
            func.count(Message.id).label('count')
        ).group_by(Message.channel_id).order_by(func.count(Message.id).desc()).first()
        
        most_active_channel_data = {
            "channel_id": most_active_channel[0],
            "message_count": most_active_channel[1]
        } if most_active_channel else None
        
        return jsonify({
            "data": {
                "total_messages": total_messages,
                "total_users": total_users,
                "total_channels": total_channels,
                "total_guilds": total_guilds,
                "messages_today": messages_today,
                "messages_this_week": messages_week,
                "most_active_user": most_active_user,
                "most_active_channel": most_active_channel_data,
                "generated_at": int(datetime.utcnow().timestamp())
            }
        })
        
    except Exception as e:
        logger.error(f'Error: {e}')
        return jsonify({"error": str(e)}), 500

# ============ GUILD MESSAGES ============

@app.route('/api/guild/<guild_id>/messages', methods=['GET'])
def get_guild_messages(guild_id):
    """Get all messages from a specific guild"""
    return get_messages_with_filter('guild_id', guild_id)

# ============ CHANNEL MESSAGES ============

@app.route('/api/channel/<channel_id>/messages', methods=['GET'])
def get_channel_messages(channel_id):
    """Get all messages from a specific channel"""
    return get_messages_with_filter('channel_id', channel_id)

# ============ USER MESSAGES ============

@app.route('/api/user/<user_id>/messages', methods=['GET'])
def get_user_messages(user_id):
    """Get all messages from a specific user"""
    return get_messages_with_filter('author_id', user_id)

# Helper function for filtered endpoints
def get_messages_with_filter(filter_field, filter_value):
    db = get_db()
    try:
        query = db.query(Message)
        
        # Apply filter based on field
        if filter_field == 'guild_id':
            query = query.filter(Message.guild_id == filter_value)
        elif filter_field == 'channel_id':
            query = query.filter(Message.channel_id == filter_value)
        elif filter_field == 'author_id':
            query = query.filter(Message.author_id == filter_value)
        
        # Additional filters
        if request.args.get('before'):
            query = query.filter(Message.timestamp < datetime.fromtimestamp(int(request.args.get('before'))))
        if request.args.get('after'):
            query = query.filter(Message.timestamp > datetime.fromtimestamp(int(request.args.get('after'))))
        
        # Order and paginate
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        
        messages = query.all()
        
        # Format response
        result = []
        for msg in messages:
            attachments = db.query(Attachment).filter_by(message_id=msg.message_id).all()
            attachment_urls = [att.url for att in attachments]
            
            result.append({
                "message_id": msg.message_id,
                "guild_id": msg.guild_id,
                "channel_id": msg.channel_id,
                "user_id": msg.author_id,
                "content": msg.content,
                "timestamp": int(msg.timestamp.timestamp()),
                "attachments": attachment_urls,
                "replied_to": msg.reply_to_message_id
            })
        
        return jsonify({
            "data": result,
            "count": len(result),
            "next_offset": offset + limit if len(result) == limit else None
        })
        
    except Exception as e:
        logger.error(f'Error: {e}')
        return jsonify({"error": str(e)}), 500

# ============ ROOT ============

@app.route('/')
def index():
    return jsonify({
        "service": "Discord Logger API",
        "version": "2.0",
        "endpoints": {
            "messages": "/api/messages?guild=&channel=&user=&limit=&before=",
            "single": "/api/messages/{message_id}",
            "search": "/api/search?q=&guild=&limit=",
            "stats": "/api/stats",
            "guild": "/api/guild/{guild_id}/messages",
            "channel": "/api/channel/{channel_id}/messages",
            "user": "/api/user/{user_id}/messages"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)