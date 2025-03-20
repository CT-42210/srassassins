from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from functools import wraps
from datetime import datetime

from app.models import db, Team, Player, GameState, KillConfirmation, ActionLog
from app.services.admin_service import (
    verify_admin_password, get_admin_dashboard_data, accept_team, 
    change_game_state, start_round, set_round_schedule, 
    toggle_team_state, toggle_player_state, force_vote_decision,
    backup_database, execute_db_command
)

admin = Blueprint('admin', __name__)

def admin_required(f):
    """
    Decorator to ensure the user is authenticated as an admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle admin login.
    """
    if request.method == 'POST':
        password = request.form.get('password')
        
        if verify_admin_password(password):
            # Set admin session
            session['admin_authenticated'] = True
            
            # Log the action
            log = ActionLog(
                action_type='admin_login',
                description='Admin logged in',
                actor='admin'
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid admin password.', 'danger')
    
    return render_template('admin/login.html', now = datetime.now())

@admin.route('/logout')
@admin_required
def logout():
    """
    Handle admin logout.
    """
    # Clear admin session
    session.pop('admin_authenticated', None)
    
    # Log the action
    log = ActionLog(
        action_type='admin_logout',
        description='Admin logged out',
        actor='admin'
    )
    db.session.add(log)
    db.session.commit()
    
    flash('Admin logged out successfully.', 'info')
    return redirect(url_for('main.index'))

@admin.route('/dashboard')
@admin_required
def dashboard():
    """
    Admin dashboard with game overview and controls.
    """
    # Get dashboard data
    dashboard_data = get_admin_dashboard_data()
    
    # Get pending teams for approval
    pending_teams = Team.query.filter_by(state='pending').all()
    
    # Get list of all teams for revive/kill actions
    all_teams = Team.query.order_by(Team.name).all()
    
    # Get list of all players for revive/kill actions
    all_players = Player.query.order_by(Player.name).all()
    
    # Get pending kill confirmations for force decisions
    pending_confirmations = KillConfirmation.query.filter_by(status='pending').all()
    
    return render_template(
        'admin/dashboard.html',
        dashboard=dashboard_data,
        pending_teams=pending_teams,
        all_teams=all_teams,
        all_players=all_players,
        pending_confirmations=pending_confirmations,
        now=datetime.now()
    )

@admin.route('/accept-team/<team_id>')
@admin_required
def approve_team(team_id):
    """
    Accept a pending team into the game.
    
    Args:
        team_id (str): ID of the team to accept
    """
    if accept_team(team_id):
        flash('Team accepted successfully!', 'success')
    else:
        flash('Failed to accept team. Game may have already started.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/change-game-state', methods=['POST'])
@admin_required
def update_game_state():
    """
    Change the game state.
    """
    new_state = request.form.get('game_state')
    confirmation = request.form.get('confirmation') == 'yes'
    
    if not confirmation:
        flash('Please confirm the action by checking the confirmation box.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    if change_game_state(new_state):
        flash(f'Game state changed to "{new_state}" successfully!', 'success')
    else:
        flash('Failed to change game state.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/start-round', methods=['POST'])
@admin_required
def new_round():
    """
    Start a new round of the game.
    """
    confirmation = request.form.get('confirmation') == 'yes'
    
    if not confirmation:
        flash('Please confirm the action by checking the confirmation box.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    if start_round(increment=True):
        flash('New round started successfully!', 'success')
    else:
        flash('Failed to start new round.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/set-schedule', methods=['POST'])
@admin_required
def schedule_round():
    """
    Set the schedule for automated round transitions.
    """
    round_start_str = request.form.get('round_start')
    round_end_str = request.form.get('round_end')
    confirmation = request.form.get('confirmation') == 'yes'
    
    if not confirmation:
        flash('Please confirm the action by checking the confirmation box.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    try:
        # Parse datetime strings
        from datetime import datetime
        round_start = datetime.strptime(round_start_str, '%Y-%m-%dT%H:%M')
        round_end = datetime.strptime(round_end_str, '%Y-%m-%dT%H:%M')
        
        # Ensure end is after start
        if round_end <= round_start:
            flash('Round end time must be after round start time.', 'danger')
            return redirect(url_for('admin.dashboard'))
        
        if set_round_schedule(round_start, round_end):
            flash('Round schedule set successfully!', 'success')
        else:
            flash('Failed to set round schedule.', 'danger')
    
    except ValueError:
        flash('Invalid date/time format.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/toggle-team/<team_id>')
@admin_required
def toggle_team(team_id):
    """
    Toggle a team's state between alive and dead.
    
    Args:
        team_id (str): ID of the team to toggle
    """
    if toggle_team_state(team_id):
        flash('Team state toggled successfully!', 'success')
    else:
        flash('Failed to toggle team state.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/toggle-player/<player_id>')
@admin_required
def toggle_player(player_id):
    """
    Toggle a player's state between alive and dead.
    
    Args:
        player_id (str): ID of the player to toggle
    """
    if toggle_player_state(player_id):
        flash('Player state toggled successfully!', 'success')
    else:
        flash('Failed to toggle player state.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/force-vote/<kill_confirmation_id>/<decision>')
@admin_required
def force_vote(kill_confirmation_id, decision):
    """
    Force a decision on a kill confirmation vote.
    
    Args:
        kill_confirmation_id (str): ID of the kill confirmation
        decision (str): 'approve' or 'reject'
    """
    decision_bool = (decision == 'approve')
    
    if force_vote_decision(kill_confirmation_id, decision_bool):
        flash(f'Kill confirmation {decision} successfully!', 'success')
    else:
        flash('Failed to force vote decision.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/backup-database')
@admin_required
def backup_db():
    """
    Manually backup the database.
    """
    backup_path = backup_database()
    
    if backup_path:
        flash(f'Database backup created at: {backup_path}', 'success')
    else:
        flash('Failed to backup database.', 'danger')
    
    return redirect(url_for('admin.dashboard'))

@admin.route('/execute-sql', methods=['POST'])
@admin_required
def execute_sql():
    """
    Execute a raw SQL command on the database.
    """
    sql_command = request.form.get('sql_command')
    confirmation = request.form.get('confirmation') == 'yes'
    
    if not confirmation:
        flash('Please confirm the action by checking the confirmation box.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    if not sql_command:
        flash('SQL command is required.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    success, result = execute_db_command(sql_command)
    
    if success:
        flash('SQL command executed successfully!', 'success')
        return render_template('admin/sql_result.html', result=result)
    else:
        flash(f'SQL command failed: {result}', 'danger')
        return redirect(url_for('admin.dashboard'))
