import os
import subprocess
import tempfile
import shutil
from flask import current_app

def process_video(input_path, output_quality='medium', convert_to_mp4=False):
    """
    Compresses video files and converts to MP4 format if needed.
    Args:
        input_path (str): Path to the input video file (.mp4 or .mov)
        output_quality (str): Compression quality: 'low', 'medium', 'high', or 'custom'
        convert_to_mp4 (bool): Always convert to MP4 even if compression isn't needed
    """
    # Check if input file exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Get file extension and check if conversion is needed
    _, ext = os.path.splitext(input_path)
    ext = ext.lower()

    # Set output path to temporary file first
    temp_dir = tempfile.gettempdir()
    temp_output = os.path.join(temp_dir, f"temp_output_{os.path.basename(input_path)}.mp4")

    # Determine if conversion is needed based on file extension
    needs_conversion = ext not in ['.mp4'] or convert_to_mp4

    # Map quality settings to FFmpeg parameters
    quality_settings = {
        'low': ['-crf', '28', '-preset', 'faster'],
        'medium': ['-crf', '23', '-preset', 'medium'],
        'high': ['-crf', '18', '-preset', 'slow'],
        'custom': ['-crf', '20', '-preset', 'medium']  # Default custom settings
    }

    # Use medium quality if invalid quality is specified
    if output_quality not in quality_settings:
        print(f"Warning: Invalid quality '{output_quality}'. Using 'medium' instead.")
        output_quality = 'medium'

    # Build FFmpeg command
    ffmpeg_cmd = ['ffmpeg', '-i', input_path, '-y']

    # Add quality settings
    ffmpeg_cmd.extend(quality_settings[output_quality])

    # Ensure output is mp4 with h264 codec for compatibility
    ffmpeg_cmd.extend(['-c:v', 'libx264', '-movflags', '+faststart'])

    # Copy audio stream without re-encoding if it exists
    ffmpeg_cmd.extend(['-c:a', 'aac', '-b:a', '128k'])

    # Add output path
    ffmpeg_cmd.append(temp_output)

    try:
        # Execute FFmpeg command
        print(f"Processing video: {input_path}")
        print(f"Command: {' '.join(ffmpeg_cmd)}")
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Replace original file with compressed version
        print(f"Replacing original file with compressed version")

        # Create a backup of the original file
        backup_path = input_path + ".backup"
        shutil.copy2(input_path, backup_path)

        # Replace the original with the compressed version
        shutil.move(temp_output, input_path)

        # Remove backup if everything went well
        os.remove(backup_path)

        print(f"Video compression complete: {input_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error processing video: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False


# Example usage:
if __name__ == "__main__":
    # Example: compress a video file
    # compress_video("path/to/video.mov", output_quality="medium", convert_to_mp4=True)
    pass