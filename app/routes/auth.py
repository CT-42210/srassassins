import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from datetime import datetime

from app.models import db, Team, Player, GameState, ActionLog
from app.services.email_service import send_team_signup_notification

auth = Blueprint('auth', __name__)


def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle player login."""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('game.home'))

    # Get game state
    game_state = GameState.query.first()

    # Only allow login during live game or admin login
    if game_state.state not in ['live', 'post'] and 'admin_login' not in request.args:
        flash('The game is not currently active.', 'danger')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Check if it's an admin login
        if 'admin_login' in request.args:
            # Redirect to admin login
            return redirect(url_for('admin.login', email=email, password=password))

        # Find player by email
        player = Player.query.filter_by(email=email).first()

        if player and player.check_password(password):
            # Log in the player
            login_user(player)

            # Log the action
            log = ActionLog(
                action_type='player_login',
                description=f'Player {player.name} logged in',
                actor=player.name
            )
            db.session.add(log)
            db.session.commit()

            # Redirect to next page or home
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('game.home'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html', now=datetime.now())


@auth.route('/logout')
@login_required
def logout():
    """Handle player logout."""
    # Log the action
    log = ActionLog(
        action_type='player_logout',
        description=f'Player {current_user.name} logged out',
        actor=current_user.name
    )
    db.session.add(log)
    db.session.commit()

    # Log out the player
    logout_user()

    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handle team and player registration."""
    # Get game state
    game_state = GameState.query.first()

    # Only allow signup during pre-game
    if game_state.state != 'pre':
        flash('Team registration is closed.', 'danger')
        return redirect(url_for('main.index'))

    # Check which step of the signup process we're on
    step = session.get('signup_step', 1)

    if step == 1:
        # Step 1: Display rules and get acknowledgement
        if request.method == 'POST':
            # Check if rules were acknowledged
            if 'rules_acknowledged' in request.form:
                # Move to step 2
                session['signup_step'] = 2
                return redirect(url_for('auth.signup'))
            else:
                flash('You must acknowledge the rules to continue.', 'danger')

        return render_template('signup/step1.html', now=datetime.now())

    elif step == 2:
        # Step 2: Enter team name and number of players
        if request.method == 'POST':
            team_name = request.form.get('team_name')
            player_count = int(request.form.get('player_count', 1))

            # Validate inputs
            if not team_name:
                flash('Please enter a team name.', 'danger')
                return render_template('signup/step2.html', now=datetime.now())

            if player_count not in [1, 2]:
                flash('Player count must be 1 or 2.', 'danger')
                return render_template('signup/step2.html', now=datetime.now())

            # Check if team name is already taken
            if Team.query.filter_by(name=team_name).first():
                flash('Team name is already taken.', 'danger')
                return render_template('signup/step2.html', now=datetime.now())

            # Store data in session
            session['team_name'] = team_name
            session['player_count'] = player_count

            # Move to step 3
            session['signup_step'] = 3
            return redirect(url_for('auth.signup'))

        return render_template('signup/step2.html', now=datetime.now())

    elif step == 3:
        # Step 3: Enter player one information
        if request.method == 'POST':
            player_name = request.form.get('player_name')
            player_email = request.form.get('player_email')
            player_phone = request.form.get('player_phone')
            player_address = request.form.get('player_address')
            player_password = request.form.get('player_password')
            player_password_confirm = request.form.get('player_password_confirm')

            # Validate inputs
            if not all([player_name, player_email, player_phone, player_address, player_password]):
                flash('All fields are required.', 'danger')
                return render_template('signup/step3.html', now=datetime.now())

            if player_password != player_password_confirm:
                flash('Passwords do not match.', 'danger')
                return render_template('signup/step3.html', now=datetime.now())

            # Check if email is already registered
            if Player.query.filter_by(email=player_email).first():
                flash('Email is already registered.', 'danger')
                return render_template('signup/step3.html', now=datetime.now())

            # Store data in session
            session['player1_name'] = player_name
            session['player1_email'] = player_email
            session['player1_phone'] = player_phone
            session['player1_address'] = player_address
            session['player1_password'] = player_password

            # Move to step 4 if there's a second player, otherwise step 5
            if session.get('player_count') == 2:
                session['signup_step'] = 4
            else:
                session['signup_step'] = 5

            return redirect(url_for('auth.signup'))

        return render_template('signup/step3.html', now=datetime.now())

    elif step == 4:
        # Step 4: Enter player two information
        if request.method == 'POST':
            player_name = request.form.get('player_name')
            player_email = request.form.get('player_email')
            player_phone = request.form.get('player_phone')
            player_address = request.form.get('player_address')
            player_password = request.form.get('player_password')
            player_password_confirm = request.form.get('player_password_confirm')

            # Validate inputs
            if not all([player_name, player_email, player_phone, player_address, player_password]):
                flash('All fields are required.', 'danger')
                return render_template('signup/step4.html', now=datetime.now())

            if player_password != player_password_confirm:
                flash('Passwords do not match.', 'danger')
                return render_template('signup/step4.html', now=datetime.now())

            # Check if email is already registered
            if Player.query.filter_by(email=player_email).first():
                flash('Email is already registered.', 'danger')
                return render_template('signup/step4.html', now=datetime.now())

            # Check if email is different from player one
            if player_email == session.get('player1_email'):
                flash('Player two must have a different email.', 'danger')
                return render_template('signup/step4.html', now=datetime.now())

            # Store data in session
            session['player2_name'] = player_name
            session['player2_email'] = player_email
            session['player2_phone'] = player_phone
            session['player2_address'] = player_address
            session['player2_password'] = player_password

            # Move to step 5
            session['signup_step'] = 5
            return redirect(url_for('auth.signup'))

        return render_template('signup/step4.html', now=datetime.now())

    elif step == 5:
        # Step 5: Upload team photo and complete registration
        if request.method == 'POST':
            # Check if a file was uploaded
            if 'team_photo' not in request.files:
                flash('No file selected.', 'danger')
                return render_template('signup/step5.html', now=datetime.now())

            file = request.files['team_photo']

            # Check if file is empty
            if file.filename == '':
                flash('No file selected.', 'danger')
                return render_template('signup/step5.html', now=datetime.now())

            # Check if file has allowed extension
            if not allowed_file(file.filename):
                flash('Invalid file type. Allowed types: png, jpg, jpeg, gif.', 'danger')
                return render_template('signup/step5.html', now=datetime.now())

            # Save the file
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)

            relative_path = f"uploads/{unique_filename}"

            # Then update the Team creation:
            team = Team(
                name=session.get('team_name'),
                photo_path=relative_path,  # Store the relative path
                state='pending'
            )
            db.session.add(team)
            # Flush to generate an ID for the team without committing
            db.session.flush()

            # Create player one
            player1 = Player(
                name=session.get('player1_name'),
                email=session.get('player1_email'),
                phone=session.get('player1_phone'),
                address=session.get('player1_address'),
                state='alive',
                team_id=team.id  # Now team.id will be a valid ID
            )
            player1.set_password(session.get('player1_password'))
            db.session.add(player1)

            # Create player two if applicable
            if session.get('player_count') == 2:
                player2 = Player(
                    name=session.get('player2_name'),
                    email=session.get('player2_email'),
                    phone=session.get('player2_phone'),
                    address=session.get('player2_address'),
                    state='alive',
                    team_id=team.id  # Now team.id will be a valid ID
                )
                player2.set_password(session.get('player2_password'))
                db.session.add(player2)

            # Log the action
            log = ActionLog(
                action_type='team_registration',
                description=f'Team {team.name} registered with {session.get("player_count")} players',
                actor='system'
            )
            db.session.add(log)

            # Commit changes
            db.session.commit()

            # Send team signup notification email with payment instructions
            send_team_signup_notification(team.id)

            # Clear session data
            for key in ['signup_step', 'team_name', 'player_count',
                        'player1_name', 'player1_email', 'player1_phone', 'player1_address', 'player1_password',
                        'player2_name', 'player2_email', 'player2_phone', 'player2_address', 'player2_password']:
                if key in session:
                    session.pop(key)

            flash(
                'Registration successful! Please check your email for payment instructions. Your team will be approved by an administrator once payment is received and the game begins.',
                'success')
            return redirect(url_for('main.index'))

        return render_template('signup/step5.html', now=datetime.now())

    # Invalid step, start over
    session['signup_step'] = 1
    return redirect(url_for('auth.signup'))


@auth.route('/signup/back')
def signup_back():
    """
    Go back to the previous signup step.
    """
    step = session.get('signup_step', 1)

    if step > 1:
        session['signup_step'] = step - 1

    return redirect(url_for('auth.signup'))


@auth.route('/signup/reset')
def signup_reset():
    """
    Reset the signup process.
    """
    # Clear session data
    for key in ['signup_step', 'team_name', 'player_count',
                'player1_name', 'player1_email', 'player1_phone', 'player1_address', 'player1_password',
                'player2_name', 'player2_email', 'player2_phone', 'player2_address', 'player2_password']:
        if key in session:
            session.pop(key)

    return redirect(url_for('auth.signup'))
