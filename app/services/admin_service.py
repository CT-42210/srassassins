import os
import json
import sqlite3
import datetime
import shutil
from subprocess import Popen, PIPE
from werkzeug.security import check_password_hash
from flask import current_app

from app.models import db, Team, Player, GameState, KillConfirmation, KillVote, ActionLog
from app.services.game_service import assign_targets, check_game_complete
from app.services.email_service import send_all_players_email
from app.services.instagram_service import post_to_feed, post_to_story, post_round_start_to_feed

def verify_admin_password(password):
    """
    Verify the admin password against the stored hash.
    
    Args:
        password (str): Password to verify
    
    Returns:
        bool: True if password is correct, False otherwise
    """
    admin_hash = current_app.config['ADMIN_PASSWORD_HASH']
    return check_password_hash(admin_hash, password)

def get_admin_dashboard_data():
    """
    Get data for the admin dashboard.
    
    Returns:
        dict: Dashboard data
    """
    # Get game state
    game_state = GameState.query.first()
    
    # Get team stats
    total_teams = Team.query.count()
    pending_teams = Team.query.filter_by(state='pending').count()
    alive_teams = Team.query.filter_by(state='alive').count()
    dead_teams = Team.query.filter_by(state='dead').count()
    
    # Get player stats
    total_players = Player.query.count()
    alive_players = Player.query.filter_by(state='alive').count()
    dead_players = Player.query.filter_by(state='dead').count()
    
    # Get kill stats
    total_kills = KillConfirmation.query.filter_by(status='approved').count()
    pending_kills = KillConfirmation.query.filter_by(status='pending').count()
    
    # Get database stats
    try:
        db_path = current_app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        db_size = os.path.getsize(db_path) / (1024 * 1024)  # Size in MB
    except:
        db_size = None
    
    # Get recent logs
    recent_logs = ActionLog.query.order_by(ActionLog.timestamp.desc()).limit(10).all()
    
    # Compile dashboard data
    dashboard_data = {
        'game_state': {
            'state': game_state.state,
            'round_number': game_state.round_number,
            'voting_threshold': game_state.voting_threshold,
            'round_start': game_state.round_start,
            'round_end': game_state.round_end
        },
        'team_stats': {
            'total': total_teams,
            'pending': pending_teams,
            'alive': alive_teams,
            'dead': dead_teams
        },
        'player_stats': {
            'total': total_players,
            'alive': alive_players,
            'dead': dead_players
        },
        'kill_stats': {
            'total': total_kills,
            'pending': pending_kills
        },
        'database': {
            'size_mb': db_size
        },
        'recent_logs': [
            {
                'action_type': log.action_type,
                'description': log.description,
                'actor': log.actor,
                'timestamp': log.timestamp
            } for log in recent_logs
        ]
    }
    
    return dashboard_data

def accept_team(team_id):
    """
    Accept a pending team into the game.
    
    Args:
        team_id (str): ID of the team to accept
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get game state
    game_state = GameState.query.first()
    
    # Can only accept teams before the game starts
    if game_state.state != 'pre':
        return False
    
    # Get the team
    team = Team.query.get(team_id)
    if not team or team.state != 'pending':
        return False
    
    # Update team state
    team.state = 'alive'
    
    # Log the action
    log = ActionLog(
        action_type='team_acceptance',
        description=f'Team {team.name} accepted into the game',
        actor='admin'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Log the event
    current_app.logger.info(f'Team {team.name} (ID: {team.id}) accepted into the game')
    
    return True

def change_game_state(new_state):
    """
    Change the game state.
    
    Args:
        new_state (str): New game state ('pre', 'live', 'post', 'forced')
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate new state
    if new_state not in ['pre', 'live', 'post', 'forced']:
        return False
    
    # Get game state
    game_state = GameState.query.first()
    old_state = game_state.state
    
    # Update state
    game_state.state = new_state
    
    # Special handling for transitioning to 'live'
    if new_state == 'live' and old_state == 'pre':
        # Auto-start round 1
        start_round(increment=True)
    
    # Special handling for transitioning to 'post'
    if new_state == 'post':
        # Determine the winner
        check_game_complete()
    
    # Log the action
    log = ActionLog(
        action_type='game_state_change',
        description=f'Game state changed from {old_state} to {new_state}',
        actor='admin'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Log the event
    current_app.logger.info(f'Game state changed from {old_state} to {new_state}')
    
    return True

def start_round(increment=False):
    """
    Start a new round of the game.
    
    Args:
        increment (bool): Whether to increment the round number
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get game state
    game_state = GameState.query.first()
    
    # Increment round number if requested
    if increment:
        game_state.round_number += 1
    
    # Set round start time
    game_state.round_start = datetime.datetime.utcnow()
    
    # Assign targets to teams
    assign_targets()
    
    # Revive eliminated players in surviving teams
    teams = Team.query.filter_by(state='alive').all()
    for team in teams:
        for player in team.players:
            if not player.is_alive:
                player.state = 'alive'
                
                # Log the revival
                log = ActionLog(
                    action_type='player_revival',
                    description=f'Player {player.name} revived for round {game_state.round_number}',
                    actor='system'
                )
                db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Send notifications
    send_all_players_email(
        subject=f"Senior Assassin - Round {game_state.round_number} Started",
        text_body=f"Round {game_state.round_number} has started! Log in to see your new target."
    )
    
    # Post to Instagram
    post_round_start_to_feed(game_state.round_number)
    post_to_story(text=f"ROUND {game_state.round_number} HAS BEGUN!")
    
    # Log the event
    current_app.logger.info(f'Started round {game_state.round_number}')
    
    return True

def set_round_schedule(round_start, round_end):
    """
    Set the schedule for the current round.
    
    Args:
        round_start (datetime): Round start time
        round_end (datetime): Round end time
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get game state
    game_state = GameState.query.first()
    
    # Update schedule
    game_state.round_start = round_start
    game_state.round_end = round_end
    
    # Log the action
    log = ActionLog(
        action_type='round_schedule',
        description=f'Round {game_state.round_number} schedule set: Start={round_start}, End={round_end}',
        actor='admin'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Log the event
    current_app.logger.info(f'Round {game_state.round_number} schedule set: Start={round_start}, End={round_end}')
    
    # Update scheduler
    from app.services.game_service import schedule_round_transitions
    schedule_round_transitions(current_app._get_current_object())
    
    return True

def toggle_team_state(team_id):
    """
    Toggle a team's state between alive and dead.
    
    Args:
        team_id (str): ID of the team to toggle
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get the team
    team = Team.query.get(team_id)
    if not team:
        return False
    
    # Toggle state
    if team.state == 'alive':
        team.state = 'dead'
        action = 'killed'
        
        # Mark all players as dead
        for player in team.players:
            player.state = 'dead'
    else:
        team.state = 'alive'
        action = 'revived'
        
        # Mark all players as alive
        for player in team.players:
            player.state = 'alive'
    
    # Log the action
    log = ActionLog(
        action_type=f'team_{action}',
        description=f'Team {team.name} {action} by admin',
        actor='admin'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Log the event
    current_app.logger.info(f'Team {team.name} (ID: {team.id}) {action} by admin')
    
    return True

def toggle_player_state(player_id):
    """
    Toggle a player's state between alive and dead.
    
    Args:
        player_id (str): ID of the player to toggle
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get the player
    player = Player.query.get(player_id)
    if not player:
        return False
    
    # Toggle state
    if player.is_alive:
        player.state = 'dead'
        action = 'killed'
        
        # Check if team is now dead
        team = Team.query.get(player.team_id)
        if all(not p.is_alive for p in team.players):
            team.state = 'dead'
    else:
        player.state = 'alive'
        action = 'revived'
        
        # Ensure team is alive
        team = Team.query.get(player.team_id)
        team.state = 'alive'
    
    # Log the action
    log = ActionLog(
        action_type=f'player_{action}',
        description=f'Player {player.name} {action} by admin',
        actor='admin'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Log the event
    current_app.logger.info(f'Player {player.name} (ID: {player.id}) {action} by admin')
    
    return True

def force_vote_decision(kill_confirmation_id, decision):
    """
    Force a decision on a kill confirmation vote.
    
    Args:
        kill_confirmation_id (str): ID of the kill confirmation
        decision (bool): True to approve, False to reject
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get the kill confirmation
    kill_confirmation = KillConfirmation.query.get(kill_confirmation_id)
    if not kill_confirmation or not kill_confirmation.is_pending:
        return False
    
    # Update status
    kill_confirmation.status = 'approved' if decision else 'rejected'
    
    # If approved, mark the victim as dead
    if decision:
        from app.services.game_service import confirm_kill
        confirm_kill(kill_confirmation)
    
    # Log the action
    log = ActionLog(
        action_type='vote_override',
        description=f'Kill confirmation {kill_confirmation_id} {"approved" if decision else "rejected"} by admin',
        actor='admin'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Log the event
    current_app.logger.info(f'Kill confirmation {kill_confirmation_id} {"approved" if decision else "rejected"} by admin')
    
    return True

def backup_database(app=None):
    """
    Backup the SQLite database to a file.
    
    Args:
        app: Flask app object (optional)
    
    Returns:
        str: Path to the backup file, or None if failed
    """
    if app:
        # Use the provided app context
        with app.app_context():
            return _do_backup()
    else:
        # Use current app context
        return _do_backup()

def _do_backup():
    """
    Internal function to perform the actual database backup.
    
    Returns:
        str: Path to the backup file, or None if failed
    """
    try:
        # Get database path from config
        db_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
        if db_uri.startswith('sqlite:///'):
            db_path = db_uri[10:]
        else:
            # Not SQLite, use pg_dump for PostgreSQL or similar
            return None
        
        # Ensure the backup directory exists
        backup_dir = current_app.config['BACKUP_DIR']
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'backup_{timestamp}.db')
        
        # Create backup
        shutil.copy2(db_path, backup_path)
        
        # Log the backup
        log = ActionLog(
            action_type='database_backup',
            description=f'Database backed up to {backup_path}',
            actor='system'
        )
        db.session.add(log)
        db.session.commit()
        
        # Log the event
        current_app.logger.info(f'Database backed up to {backup_path}')
        
        return backup_path
    
    except Exception as e:
        current_app.logger.error(f'Database backup failed: {str(e)}')
        return None

def execute_db_command(sql_command):
    """
    Execute a raw SQL command on the database.
    
    Args:
        sql_command (str): SQL command to execute
    
    Returns:
        tuple: (success, result)
    """
    try:
        # Execute the command
        result = db.session.execute(sql_command)
        db.session.commit()
        
        # Convert result to a list of dicts
        if result.returns_rows:
            columns = result.keys()
            rows = []
            for row in result:
                rows.append(dict(zip(columns, row)))
            result_data = rows
        else:
            result_data = {'rowcount': result.rowcount}
        
        # Log the action
        log = ActionLog(
            action_type='db_command',
            description=f'SQL command executed: {sql_command[:100]}...' if len(sql_command) > 100 else f'SQL command executed: {sql_command}',
            actor='admin'
        )
        db.session.add(log)
        db.session.commit()
        
        # Log the event
        current_app.logger.info(f'SQL command executed: {sql_command}')
        
        return True, result_data
    
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'SQL command failed: {str(e)}')
        return False, str(e)
