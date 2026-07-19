-- schema.sql — opis svih tabela u bazi.
-- Bezbedno ga je pokrenuti više puta: "IF NOT EXISTS" znači
-- "napravi samo ako već ne postoji".

-- Radnje u lancu. V1 koristi samo jednu, ali je sve spremno za više radnji.
CREATE TABLE IF NOT EXISTS radnje (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    naziv  TEXT NOT NULL
);

-- Šifarnik proizvoda: jedan red = jedan artikal (ne pojedinačni komad).
CREATE TABLE IF NOT EXISTS proizvodi (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    barkod  TEXT UNIQUE,             -- sa ambalaže; UNIQUE = ne mogu dva ista
    naziv   TEXT NOT NULL,
    cena    REAL                     -- opciono (prazno = cena nije upisana)
);

-- Stavke prijema: jedan red = jedan prijem jednog proizvoda sa jednim rokom.
-- Isti proizvod sme da ima više redova (različiti prijemi, različiti rokovi).
CREATE TABLE IF NOT EXISTS stavke (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id       INTEGER NOT NULL REFERENCES radnje(id),
    proizvod_id    INTEGER NOT NULL REFERENCES proizvodi(id),
    rok            TEXT NOT NULL,    -- datum isteka, oblik GGGG-MM-DD
    kolicina       INTEGER NOT NULL DEFAULT 1,
    status         TEXT NOT NULL DEFAULT 'aktivno',  -- aktivno / otpisano / snizeno
    datum_prijema  TEXT NOT NULL DEFAULT (date('now')),
    datum_promene  TEXT              -- kad je stavka označena kao otpisana/snižena
);

-- Ubrzava traženje po roku (za ekran "ističe uskoro").
CREATE INDEX IF NOT EXISTS idx_stavke_rok ON stavke(rok);

-- Prodaja iz kase: jedan red = zbir prodaje jednog artikla za jedan dan.
CREATE TABLE IF NOT EXISTS prodaja (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id     INTEGER NOT NULL REFERENCES radnje(id),
    proizvod_id  INTEGER NOT NULL REFERENCES proizvodi(id),
    datum        TEXT NOT NULL,      -- dan prodaje, GGGG-MM-DD
    kolicina     REAL NOT NULL       -- REAL zbog merenih artikala (npr. 0.350 kg)
);

-- Isti artikal + isti dan sme samo jednom: ponovni uvoz istog dana
-- zamenjuje brojke umesto da ih duplira.
CREATE UNIQUE INDEX IF NOT EXISTS idx_prodaja_dan
    ON prodaja(store_id, proizvod_id, datum);
