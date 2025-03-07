import subprocess
import time
import threading
import logging
import signal
import os
from flask import Flask, Response

app = Flask(__name__)

# 📝 Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 📡 List of YouTube Live Streams
YOUTUBE_STREAMS = {
    "media_one": "https://www.youtube.com/@MediaoneTVLive/live",
    "shajahan_rahmani": "https://www.youtube.com/@ShajahanRahmaniOfficial/live",
    "qsc_mukkam": "https://www.youtube.com/c/quranstudycentremukkam/live",
    "valiyudheen_faizy": "https://www.youtube.com/@voiceofvaliyudheenfaizy600/live",
    "skicr_tv": "https://www.youtube.com/@SKICRTV/live",
    "yaqeen_institute": "https://www.youtube.com/@yaqeeninstituteofficial/live",
    "bayyinah_tv": "https://www.youtube.com/@bayyinah/live",
}

# 🌍 Store the latest audio stream URLs
stream_cache = {}
cache_lock = threading.Lock()

# 📂 Cookie file path (set via environment variable or default location)
COOKIE_FILE = os.getenv("YT_COOKIES", "/mnt/data/cookies.txt")

def get_audio_url(youtube_url):
    """Fetch the latest direct audio URL from YouTube."""
    try:
        # 📝 Get available formats
        formats_command = [
            "yt-dlp",
            "--cookies", COOKIE_FILE,
            "--force-generic-extractor",
            "-F", youtube_url
        ]
        result = subprocess.run(formats_command, capture_output=True, text=True, check=True)
        
        # 🎵 Find the best audio format
        available_formats = result.stdout
        if "91" in available_formats:
            format_code = "91"  # Preferred format
        else:
            format_code = "bestaudio"

        # 🔗 Extract the actual audio URL
        command = [
            "yt-dlp",
            "--cookies", COOKIE_FILE,
            "--force-generic-extractor",
            "-f", format_code,
            "-g", youtube_url
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        audio_url = result.stdout.strip() if result.stdout else None

        if audio_url:
            logging.info(f"✅ Fetched audio URL for {youtube_url}")
        else:
            logging.warning(f"⚠️ No audio URL found for {youtube_url}")

        return audio_url
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ Error fetching audio URL: {e}")
        return None

def refresh_stream_url():
    """Refresh YouTube stream URLs every 2 minutes to avoid expiration."""
    while True:
        with cache_lock:
            for station, url in YOUTUBE_STREAMS.items():
                new_url = get_audio_url(url)
                if new_url:
                    stream_cache[station] = new_url
                    logging.info(f"🔄 Updated stream URL for {station}")
        time.sleep(120)  # Refresh every 2 minutes

def generate_stream(station_name):
    """Streams audio using FFmpeg, automatically updating the URL when it expires."""
    while True:
        with cache_lock:
            stream_url = stream_cache.get(station_name, None)

        if not stream_url:
            logging.warning(f"⚠️ No valid stream URL for {station_name}, trying to fetch a new one...")
            with cache_lock:
                stream_url = get_audio_url(YOUTUBE_STREAMS[station_name])
                if stream_url:
                    stream_cache[station_name] = stream_url

        if not stream_url:
            logging.error(f"❌ Failed to fetch stream URL for {station_name}")
            return

        process = subprocess.Popen(
            ["ffmpeg", "-re", "-i", stream_url,
             "-vn", "-acodec", "libmp3lame", "-b:a", "64k",
             "-probesize", "32k", "-f", "mp3", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=8192
        )

        logging.info(f"🎵 Streaming {station_name} from: {stream_url}")

        try:
            for chunk in iter(lambda: process.stdout.read(8192), b""):
                yield chunk
        except GeneratorExit:
            logging.info(f"🛑 Stopping stream for {station_name}")
            process.kill()
            break
        except Exception as e:
            logging.error(f"⚠️ Stream error for {station_name}: {e}")

        logging.info(f"🔄 FFmpeg stopped for {station_name}, retrying in 5 seconds...")
        time.sleep(5)

@app.route("/play/<station_name>")
def stream(station_name):
    if station_name not in YOUTUBE_STREAMS:
        return "⚠️ Station not found", 404

    return Response(generate_stream(station_name), mimetype="audio/mpeg")

# 🚀 Start the URL refresher thread
threading.Thread(target=refresh_stream_url, daemon=True).start()

def graceful_shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    logging.info("🛑 Shutting down Flask app...")
    exit(0)

signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)