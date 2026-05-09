from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot está vivo!"

def run():
  app.run(host='0.0.0.0', port=8099)

def keep_alive():
    t = Thread(target=run)
    t.start()
