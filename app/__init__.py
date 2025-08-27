from flask import Flask
from flask_cors import CORS
import logging
import os
from config.config import Config
from supabase import create_client


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, origins=["*"])

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler('medical_processor.log'),
            logging.StreamHandler()
        ]
    )

    # Ensure directories exist
    for directory in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER']]:
        os.makedirs(directory, exist_ok=True)
    for view in ['axial', 'coronal', 'sagittal']:
        os.makedirs(os.path.join(app.config['BASE_PATH'], view), exist_ok=True)

    # Supabase client
    try:
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['supabase'] = create_client(app.config['SUPABASE_URL'], app.config['SUPABASE_KEY'])
    except Exception:
        app.extensions['supabase'] = None

    # Register blueprints
    try:
        from app.routes.upload import upload_bp
        from app.routes.status import status_bp
        from app.routes.health import health_bp
        app.register_blueprint(upload_bp)
        app.register_blueprint(status_bp)
        app.register_blueprint(health_bp)
    except Exception:
        pass

    # Error handlers
    @app.errorhandler(413)
    def file_too_large(e):
        from flask import jsonify
        return jsonify({
            'error': 'File too large',
            'max_size_mb': app.config['MAX_FILE_SIZE'] / (1024*1024)
        }), 413

    @app.errorhandler(500)
    def internal_error(e):
        from flask import jsonify
        return jsonify({'error': 'Internal server error'}), 500

    @app.errorhandler(404)
    def not_found(e):
        from flask import jsonify
        return jsonify({'error': 'Endpoint not found'}), 404

    return app


