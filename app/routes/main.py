from flask import Blueprint, render_template, current_app, redirect, url_for
from flask_login import current_user
from datetime import datetime
from app.models import GameState, Team, Player

main = Blueprint('main', __name__)

@main.route('/')
def index():
    """
    Landing page for the application, displays different content based on game state.
    """
    # Get game state
    game_state = GameState.query.first()
    
    # Get team and player counts
    alive_teams_count = Team.query.filter_by(state='alive').count()
    alive_players_count = Player.query.filter_by(state='alive').count()
    
    if game_state.is_pre:
        # Pre-game landing page
        return render_template(
            'index.html',
            game_state=game_state,
            instagram_username=current_app.config['INSTAGRAM_USERNAME'],
            now = datetime.now()
        )
    
    elif game_state.is_live:
        # Live game landing page
        if current_user.is_authenticated:
            # Redirect to home page if user is logged in
            return redirect(url_for('game.home'))
        
        return render_template(
            'index.html',
            game_state=game_state,
            round_number=game_state.round_number,
            round_end=game_state.round_end,
            alive_teams=alive_teams_count,
            alive_players=alive_players_count,
            now=datetime.now()
        )
    
    elif game_state.is_post:
        # Post-game landing page
        # Find the winning team
        winning_team = Team.query.filter_by(state='alive').first()
        
        # If no winner found, show a message
        if not winning_team:
            return render_template(
                'index.html',
                game_state=game_state,
                no_winner=True,
                now=datetime.now()
            )
        
        # Get winning team players
        winning_players = Player.query.filter_by(team_id=winning_team.id).all()
        
        return render_template(
            'index.html',
            game_state=game_state,
            winning_team=winning_team,
            winning_players=winning_players,
            now=datetime.now()
        )
    
    else:  # Forced end
        # Forced end landing page
        return render_template(
            'index.html',
            game_state=game_state,
            now=datetime.now()
        )

@main.route('/rules')
def rules():
    """
    Display the game rules.
    """
    game_state = GameState.query.first()

    return render_template('rules.html',
                           game_state=game_state,
                           now = datetime.now()
                           )

@main.route('/leaderboard')
def leaderboard():
    """
    Display the game leaderboard.
    """
    # Get leaderboard data
    from app.services.game_service import get_leaderboard
    leaderboard_data = get_leaderboard()
    
    return render_template(
        'leaderboard.html',
        leaderboard=leaderboard_data,
        now = datetime.now()
    )

@main.route('/about')
def about():
    """
    Display information about the game and developer.
    """
    return render_template('about.html', now=datetime.now())
