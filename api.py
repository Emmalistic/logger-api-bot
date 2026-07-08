"""
Discord Logger API - Flask REST API with Neon PostgreSQL
"""

from flask import Flask, request, jsonify, g
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import logging
import sys
from database import Message, Attachment, EditedMessage, DeletedMessage, SessionLocal, init_db

# Check for DATABASE_URL
if not os.environ.get('DATABASE_URL'):
    logging.error("❌ DATABASE_URL not set! Please add your Neon connection string.")
    sys.exit(1)

# Create Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize database
try:
    init_db()
    logger.info('✅ Database initialized successfully')
except Exception as e:
    logger.error(f'❌ Database init failed: {e}')
    sys.exit(1)


def get_db():
    """Get database session"""
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database session after request"""
    db = g.pop('db', None)
    if db:
        db.close()


# ============ Health & Root ============

@app.route('/')
def index():
    return jsonify({
        'service': 'Discord Logger API',
        'database': 'Neon PostgreSQL',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            'health': '/health',
            'messages': '/api/messages',
            'message': '/api/messages/<message_id>',
            'channels': '/api/channels',
            'stats': '/api/stats',
            'users': '/api/users',
            'deleted': '/api/deleted'
        }
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Discord Logger API',
        'database': 'Neon PostgreSQL',
        'timestamp': datetime.utcnow().isoformat()
    })


# ============ Messages API ============

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get messages with filters"""
    db = get_db()
    try:
        query = db.query(Message)

        # Apply filters
        if request.args.get('channel_id'):
            query = query.filter(Message.channel_id == request.args.get('channel_id'))
        if request.args.get('guild_id'):
            query = query.filter(Message.guild_id == request.args.get('guild_id'))
        if request.args.get('author_id'):
            query = query.filter(Message.author_id == request.args.get('author_id'))
        if request.args.get('search'):
            search_term = f"%{request.args.get('search')}%"
            query = query.filter(Message.content.like(search_term))

        # Order and paginate
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)

        messages = query.all()

        return jsonify({
            'success': True,
            'count': len(messages),
            'limit': limit,
            'offset': offset,
            'messages': [msg.to_dict() for msg in messages]
        })

    except Exception as e:
        logger.error(f'Error fetching messages: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/messages/<message_id>', methods=['GET'])
def get_message(message_id):
    """Get a specific message"""
    db = get_db()
    try:
        message = db.query(Message).filter_by(message_id=message_id).first()
        if not message:
            return jsonify({'success': False, 'error': 'Message not found'}), 404
        return jsonify({'success': True, 'message': message.to_dict()})
    except Exception as e:
        logger.error(f'Error fetching message: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/messages/<message_id>/attachments', methods=['GET'])
def get_message_attachments(message_id):
    """Get attachments for a message"""
    db = get_db()
    try:
        attachments = db.query(Attachment).filter_by(message_id=message_id).all()
        return jsonify({
            'success': True,
            'count': len(attachments),
            'attachments': [att.to_dict() for att in attachments]
        })
    except Exception as e:
        logger.error(f'Error fetching attachments: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Channels API ============

@app.route('/api/channels', methods=['GET'])
def get_channels():
    """Get all channels with message counts"""
    db = get_db()
    try:
        from sqlalchemy import func
        channels = db.query(
            Message.channel_id,
            Message.channel_name,
            Message.guild_id,
            Message.guild_name,
            func.count(Message.id).label('message_count')
        ).group_by(Message.channel_id).all()

        return jsonify({
            'success': True,
            'count': len(channels),
            'channels': [
                {
                    'channel_id': c.channel_id,
                    'channel_name': c.channel_name,
                    'guild_id': c.guild_id,
                    'guild_name': c.guild_name,
                    'message_count': c.message_count
                }
                for c in channels
            ]
        })
    except Exception as e:
        logger.error(f'Error fetching channels: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/channels/<channel_id>/messages', methods=['GET'])
def get_channel_messages(channel_id):
    """Get messages from a specific channel"""
    db = get_db()
    try:
        query = db.query(Message).filter_by(channel_id=channel_id)
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        messages = query.all()

        return jsonify({
            'success': True,
            'channel_id': channel_id,
            'count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        logger.error(f'Error fetching channel messages: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Users API ============

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users with message counts"""
    db = get_db()
    try:
        from sqlalchemy import func
        users = db.query(
            Message.author_id,
            Message.author_name,
            func.count(Message.id).label('message_count')
        ).group_by(Message.author_id).order_by(func.count(Message.id).desc()).all()

        return jsonify({
            'success': True,
            'count': len(users),
            'users': [
                {
                    'author_id': u.author_id,
                    'author_name': u.author_name,
                    'message_count': u.message_count
                }
                for u in users
            ]
        })
    except Exception as e:
        logger.error(f'Error fetching users: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<author_id>/messages', methods=['GET'])
def get_user_messages(author_id):
    """Get messages from a specific user"""
    db = get_db()
    try:
        query = db.query(Message).filter_by(author_id=author_id)
        if request.args.get('channel_id'):
            query = query.filter(Message.channel_id == request.args.get('channel_id'))
        query = query.order_by(Message.timestamp.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        messages = query.all()

        return jsonify({
            'success': True,
            'author_id': author_id,
            'count': len(messages),
            'messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        logger.error(f'Error fetching user messages: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Deleted Messages ============

@app.route('/api/deleted', methods=['GET'])
def get_deleted_messages():
    """Get deleted messages"""
    db = get_db()
    try:
        query = db.query(DeletedMessage)
        if request.args.get('channel_id'):
            query = query.filter(DeletedMessage.channel_id == request.args.get('channel_id'))
        query = query.order_by(DeletedMessage.deleted_at.desc())
        limit = min(int(request.args.get('limit', 50)), 500)
        offset = int(request.args.get('offset', 0))
        query = query.limit(limit).offset(offset)
        messages = query.all()

        return jsonify({
            'success': True,
            'count': len(messages),
            'deleted_messages': [msg.to_dict() for msg in messages]
        })
    except Exception as e:
        logger.error(f'Error fetching deleted messages: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Statistics ============

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get overall statistics"""
    db = get_db()
    try:
        from sqlalchemy import func
        total_messages = db.query(func.count(Message.id)).scalar() or 0
        total_users = db.query(func.count(func.distinct(Message.author_id))).scalar() or 0
        total_channels = db.query(func.count(func.distinct(Message.channel_id))).scalar() or 0
        total_guilds = db.query(func.count(func.distinct(Message.guild_id))).scalar() or 0

        week_ago = datetime.utcnow() - timedelta(days=7)
        messages_this_week = db.query(func.count(Message.id)).filter(
            Message.timestamp >= week_ago
        ).scalar() or 0

        return jsonify({
            'success': True,
            'stats': {
                'total_messages': total_messages,
                'total_users': total_users,
                'total_channels': total_channels,
                'total_guilds': total_guilds,
                'messages_this_week': messages_this_week,
                'generated_at': datetime.utcnow().isoformat()
            }
        })
    except Exception as e:
        logger.error(f'Error fetching stats: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Main ============

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f'🚀 Starting Discord Logger API on port {port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
