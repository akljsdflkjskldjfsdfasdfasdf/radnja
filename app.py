# app.py — glavna datoteka aplikacije.
# Za sada samo jedna stranica, da proverimo da sve radi (laptop, telefon, hosting).

from flask import Flask

app = Flask(__name__)


@app.route("/")
def pocetna():
    return """
    <!doctype html>
    <html lang="sr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Radnja</title>
    </head>
    <body style="font-family: sans-serif; text-align: center; margin-top: 3rem;">
        <h1>Radi! 🎉</h1>
        <p>Platforma za radnju — Faza 1: rokovi trajanja.</p>
    </body>
    </html>
    """


# Ovaj deo se izvršava samo kad na laptopu pokrenemo "python app.py".
# Na hostingu (Render) aplikaciju pokreće drugi program (gunicorn), pa se ovo preskače.
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
