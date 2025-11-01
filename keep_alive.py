# ─────────────────────────────────────────────
#  Hoshikuzu Keep Alive System 🌸
#  Maintains bot uptime on Render / Replit
# ─────────────────────────────────────────────

from flask import Flask
from threading import Thread

app = Flask('Hoshikuzu')

@app.route('/')
def home():
    return "🌸 Hoshikuzu bot is alive and running perfectly 💜"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    """
    Lance un petit serveur HTTP Flask pour empêcher Render
    de couper le bot (ping régulier).
    """
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print("🌐 Keep-alive server started on port 8080")
