from __future__ import annotations
import csv, io
from .models import RegistroRestricao

def gerar_csv_siafi(nivel: str, codigo_responsavel: str, mes: str | int, registros: list[RegistroRestricao]) -> str:
    saida = io.StringIO()
    writer = csv.writer(saida, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    mes_str = str(int(str(mes))) if str(mes).strip().isdigit() else str(mes).strip()
    writer.writerow(["H", nivel, codigo_responsavel, mes_str, " ", " ", "|"])
    for r in registros:
        writer.writerow(["D", r.ug, r.restricao, r.motivo, r.providencia, r.valor, "|"])
    writer.writerow(["T", len(registros), "", "", "", "", "|"])
    return saida.getvalue()

def nome_csv_padrao(mes: str | int, ano: str, codigo_responsavel: str="153062") -> str:
    mes2 = str(mes).zfill(2) if str(mes).isdigit() else "MM"
    ano = ano or "AAAA"
    return f"restricoes_siafi_{codigo_responsavel}_{ano}_{mes2}.csv"
