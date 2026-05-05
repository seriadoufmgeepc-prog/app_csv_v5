from __future__ import annotations
import re
import unicodedata
from typing import Optional

MESES = {
    "jan": "01", "janeiro": "01", "fev": "02", "fevereiro": "02", "mar": "03", "marco": "03", "março": "03",
    "abr": "04", "abril": "04", "mai": "05", "maio": "05", "jun": "06", "junho": "06", "jul": "07", "julho": "07",
    "ago": "08", "agosto": "08", "set": "09", "setembro": "09", "out": "10", "outubro": "10", "nov": "11", "novembro": "11",
    "dez": "12", "dezembro": "12",
}

def sem_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")

def limpar_espacos(texto: object) -> str:
    if texto is None:
        return ""
    if str(texto).lower() in {"nan", "none", "nat"}:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()

def somente_digitos(valor: object, tamanho: Optional[int] = None) -> str:
    digitos = re.sub(r"\D", "", limpar_espacos(valor))
    return digitos.zfill(tamanho) if tamanho and digitos else digitos

def codigo_ug(valor: object) -> str:
    return somente_digitos(valor, 6)

def codigo_restricao(valor: object) -> str:
    return somente_digitos(valor, 3)

def normalizar_competencia(valor: object) -> str:
    bruto = limpar_espacos(valor)
    if not bruto:
        return ""
    m = re.search(r"(\d{1,2})\s*/\s*(\d{4})", bruto)
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    m = re.search(r"([A-Za-zçÇãÃéÉ]+)\s*/\s*(\d{4})", bruto)
    if m:
        mes = MESES.get(sem_acentos(m.group(1)).lower()[:3], "") or MESES.get(sem_acentos(m.group(1)).lower(), "")
        return f"{mes}/{m.group(2)}" if mes else bruto
    return bruto

def moeda_para_digitos(valor: object) -> str:
    texto = limpar_espacos(valor)
    if not texto:
        return ""
    texto = texto.replace("R$", "").replace(".", "").replace(",", "")
    return somente_digitos(texto)

def texto_siafi(valor: object, limite: int = 1024) -> str:
    texto = limpar_espacos(valor)
    texto = texto.replace("¿", "'")
    texto = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", " ", texto)
    texto = limpar_espacos(texto)
    return texto[:limite]

def normalizar_coluna(nome: object) -> str:
    s = sem_acentos(limpar_espacos(nome)).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s
