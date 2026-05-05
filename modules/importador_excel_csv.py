from __future__ import annotations
from io import BytesIO
from typing import Iterable
import pandas as pd
from .models import RegistroRestricao
from .normalizacao import normalizar_coluna, codigo_ug, codigo_restricao, texto_siafi, moeda_para_digitos, normalizar_competencia

ALIAS = {
    "ug": {"ug", "codigo_ug", "cod_ug", "unidade_gestora", "unidade_gestora_codigo", "codigo_da_ug"},
    "restricao": {"restricao", "codigo_restricao", "cod_restricao", "codigo_da_restricao", "restricao_contabil"},
    "motivo": {"motivo", "descricao", "descricao_restricao", "justificativa", "observacao", "obs"},
    "providencia": {"providencia", "providencias", "acao", "correcao", "encaminhamento"},
    "valor": {"valor", "saldo", "montante"},
    "competencia": {"competencia", "mes", "mes_referencia", "referencia"},
    "grupo": {"grupo", "grupo_restricao"},
    "conta_contabil": {"conta_contabil", "conta", "pcasp"},
    "equacao": {"equacao", "equacao_siafi", "codigo_equacao"},
    "situacao": {"situacao", "indicador", "status"},
}

def _detectar_colunas(df: pd.DataFrame) -> dict[str, str]:
    normalizadas = {normalizar_coluna(c): c for c in df.columns}
    mapa = {}
    for campo, nomes in ALIAS.items():
        for nome in nomes:
            if nome in normalizadas:
                mapa[campo] = normalizadas[nome]
                break
    faltantes = [c for c in ["ug", "restricao"] if c not in mapa]
    if faltantes:
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(faltantes) + ". Esperado, no mínimo: UG e Restrição.")
    return mapa

def ler_tabela(uploaded_file) -> pd.DataFrame:
    nome = uploaded_file.name.lower()
    if nome.endswith(".csv"):
        dados = uploaded_file.getvalue()
        try:
            sample = dados[:4096].decode("utf-8-sig")
        except UnicodeDecodeError:
            sample = dados[:4096].decode("latin1")
        sep = ";" if sample.count(";") >= sample.count(",") else ","
        return pd.read_csv(BytesIO(dados), sep=sep, dtype=str, encoding="utf-8-sig").fillna("")
    return pd.read_excel(uploaded_file, dtype=str).fillna("")

def dataframe_para_registros(df: pd.DataFrame, origem: str, arquivo: str) -> list[RegistroRestricao]:
    df = df.dropna(how="all").copy()
    mapa = _detectar_colunas(df)
    registros = []
    for pos, row in df.iterrows():
        reg = RegistroRestricao(
            ug=codigo_ug(row.get(mapa.get("ug", ""), "")),
            restricao=codigo_restricao(row.get(mapa.get("restricao", ""), "")),
            motivo=texto_siafi(row.get(mapa.get("motivo", ""), "")),
            providencia=texto_siafi(row.get(mapa.get("providencia", ""), "")),
            valor=moeda_para_digitos(row.get(mapa.get("valor", ""), "")),
            competencia=normalizar_competencia(row.get(mapa.get("competencia", ""), "")),
            grupo=texto_siafi(row.get(mapa.get("grupo", ""), ""), 120),
            conta_contabil=texto_siafi(row.get(mapa.get("conta_contabil", ""), ""), 40),
            equacao=texto_siafi(row.get(mapa.get("equacao", ""), ""), 40),
            situacao=texto_siafi(row.get(mapa.get("situacao", ""), ""), 80),
            origem=origem,
            arquivo_origem=arquivo,
            linha_origem=str(pos + 2),
        )
        if any([reg.ug, reg.restricao, reg.motivo, reg.providencia, reg.valor]):
            registros.append(reg)
    return registros
