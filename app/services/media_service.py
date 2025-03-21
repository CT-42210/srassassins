import os
import subprocess
from flask import current_app


def process_video(input_path, quality='high'):
    """
    Process video for web display - reformats to MP4/H.264/AAC and compresses in one operation.

    Args:
        input_path (str): Path to the input video file
        quality (str): Compression quality: 'low', 'medium', 'high', or 'extreme'

    Returns:
        str: Path to the processed video (same as input_path)
    """
    # Create a temporary filename for processed output
    temp_output = f"{input_path}_processed_temp.mp4"

    # Configure settings based on quality level
    crf_values = {
        'low': '23',  # Good quality, moderate compression
        'medium': '28',  # Medium compression, decent quality
        'high': '30',  # High compression, acceptable quality
        'extreme': '35',  # Extreme compression, lower quality
    }

    scale_values = {
        'low': '1280:-2',  # 720p
        'medium': '854:-2',  # 480p
        'high': '640:-2',  # 360p
        'extreme': '426:-2'  # 240p
    }

    audio_bitrates = {
        'low': '128k',
        'medium': '96k',
        'high': '64k',
        'extreme': '32k'
    }

    # Use provided quality or default to high
    quality_level = quality if quality in crf_values else 'high'

    try:
        # FFmpeg command for web optimization and compression in one step
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',  # H.264 video codec
            '-profile:v', 'main',  # Mainstream compatibility profile
            '-preset', 'medium',  # Balance between speed and compression
            '-crf', crf_values[quality_level],
            '-vf', f"scale={scale_values[quality_level]}",
            '-movflags', '+faststart',  # Optimize for web streaming
            '-c:a', 'aac',  # AAC audio codec
            '-b:a', audio_bitrates[quality_level],
            '-y',  # Overwrite output if exists
            temp_output
        ]

        # Execute FFmpeg
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if processing succeeded
        if os.path.exists(temp_output):
            original_size = os.path.getsize(input_path) / (1024 * 1024)
            processed_size = os.path.getsize(temp_output) / (1024 * 1024)

            current_app.logger.info(
                f"Processed video: {os.path.basename(input_path)} "
                f"({original_size:.2f}MB → {processed_size:.2f}MB, "
                f"reduction: {100 - (processed_size / original_size * 100):.1f}%)"
            )

            # Replace the original file with the processed version
            os.remove(input_path)
            os.rename(temp_output, input_path)

    except Exception as e:
        current_app.logger.error(f"Video processing failed: {str(e)}")
        # Clean up temporary file if it exists
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass
