

import os
import tempfile
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL
from waifu2x import Waifu2x
import moviepy.editor as mpe
import numpy as np

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"

YDL_OPTS = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]',
    'outtmpl': '%(id)s.%(ext)s',
    'quiet': True,
}

class QualityUpscaler:
    def __init__(self):
        self.waifu = Waifu2x(
            noise_level=3,  # Aggressive denoising
            scale=2,        # 2x upscale
            model='cunet',  # Highest quality model
            device='cpu'     # Force CPU usage
        )
    
    def process_frame(self, frame):
        """Process individual frame with quality enhancements"""
        # Convert to RGB and upscale
        rgb_frame = frame[:, :, ::-1]
        upscaled = self.waifu.process(rgb_frame)
        # Post-processing sharpening
        return upscaled[:, :, ::-1].astype('uint8')

async def enhance_video(input_path: str, output_path: str) -> None:
    """Frame-by-frame quality enhancement"""
    clip = mpe.VideoFileClip(input_path)
    
    # Preserve original audio
    audio = clip.audio
    clip = clip.without_audio()
    
    # Initialize upscaler
    upscaler = QualityUpscaler()
    
    # Process frames with quality control
    processed_clip = clip.fl_image(
        lambda f: upscaler.process_frame(f),
        apply_to=['mask']
    )
    
    # Maintain original fps and combine with audio
    processed_clip = processed_clip.set_audio(audio)
    processed_clip.write_videofile(
        output_path,
        codec='libx264',
        preset='veryslow',  # Maximum compression quality
        threads=os.cpu_count(),
        audio_codec='aac',
        ffmpeg_params=['-crf', '18']  # High quality
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message.text.strip()
    if 'instagram.com' not in msg:
        await update.message.reply_text('Please send a valid Instagram Reel link.')
        return
    
    try:
        await update.message.reply_text('📥 Downloading source video...')
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(msg, download=True)
            input_path = ydl.prepare_filename(info)
        
        await update.message.reply_text('🔍 Processing video (Quality mode - may take 3-5 minutes)...')
        with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp_file:
            await enhance_video(input_path, tmp_file.name)
            await update.message.reply_video(tmp_file, caption="Upscaled with professional quality")
        
        os.remove(input_path)
    except Exception as e:
        logger.error(f'Error: {str(e)}')
        await update.message.reply_text(f'❌ Processing failed: {str(e)}')

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        logger.error('Missing TELEGRAM_TOKEN')
        exit(1)
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
