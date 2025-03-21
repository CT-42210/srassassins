import os

from flask import current_app
from instagrapi import Client
from instagrapi.exceptions import LoginRequired

from app.models import GameState, Player

# Global Instagram client instance
_instagram_client = None

def get_instagram_client():
    """
    Get a logged-in Instagram client instance.
    
    Returns:
        Client: Logged-in Instagram client instance
    """
    global _instagram_client
    
    if _instagram_client is not None:
        try:
            # Test if the client is still logged in
            _instagram_client.get_timeline_feed()
            return _instagram_client
        except LoginRequired:
            # Client is no longer logged in, create a new one
            _instagram_client = None
    
    # Create and login a new client
    client = Client()
    username = current_app.config['INSTAGRAM_USERNAME']
    password = current_app.config['INSTAGRAM_PASSWORD']
    
    try:
        # Try to load session if it exists
        session_file = os.path.join(current_app.instance_path, 'instagram_session.json')
        if os.path.exists(session_file):
            client.load_settings(session_file)
            client.login(username, password)
        else:
            # Login with credentials
            client.login(username, password)
            # Save session for future use
            os.makedirs(current_app.instance_path, exist_ok=True)
            client.dump_settings(session_file)
        
        _instagram_client = client
        return client
    
    except Exception as e:
        current_app.logger.error(f"Instagram login failed: {str(e)}")
        raise

def post_to_feed(image_path, caption):
    """
    Post an image with a caption to the Instagram feed.
    
    Args:
        image_path (str): Path to the image file
        caption (str): Caption for the post
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = get_instagram_client()
        
        # Upload the photo
        media = client.photo_upload(
            image_path,
            caption
        )
        
        current_app.logger.info(f"Instagram post created: {media.pk}")
        return True
    
    except Exception as e:
        current_app.logger.error(f"Failed to post to Instagram feed: {str(e)}")
        return False

def post_to_story(image_path=None, video_path=None, text=None):
    """
    Post a story to Instagram.
    
    Args:
        image_path (str, optional): Path to the image file
        video_path (str, optional): Path to the video file
        text (str, optional): Text to overlay on the story
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = get_instagram_client()
        
        if video_path:
            # Upload video to story
            media = client.video_upload_to_story(
                video_path,
                caption=text
            )
        elif image_path:
            # Upload image to story
            media = client.photo_upload_to_story(
                image_path,
                caption=text
            )
        else:
            # Create a black background with text
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a black image
            img = Image.new('RGB', (1080, 1920), color='black')
            
            # Add text if provided
            if text:
                # Initialize drawing context
                draw = ImageDraw.Draw(img)
                
                # Use a default font
                try:
                    font = ImageFont.truetype("arial.ttf", 60)
                except IOError:
                    font = ImageFont.load_default()
                
                # Calculate text position for center alignment
                text_width, text_height = draw.textsize(text, font=font)
                position = ((1080 - text_width) / 2, (1920 - text_height) / 2)
                
                # Draw the text
                draw.text(position, text, fill='white', font=font)
            
            # Save the image to a temporary file
            temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'temp_story.jpg')
            img.save(temp_path)
            
            # Upload to story
            media = client.photo_upload_to_story(
                temp_path
            )
            
            # Remove the temporary file
            os.remove(temp_path)
        
        current_app.logger.info(f"Instagram story created: {media.pk}")
        return True
    
    except Exception as e:
        current_app.logger.error(f"Failed to post to Instagram story: {str(e)}")
        return False

def post_kill_video_to_story(kill_confirmation):
    """
    Post a kill confirmation video to Instagram story.
    
    Args:
        kill_confirmation: KillConfirmation object
    
    Returns:
        bool: True if successful, False otherwise
    """
    from app.models import Player, Team
    
    # Get victim and attacker info
    victim = Player.query.get(kill_confirmation.victim_id)
    attacker = Player.query.get(kill_confirmation.attacker_id)
    victim_team = Team.query.get(victim.team_id)
    attacker_team = Team.query.get(attacker.team_id)
    
    # Create caption for the story
    text = f"KILL SUBMISSION\n{attacker.name} ({attacker_team.name}) claims to have eliminated {victim.name} ({victim_team.name})"
    
    # Post to story
    return post_to_story(
        video_path=kill_confirmation.video_path,
        text=text
    )

def post_team_elimination_to_feed(team):
    """
    Post a team elimination announcement to Instagram feed.
    
    Args:
        team: Team object that has been eliminated
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Caption for the post
    caption = f"TEAM ELIMINATED\n\nTeam {team.name} has been completely eliminated from the game!\n\nRound: {GameState.query.first().round_number}"
    
    # Post to feed with team photo
    return post_to_feed(
        image_path=team.photo_path,
        caption=caption
    )

def post_round_start_to_feed(round_number):
    """
    Post a round start announcement to Instagram feed.
    
    Args:
        round_number (int): Current round number
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get count of teams and players still alive
    from app.models import Team, Player

    alive_teams = Team.query.filter_by(state='alive').count()
    alive_players = Player.query.filter_by(state='alive').count()
    
    # Caption for the post
    caption = f"ROUND {round_number} BEGINS\n\n{alive_teams} teams and {alive_players} players remain in the game.\n\nGood luck, and may the odds be ever in your favor!"
    
    # Use a default round start image
    image_path = os.path.join(current_app.root_path, 'static', 'img', 'round_start.jpg')
    
    # Post to feed
    return post_to_feed(
        image_path=image_path,
        caption=caption
    )

def post_game_winner_to_feed(winning_team):
    """
    Post the game winner announcement to Instagram feed.
    
    Args:
        winning_team: Team object that has won the game
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get players in the winning team
    players = Player.query.filter_by(team_id=winning_team.id).all()
    player_names = ', '.join([player.name for player in players])
    
    # Caption for the post
    caption = f"GAME OVER - WE HAVE A WINNER!\n\nCongratulations to Team {winning_team.name} ({player_names}) for winning Senior Assassin!\n\nKill Count: {winning_team.eliminations}\n\nThank you to everyone who participated!"
    
    # Post to feed with team photo
    return post_to_feed(
        image_path=winning_team.photo_path,
        caption=caption
    )
