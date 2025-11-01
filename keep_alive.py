# ─────────────────────────────────────────────
#  Hoshikuzu Keep Alive System 🌸 (Render Edition)
#  Maintains bot uptime gracefully without thread crash
# ─────────────────────────────────────────────

from flask import Flask
from threading import Thread
import logging

# Désactivation des logs Flask inutiles dans Render
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('Hoshikuzu')

@app.route('/')
def home():
    return "🌸 Hoshikuzu bot is alive and stable 💜"

def run():
    try:
        app.run(host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"[KeepAlive] Erreur Flask : {e}")

def keep_alive():
    """
    Lance un petit serveur HTTP Flask pour empêcher Render
    de couper le bot. Version stable sans crash à l'arrêt.
    """
    t = Thread(target=run)
    t.daemon = False  # Permet une fermeture propre à l'arrêt du conteneur
    t.start()
    print("🌐 Keep-alive server started on port 8080 (Render mode)")
