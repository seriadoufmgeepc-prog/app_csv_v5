from __future__ import annotations
from io import BytesIO
import pandas as pd
from .models import RegistroRestricao

def gerar_xlsx_abas(abas: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for nome, df in abas.items():
            safe = nome[:31]
            df.to_excel(writer, index=False, sheet_name=safe)
            workbook = writer.book
            worksheet = writer.sheets[safe]
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
            for col, value in enumerate(df.columns):
                worksheet.write(0, col, value, header_fmt)
                width = min(max(12, int(df[value].astype(str).str.len().max() if not df.empty else len(str(value))) + 2), 60)
                worksheet.set_column(col, col, width)
            worksheet.autofilter(0, 0, max(len(df), 1), max(len(df.columns)-1, 0))
            worksheet.freeze_panes(1, 0)
    return output.getvalue()

def modelo_importacao() -> bytes:
    df = pd.DataFrame([
        {"UG":"153254", "Restrição":"634", "Competência":"03/2026", "Motivo":"Bens adquiridos antes de 2010 permanecem com valores históricos, necessitando de reavaliação.", "Providência":"Aguardando providências da Administração Central.", "Valor":""},
        {"UG":"153277", "Restrição":"302", "Competência":"03/2026", "Motivo":"Falta ou atraso de remessa do RMA ou RMB.", "Providência":"Os lançamentos serão efetuados após o recebimento do relatório.", "Valor":""},
    ])
    return gerar_xlsx_abas({"Modelo": df})

def resumo_por_ug(df: pd.DataFrame, ugs: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["ug", "nome_ug", "quantidade", "restricoes"])
    base = df.groupby("ug").agg(quantidade=("restricao","count"), restricoes=("restricao", lambda x: ", ".join(sorted(set(map(str,x)))))).reset_index()
    return base.merge(ugs[["codigo_ug", "nome_ug"]], left_on="ug", right_on="codigo_ug", how="left").drop(columns=["codigo_ug"]).loc[:, ["ug", "nome_ug", "quantidade", "restricoes"]]

def ugs_sem_restricao(df: pd.DataFrame, ugs: pd.DataFrame) -> pd.DataFrame:
    """Retorna UGs válidas que não possuem restrição associada no conjunto analisado."""
    if ugs.empty:
        return pd.DataFrame(columns=["codigo_ug", "nome_ug"])
    base = ugs.copy()
    base["codigo_ug"] = base["codigo_ug"].astype(str).str.zfill(6)
    com_restricao = set()
    if df is not None and not df.empty and "ug" in df.columns:
        com_restricao = set(df["ug"].astype(str).str.zfill(6))
    sem = base.loc[~base["codigo_ug"].isin(com_restricao)].copy()
    colunas = [c for c in ["codigo_ug", "nome_ug", "sigla"] if c in sem.columns]
    return sem[colunas].sort_values("codigo_ug").reset_index(drop=True)
