import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def send_ellie(text_body, video_path, recipients=[], html_body=None):
    from flask import current_app
    recipients = [current_app.config["ELLIEMAIL"]]
    """
    Send an email with the given body text and an attached MP4 video to the specified recipients.
    Args:
        text_body (str): Plain text email body
        video_path (str): Path to the MP4 video file to attach
        recipients (list): List of email addresses
        html_body (str, optional): HTML email body
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if video file exists
        if not os.path.exists(video_path):
            current_app.logger.error(f'Video file not found: {video_path}')
            return False

        msg = MIMEMultipart('mixed')  # Changed to 'mixed' to support attachments
        msg['Subject'] = "New Video for Instagram"
        msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = ', '.join(recipients)

        # Create alternative part for text/html content
        alt_part = MIMEMultipart('alternative')

        # Attach text part
        text_part = MIMEText(text_body, 'plain')
        alt_part.attach(text_part)

        # Attach HTML part if provided
        if html_body:
            html_part = MIMEText(html_body, 'html')
            alt_part.attach(html_part)

        # Add the text/html parts to the message
        msg.attach(alt_part)

        # Attach the video file
        with open(video_path, 'rb') as video_file:
            video_attachment = MIMEApplication(video_file.read())
            video_filename = os.path.basename(video_path)
            video_attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="{video_filename}"'
            )
            video_attachment.add_header('Content-Type', 'video/mp4')
            msg.attach(video_attachment)

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

        current_app.logger.info(f'Email with video attachment sent to Ellie: New Video for Instagram')
        return True

    except Exception as e:
        current_app.logger.error(f'Failed to send email with video: {str(e)}')
        return False