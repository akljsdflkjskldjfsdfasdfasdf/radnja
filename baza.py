# baza.py — sve oko baze podataka na jednom mestu.

import sqlite3
from pathlib import Path

# Baza je jedan običan fajl pored koda.
PUTANJA_BAZE = Path(__file__).parent / "radnja.db"
PUTANJA_SEME = Path(__file__).parent / "schema.sql"


def konekcija():
    """Otvori vezu ka bazi. Redovi se ponašaju kao rečnici: red["naziv"]."""
    veza = sqlite3.connect(PUTANJA_BAZE)
    veza.row_factory = sqlite3.Row
    veza.execute("PRAGMA foreign_keys = ON")  # čuva veze između tabela
    return veza


def pripremi_bazu():
    """Napravi tabele ako ne postoje i upiši radnju ako je baza prazna."""
    veza = konekcija()
    veza.executescript(PUTANJA_SEME.read_text(encoding="utf-8"))
    prva_radnja = veza.execute("SELECT id FROM radnje LIMIT 1").fetchone()
    if prva_radnja is None:
        veza.execute("INSERT INTO radnje (naziv) VALUES (?)", ("Test radnja",))
    veza.commit()
    veza.close()
