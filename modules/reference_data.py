from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig").fillna("")

def carregar_conrestcon() -> pd.DataFrame:
    df = _read_csv(DATA_DIR / "conrestcon.csv")
    df["codigo_restricao"] = df["codigo_restricao"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(3)
    return df.drop_duplicates("codigo_restricao")

def carregar_ugs_validas() -> pd.DataFrame:
    df = _read_csv(DATA_DIR / "ugs_validas.csv")
    df["codigo_ug"] = df["codigo_ug"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(6)
    return df.drop_duplicates("codigo_ug")

def mapa_conrestcon() -> dict[str, str]:
    return dict(zip(carregar_conrestcon()["codigo_restricao"], carregar_conrestcon()["descricao"]))

def mapa_ugs() -> dict[str, str]:
    return dict(zip(carregar_ugs_validas()["codigo_ug"], carregar_ugs_validas()["nome_ug"]))
