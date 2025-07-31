from flask import Flask
import threading
import os
import jwbot  # importa tu bot

app = Flask(__name__)

def run_bot():
    jwbot.main()  # arranca el bot en segundo plano

# Inicia el bot al cargar la app
threading.Thread(target=run_bot, daemon=True).start()

@app.route("/")
def index():
    return "JW bot en ejecución."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
