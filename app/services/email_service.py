import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template
from app.models import Player, Team, db

def send_email(subject, recipients, text_body, html_body=None):
    """
    Send an email with the given subject and body to the specified recipients.
    
    Args:
        subject (str): Email subject
        recipients (list): List of email addresses
        text_body (str): Plain text email body
        html_body (str, optional): HTML email body
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = ', '.join(recipients)
        
        # Attach text part
        text_part = MIMEText(text_body, 'plain')
        msg.attach(text_part)
        
        # Attach HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
        
        # Connect to the mail server
        server = smtplib.SMTP(
            current_app.config['MAIL_SERVER'],
            current_app.config['MAIL_PORT']
        )
        
        if current_app.config['MAIL_USE_TLS']:
            server.starttls()
        
        # Login if credentials are provided
        if current_app.config['MAIL_USERNAME'] and current_app.config['MAIL_PASSWORD']:
            server.login(
                current_app.config['MAIL_USERNAME'],
                current_app.config['MAIL_PASSWORD']
            )
        
        # Send the email
        server.sendmail(
            current_app.config['MAIL_DEFAULT_SENDER'],
            recipients,
            msg.as_string()
        )
        
        # Close the connection
        server.quit()
        
        current_app.logger.info(f'Email sent to {len(recipients)} recipients: {subject}')
        return True
    
    except Exception as e:
        current_app.logger.error(f'Failed to send email: {str(e)}')
        return False

def send_all_players_email(subject, text_body, html_body=None):
    """Send an email to all players in the game."""
    players = Player.query.all()
    recipients = [player.email for player in players]
    
    if recipients:
        return send_email(subject, recipients, text_body, html_body)
    return False

def send_team_email(team_id, subject, text_body, html_body=None):
    """Send an email to all players in a specific team."""
    players = Player.query.filter_by(team_id=team_id).all()
    recipients = [player.email for player in players]
    
    if recipients:
        return send_email(subject, recipients, text_body, html_body)
    return False

def send_new_round_notification(round_number):
    """Send a notification email about a new round starting."""
    subject = f"Senior Assassin - Round {round_number} Started"
    
    text_body = f"""
    Round {round_number} of Senior Assassin has begun!
    
    A new target has been assigned to your team. Log in to the game portal to see your new assignment.
    
    Good luck and happy hunting!
    """
    
    html_body = render_template(
        'email/new_round_notification.html',
        round_number=round_number
    )
    
    return send_all_players_email(subject, text_body, html_body)

def send_kill_submission_notification(kill_confirmation):
    """
    Send a notification email about a kill submission that needs to be voted on.
    
    Args:
        kill_confirmation: KillConfirmation object
    """
    subject = "Senior Assassin - New Kill Submission Requires Your Vote"
    
    # Get victim and attacker info
    victim = Player.query.get(kill_confirmation.victim_id)
    attacker = Player.query.get(kill_confirmation.attacker_id)
    victim_team = Team.query.get(victim.team_id)
    attacker_team = Team.query.get(attacker.team_id)
    
    # Create the email body
    text_body = f"""
    A new kill has been submitted and requires your vote.
    
    Attacker: {attacker.name} from Team {attacker_team.name}
    Victim: {victim.name} from Team {victim_team.name}
    Time of Kill: {kill_confirmation.kill_time.strftime('%Y-%m-%d %H:%M')}
    Round: {kill_confirmation.round_number}
    
    Please log in to the game portal to review the kill submission video and cast your vote.
    Your vote must be submitted within 24 hours.
    """
    
    html_body = render_template(
        'email/kill_submission_notification.html',
        victim=victim,
        attacker=attacker,
        victim_team=victim_team,
        attacker_team=attacker_team,
        kill_confirmation=kill_confirmation
    )
    
    # Send to all players except the attacker and victim
    players = Player.query.filter(
        Player.id != victim.id,
        Player.id != attacker.id
    ).all()
    
    recipients = [player.email for player in players]
    
    if recipients:
        return send_email(subject, recipients, text_body, html_body)
    return False

def send_kill_confirmation_result(kill_confirmation):
    """
    Send an email about the result of a kill confirmation vote.
    
    Args:
        kill_confirmation: KillConfirmation object
    """
    result = "approved" if kill_confirmation.is_approved else "rejected"
    subject = f"Senior Assassin - Kill Submission {result.capitalize()}"
    
    # Get victim and attacker info
    victim = Player.query.get(kill_confirmation.victim_id)
    attacker = Player.query.get(kill_confirmation.attacker_id)
    victim_team = Team.query.get(victim.team_id)
    attacker_team = Team.query.get(attacker.team_id)
    
    # Create the email body
    text_body = f"""
    The kill submission has been {result}.
    
    Attacker: {attacker.name} from Team {attacker_team.name}
    Victim: {victim.name} from Team {victim_team.name}
    Time of Kill: {kill_confirmation.kill_time.strftime('%Y-%m-%d %H:%M')}
    Round: {kill_confirmation.round_number}
    
    {"The victim has been marked as eliminated." if kill_confirmation.is_approved else "The victim remains active in the game."}
    """
    
    html_body = render_template(
        'email/kill_confirmation_result.html',
        result=result,
        victim=victim,
        attacker=attacker,
        victim_team=victim_team,
        attacker_team=attacker_team,
        kill_confirmation=kill_confirmation
    )
    
    # Send to all players
    return send_all_players_email(subject, text_body, html_body)
