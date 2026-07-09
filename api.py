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
    # Continue anyway, will try on each request


def get_db():
    """Get database session"""
    if 'db' not in g:
        try:
            g.db = SessionLocal()
        except Exception as e:
            logger.error(f"❌ Failed to create database session: {e}")
            g.db = None
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database session after request"""
    db = g.pop('db', None)
    if db:
        try:
            db.close()
        except Exception as e:
            logger.error(f"❌ Error closing database: {e}")


# ============ Health & Root ============

@app.route('/')
def index():
    return jsonify({
        'service': 'Discord Logger API',
        'database': 'Neon PostgreSQL' if os.environ.get('DATABASE_URL') else 'SQLite (fallback)',
        'status': 'running',
        'version': '1.0.0',
        'python_version': sys.version.split()[0],
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
    try:
        # Test database connection
        db = get_db()
        if db:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            db_status = "connected"
        else:
            db_status = "disconnected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        'status': 'healthy',
        'service': 'Discord Logger API',
        'database': db_status,
        'timestamp': datetime.utcnow().isoformat()
    })


# ============ Messages API ============

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get messages with filters"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500
    
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
        logger.error(sys.exc_info())
        return jsonify({'success': False, 'error': str(e)}), 500


# ... (rest of API endpoints remain the same) ...


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    logger.info(f'🚀 Starting Discord Logger API on port {port}')
    app.run(host='0.0.0.0', port=port, debug=debug)
