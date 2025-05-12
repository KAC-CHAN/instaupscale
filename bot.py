import os
import logging
import tempfile
import subprocess
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import youtube_dl

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.environ.get('7259559804:AAG3VoiBqnwn8_5BlK51U1UMvccj3urRIdk')
HF_API_TOKEN = os.environ.get('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')
if not TELEGRAM_TOKEN or not HF_API_TOKEN:
    raise RuntimeError("Please set both TELEGRAM_TOKEN and HF_API_TOKEN as environment variables.")

# Hugging Face model for super-resolution
HF_MODEL = 'xinntao/Real-ESRGAN_x4plus'
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HEADERS = {"Authorization": f"Bearer {HF_API_TOKEN}"}

# Download Instagram Reel using youtube_dl

def download_reel(url: str, output_path: str) -> str:
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': output_path,
        'merge_output_format': 'mp4',
        'quiet': True,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not filename.lower().endswith('.mp4'):
            filename = os.path.splitext(filename)[0] + '.mp4'
        return filename

# Upscale video by sending frames to Hugging Face API

def upscale_video(input_path: str, output_path: str, framerate: int = 30) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Extract frames
        frame_pattern = os.path.join(tmpdir, 'frame_%06d.png')
        subprocess.run([
            'ffmpeg', '-i', input_path,
            frame_pattern
        ], check=True)

        # List extracted frames
        frames = sorted([f for f in os.listdir(tmpdir)
                         if f.startswith('frame_') and f.endswith('.png')])

        # Upscale each frame
        for frame in frames:
            frame_path = os.path.join(tmpdir, frame)
            with open(frame_path, 'rb') as img_file:
                response = requests.post(HF_API_URL, headers=HEADERS, data=img_file)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Frame upscale failed: {response.status_code} {response.text}")
            with open(frame_path, 'wb') as out_file:
                out_file.write(response.content)

        # Reassemble video
        subprocess.run([
            'ffmpeg', '-framerate', str(framerate),
            '-i', os.path.join(tmpdir, 'frame_%06d.png'),
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', output_path
        ], check=True)
    return output_path

# Add watermark using FFmpeg

def add_watermark(input_path: str, output_path: str, text: str) -> str:
    cmd = [
        'ffmpeg', '-i', input_path,
        '-vf', f"drawtext=text='{text}':fontcolor=white:fontsize=24:x=w-tw-10:y=h-th-10",
        '-codec:a', 'copy', output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

# Telegram bot handlers

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Send me an Instagram Reel URL. I will download it, upscale (4× via HF API), watermark, and return it.'
    )


def handle_message(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    if 'instagram.com' not in url:
        update.message.reply_text('Please send a valid Instagram Reel URL.')
        return

    status_msg = update.message.reply_text('Downloading reel...')
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Download
            orig_path = os.path.join(tmpdir, 'original.mp4')
            download_reel(url, orig_path)

            # Upscale
            status_msg.edit_text('Upscaling frames via HF API...')
            upscaled_path = os.path.join(tmpdir, 'upscaled.mp4')
            upscale_video(orig_path, upscaled_path)

            # Watermark
            status_msg.edit_text('Adding watermark...')
            final_path = os.path.join(tmpdir, 'final.mp4')
            add_watermark(upscaled_path, final_path, 'desi gadgets')

            # Send back
            status_msg.edit_text('Uploading enhanced reel...')
            with open(final_path, 'rb') as video_file:
                update.message.reply_video(video_file)
        except Exception as exc:
            logger.error(f"Processing error: {exc}")
            update.message.reply_text('Sorry, something went wrong during processing.')


def main():
    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
