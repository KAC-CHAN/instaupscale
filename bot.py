
import os
import tempfile
import subprocess
import logging
import requests
import replicate
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "7259559804:AAFIqjtqJgC68m9ucmOt9vfbGlM4iiGxwY4"
REPLICATE_API_TOKEN  = "r8_4KvDvivCWUDGU4BY3OykD60uFew2jAG3kso9T"
YDL_OPTS = {
    "format": "bestvideo+bestaudio/best",
    "outtmpl": "%(id)s.%(ext)s",
    "merge_output_format": "mp4",
}

# Initialize Replicate client
rep_client = replicate.Client(api_token=REPLICATE_API_TOKEN)
# Model on Replicate: Real-ESRGAN for video
MODEL = "twhui/Real-ESRGAN-video:latest"

async def download_reel(url, target):
    with YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        fn = ydl.prepare_filename(info)
        ydl.download([url])
    os.replace(fn, target)

async def upscale_with_replicate(input_path, output_path):
    # Replicate accepts file uploads via multipart/form-data
    with open(input_path, "rb") as video_file:
        logger.info("Uploading video to Replicate…")
        prediction = rep_client.run(
            MODEL,
            input={ "video": video_file },
            stream=True,          # stream logs
        )
        # prediction is a generator of JSON chunks (with logs and finally 'output' key)
        output_url = None
        for chunk in prediction:
            if "output" in chunk:
                output_url = chunk["output"]
        if not output_url:
            raise RuntimeError("Replicate did not return an output URL")
        # download the upscaled result
        r = requests.get(output_url, stream=True)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for buf in r.iter_content(8_192):
                f.write(buf)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if "instagram.com" not in url:
        return await update.message.reply_text("Please send a valid Instagram Reel link.")
    await update.message.reply_text("Downloading reel…")
    with tempfile.TemporaryDirectory() as tmp:
        in_vid  = os.path.join(tmp, "in.mp4")
        out_vid = os.path.join(tmp, "out.mp4")
        try:
            await download_reel(url, in_vid)
            await update.message.reply_text("Upscaling (via Replicate)…")
            await upscale_with_replicate(in_vid, out_vid)
            with open(out_vid, "rb") as v:
                await update.message.reply_video(v, caption="Here’s your upscaled reel! 💥")
        except Exception as e:
            logger.error("Error: %s", e)
            await update.message.reply_text(f"Something went wrong: {e}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not REPLICATE_API_TOKEN:
        logger.error("Set TELEGRAM_TOKEN and REPLICATE_API_TOKEN env vars.")
        exit(1)
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
