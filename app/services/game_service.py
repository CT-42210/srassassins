import json
import datetime
import json
import random

from app.models import db, Team, Player, GameState, KillConfirmation, KillVote, ActionLog
from app.services.email_service import send_kill_submission_notification
from app.services.admin_email_service import send_admin_targets

def assign_targets():
    """
    Randomly assign target teams to each alive team.

    Returns:
        bool: True if successful, False otherwise
    """
    # Get all alive teams
    alive_teams = Team.query.filter_by(state='alive').all()

    # If less than 2 teams are alive, can't assign targets
    if len(alive_teams) < 2:
        return False

    # Shuffle the teams
    random.shuffle(alive_teams)

    # Assign targets in a circular fashion
    for i in range(len(alive_teams)):
        current_team = alive_teams[i]
        target_team = alive_teams[(i + 1) % len(alive_teams)]
        current_team.target_id = target_team.id

    # Log the action
    log = ActionLog(
        action_type='target_assignment',
        description=f'Targets assigned to {len(alive_teams)} teams',
        actor='system'
    )
    db.session.add(log)

    # Commit changes
    db.session.commit()

    # Send assignment summary to admin
    send_admin_targets(alive_teams)

    return True


def increment_rounds():
    game_state = GameState.query.first()
    game_state.round_start = datetime.datetime.now()
    game_state.round_number += 1


def game_logic():
    """
    Implements game rules for round transitions:
    - If a team eliminated all their targets, they move on and any eliminated players are revived
    - If a team eliminated at least one target, they move on (eliminated players stay dead)
    - If a team didn't eliminate any targets, the entire team is eliminated
    """
    game_state = GameState.query.first()
    alive_teams = Team.query.filter_by(state='alive').all()

    # Add debug logs
    print(f"Game logic - Round {game_state.round_number} - Processing {len(alive_teams)} alive teams")

    # Track teams to be eliminated
    teams_to_eliminate = []

    # Check each team's performance
    for team in alive_teams:
        # Get the team's current target
        target_team = Team.query.get(team.target_id) if team.target_id else None
        if not target_team:
            print(f"Team {team.name} has no target, skipping")
            continue

        # Get target team's players
        target_players = Player.query.filter_by(team_id=target_team.id).all()

        # Count how many of the target's players were eliminated (by any means)
        eliminated_count = 0
        total_targets = len(target_players)

        print(f"Team {team.name} targeting {target_team.name} with {total_targets} players")

        for target_player in target_players:
            # Check if this player is eliminated (by any means - not just through obituaries)
            if not target_player.is_alive:
                eliminated_count += 1
                print(f"Found eliminated player: {target_player.name}")

        print(f"Team {team.name} eliminated {eliminated_count}/{total_targets} targets")

        # Apply game rules
        if eliminated_count == 0:
            # Rule: Team didn't eliminate any targets, they're eliminated
            print(f"Team {team.name} eliminated 0 targets - marking for elimination")
            teams_to_eliminate.append(team)
        elif eliminated_count == total_targets:
            # Rule: Team eliminated all targets, revive any dead players
            print(f"Team {team.name} eliminated all targets - reviving dead members")
            for player in Player.query.filter_by(team_id=team.id).all():
                if not player.is_alive:
                    player.state = 'alive'
                    print(f"Reviving player {player.name}")

                    # Log the revival
                    log = ActionLog(
                        action_type='player_revival',
                        description=f'Player {player.name} revived for round {game_state.round_number}',
                        actor='system'
                    )
                    db.session.add(log)
        else:
            # Rule: Team eliminated some but not all targets - they move on but dead players stay dead
            print(f"Team {team.name} eliminated some targets - advancing without revival")

    # Process team eliminations
    print(f"Processing {len(teams_to_eliminate)} teams for elimination")
    for team in teams_to_eliminate:
        team.state = 'dead'
        print(f"Marking team {team.name} as dead")

        # Mark all team members as dead - ONLY for the teams that failed
        team_players = Player.query.filter_by(team_id=team.id).all()
        for player in team_players:
            player.state = 'dead'
            print(f"Marking player {player.name} from team {team.name} as dead")

        # Log the team elimination
        log = ActionLog(
            action_type='team_elimination',
            description=f'Team {team.name} eliminated in round {game_state.round_number} for failing to eliminate targets',
            actor='system'
        )
        db.session.add(log)

    # Commit all changes
    db.session.commit()
    print("Game logic complete - changes committed")

    check_game_complete()


def submit_kill(victim_id, attacker_id, kill_time, video_path):
    """
    Submit a kill for confirmation.
    
    Args:
        victim_id (str): ID of the victim player
        attacker_id (str): ID of the attacker player
        kill_time (datetime): Time of the kill
        video_path (str): Path to the kill video
    
    Returns:
        KillConfirmation: Created kill confirmation, or None if failed
    """
    print("trace")
    # Get game state
    game_state = GameState.query.first()
    
    # Get the players
    victim = Player.query.get(victim_id)
    attacker = Player.query.get(attacker_id)
    
    if not victim or not attacker:
        return None
    
    # Check if players are alive
    if not victim.is_alive or not attacker.is_alive:
        return None

    # check if free for all is enabled
    if not game_state.free_for_all:
        # Check if victim's team is the attacker's target
        attacker_team = Team.query.get(attacker.team_id)
        victim_team = Team.query.get(victim.team_id)
    
        if attacker_team.target_id != victim_team.id:
            return None

    existing_kill = KillConfirmation.query.filter_by(
        victim_id=victim_id,
        status='pending'
    ).first()

    if existing_kill:
        return None

    # Create a new kill confirmation
    kill_confirmation = KillConfirmation(
        victim_id=victim_id,
        attacker_id=attacker_id,
        kill_time=kill_time,
        round_number=game_state.round_number,
        video_path=video_path,
        status='pending',
        expiration_time=datetime.datetime.now() + datetime.timedelta(hours=24)
    )
    
    db.session.add(kill_confirmation)
    
    # Log the action
    log = ActionLog(
        action_type='kill_submission',
        description=f'Kill submitted: {attacker.name} -> {victim.name}',
        actor=attacker.name
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Send notifications
    send_kill_submission_notification(kill_confirmation)

    return kill_confirmation

def vote_on_kill(kill_confirmation_id, voter_id, vote):
    """
    Submit a vote on a kill confirmation.
    
    Args:
        kill_confirmation_id (str): ID of the kill confirmation
        voter_id (str): ID of the voter
        vote (bool): True to approve, False to reject
    
    Returns:
        tuple: (bool, str) - (success, message)
    """
    # Get the kill confirmation
    kill_confirmation = KillConfirmation.query.get(kill_confirmation_id)
    voter = Player.query.get(voter_id)
    
    if not kill_confirmation or not voter:
        return False, "Invalid kill confirmation or voter"
    
    # Check if kill confirmation is still pending
    if not kill_confirmation.is_pending:
        return False, "Kill confirmation is no longer pending"
    
    # Check if vote has expired
    if kill_confirmation.expiration_time < datetime.datetime.now():
        # Auto-reject expired confirmations
        kill_confirmation.status = 'rejected'
        
        # Log the action
        log = ActionLog(
            action_type='kill_expired',
            description=f'Kill confirmation {kill_confirmation_id} expired and auto-rejected',
            actor='system'
        )
        db.session.add(log)
        db.session.commit()
        
        return False, "Kill confirmation has expired"
    
    # Check if voter is the victim or attacker
    if voter_id == kill_confirmation.victim_id or voter_id == kill_confirmation.attacker_id:
        return False, "You cannot vote on your own kill confirmation"
    
    # Check if voter has already voted
    existing_vote = KillVote.query.filter_by(
        kill_confirmation_id=kill_confirmation_id,
        voter_id=voter_id
    ).first()
    
    if existing_vote:
        return False, "You have already voted on this kill confirmation"
    
    # Create a new vote
    kill_vote = KillVote(
        kill_confirmation_id=kill_confirmation_id,
        voter_id=voter_id,
        vote=vote
    )
    db.session.add(kill_vote)
    
    # Log the action
    log = ActionLog(
        action_type='kill_vote',
        description=f'Vote submitted on kill confirmation {kill_confirmation_id}: {"approve" if vote else "reject"}',
        actor=voter.name
    )
    db.session.add(log)
    
    # Check if voting threshold reached
    game_state = GameState.query.first()
    threshold = game_state.voting_threshold
    
    # Get updated vote counts
    db.session.flush()
    approve_votes = sum(1 for v in kill_confirmation.votes if v.vote)
    reject_votes = sum(1 for v in kill_confirmation.votes if not v.vote)
    
    # Determine if threshold reached
    if approve_votes >= threshold:
        kill_confirmation.status = 'approved'
        confirm_kill(kill_confirmation)
        message = "Kill confirmed"
    elif reject_votes >= threshold:
        kill_confirmation.status = 'rejected'
        message = "Kill rejected"
    else:
        message = "Vote recorded"
    
    # Commit changes
    db.session.commit()
    
    # Send notification if status changed
    if kill_confirmation.status in ['approved', 'rejected']:
        pass
        # send to ellie
    
    return True, message

def confirm_kill(kill_confirmation):
    """
    Process a confirmed kill.
    
    Args:
        kill_confirmation: KillConfirmation object
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get the victim
    victim = Player.query.get(kill_confirmation.victim_id)
    attacker = Player.query.get(kill_confirmation.attacker_id)
    
    # Set victim as dead
    victim.state = 'dead'
    
    # Set obituary data
    obituary_data = {
        'round': kill_confirmation.round_number,
        'killer': attacker.name,
        'time': kill_confirmation.kill_time.isoformat()
    }
    victim.obituary = json.dumps(obituary_data)
    
    # Update attacker team's elimination count
    attacker_team = Team.query.get(attacker.team_id)
    attacker_team.eliminations += 1
    
    # Check if victim's team is now dead
    victim_team = Team.query.get(victim.team_id)
    if all(not player.is_alive for player in victim_team.players):
        victim_team.state = 'dead'

    
    # Log the action
    log = ActionLog(
        action_type='kill_confirmed',
        description=f'Kill confirmed: {attacker.name} eliminated {victim.name}',
        actor='system'
    )
    db.session.add(log)
    
    # Commit changes
    db.session.commit()
    
    # Check if game is complete
    check_game_complete()
    
    return True

def check_game_complete():
    """
    Check if the game is complete (only one team left alive).
    
    Returns:
        bool: True if game is complete, False otherwise
    """
    # Get game state
    game_state = GameState.query.first()
    
    # If game is not live, no need to check
    if game_state.state != 'live':
        return False
    
    # Count alive teams
    alive_teams = Team.query.filter_by(state='alive').all()
    
    # If only one team is alive, game is complete
    if len(alive_teams) == 1:
        # Change game state to post
        game_state.state = 'post'
        
        # Get the winning team
        winning_team = alive_teams[0]
        
        # Log the action
        log = ActionLog(
            action_type='game_complete',
            description=f'Game complete. Winner: Team {winning_team.name}',
            actor='system'
        )
        db.session.add(log)
        
        # Commit changes
        db.session.commit()
        
        return True
    
    return False

def get_kill_confirmations_for_voter(voter_id):
    """
    Get all pending kill confirmations for a voter.
    
    Args:
        voter_id (str): ID of the voter
    
    Returns:
        list: List of pending kill confirmations
    """
    # Find all pending kill confirmations
    pending_kills = KillConfirmation.query.filter_by(status='pending').all()
    
    # Filter out confirmations the voter has already voted on
    voted_ids = [vote.kill_confirmation_id for vote in KillVote.query.filter_by(voter_id=voter_id).all()]
    
    # Filter out confirmations where the voter is the victim or attacker
    return [
        kill for kill in pending_kills 
        if kill.id not in voted_ids 
        and kill.victim_id != voter_id 
        and kill.attacker_id != voter_id
        and kill.expiration_time > datetime.datetime.now()
    ]

def get_leaderboard():
    """
    Get the game leaderboard.
    
    Returns:
        list: List of teams sorted by status and eliminations
    """
    # Get all teams
    teams = Team.query.all()
    
    # Get player data for each team
    leaderboard = []
    for team in teams:
        players = Player.query.filter_by(team_id=team.id).all()
        
        leaderboard.append({
            'team_id': team.id,
            'team_name': team.name,
            'state': team.state,
            'eliminations': team.eliminations,
            'players': [
                {
                    'player_id': player.id,
                    'player_name': player.name,
                    'state': player.state
                } for player in players
            ]
        })
    
    # Sort the leaderboard:
    # 1. Alive teams first
    # 2. Then by number of eliminations (descending)
    # 3. Then dead teams by number of eliminations (descending)
    leaderboard.sort(key=lambda x: (
        0 if x['state'] == 'alive' else 1,
        -x['eliminations']
    ))
    
    return leaderboard

def schedule_round_transitions(app):
    """
    Schedule the automatic start/end of rounds based on the game state.
    
    Args:
        app: Flask application instance
    """
    from app import scheduler
    
    # Clear any existing scheduled round transitions
    for job in scheduler.get_jobs():
        if job.id.startswith('round_'):
            job.remove()
    
    with app.app_context():
        # Get game state
        game_state = GameState.query.first()
        
        # If round start/end times are set and game is live, schedule transitions
        if game_state.state == 'live' and game_state.round_start and game_state.round_end:
            now = datetime.datetime.now()
            
            # Schedule round start if it's in the future
            if game_state.round_start > now:
                scheduler.add_job(
                    start_round,
                    'date', 
                    run_date=game_state.round_start,
                    id=f'round_start_{game_state.round_number}',
                    args=[app]
                )
            
            # Schedule round end and start of next round
            if game_state.round_end > now:
                scheduler.add_job(
                    end_round_start_next,
                    'date', 
                    run_date=game_state.round_end,
                    id=f'round_end_{game_state.round_number}',
                    args=[app]
                )


def start_round(app=None):
    """
    Start the current round.

    Args:
        app: Flask application instance (optional)
    """
    if app:
        with app.app_context():
            from app.services.admin_service import start_round as admin_start_round
            admin_start_round(increment=False)
    else:
        from app.services.admin_service import start_round as admin_start_round
        admin_start_round(increment=False)


def end_round_start_next(app=None):
    """
    End the current round and start the next one.
    
    Args:
        app: Flask application instance (optional)
    """
    if app:
        with app.app_context():
            _do_end_round_start_next()
    else:
        _do_end_round_start_next()

def _do_end_round_start_next():
    """
    Internal function to end the current round and start the next one.
    """
    # Get game state
    game_state = GameState.query.first()
    
    # Check if game is still live
    if game_state.state != 'live':
        return
    
    # Log end of round
    log = ActionLog(
        action_type='round_end',
        description=f'Round {game_state.round_number} ended',
        actor='system'
    )
    db.session.add(log)
    
    # Start new round
    from app.services.admin_service import start_round as admin_start_round
    admin_start_round(increment=True)
