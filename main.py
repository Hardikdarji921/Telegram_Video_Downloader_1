import os
import threading
import signal
import sys
import asyncio

# Import Flask app
from api import app as flask_app

# Import bot functions
import bot

def run_flask():
    """Run Flask API server in its own thread"""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    
    print(f"Starting Flask API → http://{host}:{port}")
    flask_app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=False,       # Important when running in thread
        threaded=True
    )

def shutdown_handler(signum, frame):
    """Graceful shutdown handler"""
    print("\nShutting down gracefully...")
    try:
        # Try to stop bot
        if hasattr(bot, 'application') and bot.application:
            asyncio.run_coroutine_threadsafe(
                bot.application.stop_running(),
                asyncio.get_event_loop()
            )
    except Exception as e:
        print(f"Error stopping bot: {e}")
    
    print("Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start Flask in background thread
    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True,
        name="Flask-Server"
    )
    flask_thread.start()

    print("Terabox Gateway + Telegram Bot")
    print("--------------------------------")
    print("• API     → http://localhost:5000")
    print("• Health  → http://localhost:5000/health")
    print("• Help    → http://localhost:5000/help")
    print("Bot is polling Telegram...\n")

    # Run bot in main thread (it uses asyncio internally)
    bot.main()
