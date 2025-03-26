import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_login import LoginManager
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import config_by_name
from app.models import db, Player, GameState

# Initialize extensions
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
csrf = CSRFProtect()
talisman = Talisman()
migrate = Migrate()
scheduler = BackgroundScheduler()

@login_manager.user_loader
def load_user(user_id):
    return Player.query.get(user_id)

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Only enable HTTPS in production
    if config_name == 'production':
        talisman.init_app(app, force_https=False, content_security_policy=None)
    
    migrate.init_app(app, db)
    
    # Ensure upload and backup directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['BACKUP_DIR'], exist_ok=True)
    
    # Register blueprints
    from app.routes.main import main as main_blueprint
    from app.routes.auth import auth as auth_blueprint
    from app.routes.game import game as game_blueprint
    from app.routes.admin import admin as admin_blueprint
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    app.register_blueprint(game_blueprint, url_prefix='/game')
    app.register_blueprint(admin_blueprint, url_prefix='/admin')
    
    # Configure logging
    if not app.debug and not app.testing:
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
        
        file_handler = RotatingFileHandler(
            'logs/senior_assassin.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Senior Assassin startup')
    
    # Initialize the scheduler
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
        
        # Initialize game state if it doesn't exist
        if not GameState.query.first():
            game_state = GameState(
                state='pre',
                round_number=0,
                voting_threshold=app.config['VOTING_THRESHOLD']
            )
            db.session.add(game_state)
            db.session.commit()
        
        # Start the scheduler
        from app.services.game_service import schedule_round_transitions
        schedule_round_transitions(app)
        
        if not scheduler.running:
            scheduler.start()
            
        # Schedule daily backup
        from app.services.admin_service import backup_database
        scheduler.add_job(
            backup_database,
            'cron', 
            hour=3,  # Run at 3 AM
            minute=0, 
            args=[app]
        )
    
    return app
