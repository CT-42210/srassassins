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


def send_alive_players_email(subject, text_body, html_body=None):
    """Send an email to all players that are still alive in the game."""
    players = Player.query.filter_by(state='alive').all()
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

    # Only send to players who are still alive
    return send_alive_players_email(subject, text_body, html_body)


def send_team_signup_notification(team_id):
    """
    Send a notification email to a team that has just signed up with payment instructions.

    Args:
        team_id: ID of the team that signed up
    """
    team = Team.query.get(team_id)
    if not team:
        return False

    subject = "Senior Assassin - Team Registration Confirmation"

    text_body = f"""
    Thank you for registering Team {team.name} for Senior Assassin!

    To complete your registration, please submit the registration fee of $20 per player.

    Payment Options:
    1. Venmo: @SeniorAssassin
    2. Cash: Deliver to the Student Activities Office (Room 204)

    Please include your team name in the payment note/memo.

    Your team will be activated once payment is received and the game begins.
    """

    html_body = render_template(
        'email/team_signup_notification.html',
        team=team
    )

    return send_team_email(team_id, subject, text_body, html_body)


def send_team_approval_notification(team_id):
    """
    Send a notification email to a team that has been approved by an admin.

    Args:
        team_id: ID of the team that was approved
    """
    team = Team.query.get(team_id)
    if not team:
        return False

    subject = "Senior Assassin - Team Approved!"

    text_body = f"""
    Great news! Team {team.name} has been approved and is now active in the Senior Assassin game.

    Log in to the game portal to see your first target assignment.

    Game Rules Reminder:
    - Only use approved water weapons
    - Safe zones include classrooms during school hours, workplaces, and religious activities
    - All eliminations must be recorded on video
    - You have 48 hours to eliminate your target

    Good luck and happy hunting!
    """

    html_body = render_template(
        'email/team_approval_notification.html',
        team=team
    )

    return send_team_email(team_id, subject, text_body, html_body)


def send_team_elimination_notification(team_id):
    """
    Send a notification email to a team that has been eliminated from the game.

    Args:
        team_id: ID of the team that was eliminated
    """
    team = Team.query.get(team_id)
    if not team:
        return False

    subject = "Senior Assassin - Team Elimination"

    text_body = f"""
    Team {team.name}, we regret to inform you that your team has been eliminated from Senior Assassin.

    You made it to round {team.eliminated_in_round}. Congratulations on your performance!

    Although you can no longer hunt, you still play a crucial role in the game. You can continue to log in to:
    - Vote on kill confirmations
    - Watch the game unfold
    - Attend the end-of-game celebration

    Thank you for participating, and we hope you enjoyed the experience!
    """

    html_body = render_template(
        'email/team_elimination_notification.html',
        team=team
    )

    return send_team_email(team_id, subject, text_body, html_body)


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

    # Send to all players
    return send_all_players_email(subject, text_body, html_body)


def send_custom_email(email, subject, content):
    """
    Send a custom plaintext email to a recipient.
    """
    # Use the existing send_email function with the email address as a list
    return send_email(
        subject=subject,
        recipients=[email],
        text_body=content
    )
