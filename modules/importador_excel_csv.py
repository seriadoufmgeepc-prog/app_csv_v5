from __future__ import annotations
from io import BytesIO, StringIO
import csv
from typing import Iterable
import pandas as pd
from .models import RegistroRestricao
from .normalizacao import normalizar_coluna, codigo_ug, codigo_restricao, texto_siafi, moeda_para_digitos, normalizar_competencia

ALIAS = {
    "ug": {"ug", "codigo_ug", "cod_ug", "unidade_gestora", "unidade_gestora_codigo", "codigo_da_ug", "cod_unidade_gestora"},
    "restricao": {"restricao", "codigo_restricao", "cod_restricao", "codigo_da_restricao", "restricao_contabil", "codigo_restricao_contabil", "cod_restricao_contabil"},
    "motivo": {"motivo", "descricao", "descricao_restricao", "justificativa", "observacao", "obs", "historico", "texto_motivo"},
    "providencia": {"providencia", "providencias", "acao", "correcao", "encaminhamento", "texto_providencia"},
    "valor": {"valor", "saldo", "montante", "valor_restricao"},
    "competencia": {"competencia", "mes", "mes_referencia", "referencia", "mes_ano", "periodo"},
    "grupo": {"grupo", "grupo_restricao", "grupo_conformidade"},
    "conta_contabil": {"conta_contabil", "conta", "pcasp", "conta_pcasp"},
    "equacao": {"equacao", "equacao_siafi", "codigo_equacao", "cod_equacao"},
    "situacao": {"situacao", "indicador", "status"},
}

CSV_SEPARADORES = [";", ",", "\t", "|"]


def _tem_colunas_obrigatorias(df: pd.DataFrame) -> bool:
    normalizadas = {normalizar_coluna(c) for c in df.columns}
    tem_ug = bool(normalizadas & ALIAS["ug"])
    tem_restricao = bool(normalizadas & ALIAS["restricao"])
    return tem_ug and tem_restricao


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
        colunas_encontradas = ", ".join(str(c) for c in df.columns[:8])
        detalhe = f" Colunas encontradas: {colunas_encontradas}." if colunas_encontradas else ""
        raise ValueError("Colunas obrigatórias ausentes: " + ", ".join(faltantes) + ". Esperado, no mínimo: UG e Restrição." + detalhe)
    return mapa


def _decodificar_csv(dados: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin1", "cp1252"):
        try:
            return dados.decode(enc)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin1", errors="replace")


def _sniff_delimitador(texto: str) -> str | None:
    amostra = texto[:8192]
    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
        return dialect.delimiter
    except csv.Error:
        return None


def _ler_csv_com_separador(texto: str, sep: str, header: int | None = 0) -> pd.DataFrame:
    return pd.read_csv(StringIO(texto), sep=sep, dtype=str, header=header, engine="python").fillna("")


def _parece_csv_siafi(df_sem_cabecalho: pd.DataFrame) -> bool:
    if df_sem_cabecalho.empty or df_sem_cabecalho.shape[1] < 4:
        return False
    primeira_coluna = df_sem_cabecalho.iloc[:, 0].astype(str).str.strip().str.upper()
    return primeira_coluna.isin(["H", "D", "T"]).sum() >= 1 and (primeira_coluna == "D").any()


def _converter_csv_siafi_para_tabela(df_sem_cabecalho: pd.DataFrame) -> pd.DataFrame:
    """Converte arquivo CSV final do SIAFI/app, sem cabeçalho, para colunas internas padrão.

    Layout esperado das linhas de dados: D;UG;Restrição;Motivo;Providência;Valor;|
    A linha H, quando existente, é usada apenas para capturar a competência/mês.
    """
    linhas = df_sem_cabecalho.copy().fillna("")
    linhas.columns = list(range(linhas.shape[1]))
    competencia = ""
    cabecalho = linhas[linhas[0].astype(str).str.strip().str.upper() == "H"]
    if not cabecalho.empty and linhas.shape[1] > 3:
        competencia = texto_siafi(cabecalho.iloc[0, 3], 20)

    dados = linhas[linhas[0].astype(str).str.strip().str.upper() == "D"]
    registros = []
    for _, row in dados.iterrows():
        registros.append({
            "ug": row.get(1, ""),
            "restricao": row.get(2, ""),
            "motivo": row.get(3, ""),
            "providencia": row.get(4, ""),
            "valor": row.get(5, "") if linhas.shape[1] > 5 else "",
            "competencia": competencia,
        })
    return pd.DataFrame(registros, columns=["ug", "restricao", "motivo", "providencia", "valor", "competencia"]).fillna("")


def _ler_csv_robusto(dados: bytes) -> pd.DataFrame:
    texto = _decodificar_csv(dados)
    candidatos = []
    sniff = _sniff_delimitador(texto)
    if sniff:
        candidatos.append(sniff)
    candidatos.extend([sep for sep in CSV_SEPARADORES if sep not in candidatos])

    melhor_df = None
    melhor_score = -1
    melhor_sem_cabecalho = None

    for sep in candidatos:
        try:
            df_header = _ler_csv_com_separador(texto, sep=sep, header=0)
            df_no_header = _ler_csv_com_separador(texto, sep=sep, header=None)
        except Exception:
            continue

        # Prioridade 1: CSV final gerado para SIAFI, sem cabeçalho, com linhas H/D/T.
        if _parece_csv_siafi(df_no_header):
            return _converter_csv_siafi_para_tabela(df_no_header)

        # Prioridade 2: CSV tabular com cabeçalhos reconhecíveis.
        largura = int(df_header.shape[1])
        obrig = 100 if _tem_colunas_obrigatorias(df_header) else 0
        vazios = int(df_header.empty)
        score = obrig + largura - (10 * vazios)
        if score > melhor_score:
            melhor_score = score
            melhor_df = df_header
            melhor_sem_cabecalho = df_no_header

    if melhor_df is None:
        raise ValueError("Não foi possível ler o arquivo CSV. Verifique a codificação, o separador e o conteúdo do arquivo.")

    # Se o melhor candidato ainda não tiver UG/Restrição, tenta detectar CSV SIAFI no candidato sem cabeçalho.
    if not _tem_colunas_obrigatorias(melhor_df) and melhor_sem_cabecalho is not None and _parece_csv_siafi(melhor_sem_cabecalho):
        return _converter_csv_siafi_para_tabela(melhor_sem_cabecalho)

    return melhor_df.fillna("")


def ler_tabela(uploaded_file) -> pd.DataFrame:
    nome = uploaded_file.name.lower()
    if nome.endswith(".csv"):
        dados = uploaded_file.getvalue()
        return _ler_csv_robusto(dados)
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
