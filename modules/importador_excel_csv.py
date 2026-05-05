from __future__ import annotations
from io import StringIO
import csv
import re
import pandas as pd
from .models import RegistroRestricao
from .normalizacao import (
    normalizar_coluna,
    codigo_ug,
    codigo_restricao,
    texto_siafi,
    moeda_para_digitos,
    normalizar_competencia,
    limpar_espacos,
)

# Nomes de colunas aceitos após normalização sem acentos, em minúsculas e com _.
# A lista foi ampliada para contemplar CSVs exportados pelo Excel, modelos internos,
# arquivos com cabeçalho alternativo e arquivos já gerados para conferência/upload.
ALIAS = {
    "ug": {
        "ug", "codigo_ug", "cod_ug", "cod_ug_emitente", "unidade_gestora", "unidade_gestora_codigo",
        "codigo_da_ug", "cod_unidade_gestora", "codigo_unidade_gestora", "unid_gestora",
        "unidade", "gestora", "ug_executora", "ug_informada", "cod_ug_executora",
        "orgao_ug", "unidade_gestora_ug", "codigo", "cod",
    },
    "restricao": {
        "restricao", "codigo_restricao", "cod_restricao", "codigo_da_restricao", "restricao_contabil",
        "codigo_restricao_contabil", "cod_restricao_contabil", "cod_restr", "codigo_restr", "restricoes",
        "restricao_siafi", "cod_restricao_siafi", "codigo_restricao_siafi", "codigo_da_restricao_contabil",
        "cod_restricao_contabil_siafi", "restr", "cod_restricao_contabil", "codigo_conrestcon",
    },
    "motivo": {
        "motivo", "descricao", "descricao_restricao", "descricao_da_restricao", "justificativa", "observacao",
        "obs", "historico", "texto_motivo", "motivo_restricao", "motivo_da_restricao", "mensagem",
    },
    "providencia": {
        "providencia", "providencias", "providencia_adotada", "providencia_prevista", "acao", "correcao",
        "encaminhamento", "texto_providencia", "medida", "medidas", "providencia_saneamento",
    },
    "valor": {"valor", "saldo", "montante", "valor_restricao", "valor_da_restricao", "valor_r", "vlr"},
    "competencia": {"competencia", "mes", "mes_referencia", "referencia", "mes_ano", "periodo", "compet", "ref"},
    "grupo": {"grupo", "grupo_restricao", "grupo_conformidade", "grupo_da_restricao", "grupo_siafi"},
    "conta_contabil": {"conta_contabil", "conta", "pcasp", "conta_pcasp", "conta_contabil_pcasp", "conta_siafi"},
    "equacao": {"equacao", "equacao_siafi", "codigo_equacao", "cod_equacao", "eq", "equacao_referencia"},
    "situacao": {"situacao", "indicador", "status", "situacao_restricao"},
}

CSV_SEPARADORES = [";", ",", "\t", "|"]


def _tem_colunas_obrigatorias(df: pd.DataFrame) -> bool:
    normalizadas = {normalizar_coluna(c) for c in df.columns}
    return bool(normalizadas & ALIAS["ug"]) and bool(normalizadas & ALIAS["restricao"])


def _detectar_colunas(df: pd.DataFrame) -> dict[str, str]:
    normalizadas = {normalizar_coluna(c): c for c in df.columns}
    mapa: dict[str, str] = {}
    for campo, nomes in ALIAS.items():
        for nome in nomes:
            if nome in normalizadas:
                mapa[campo] = normalizadas[nome]
                break

    # Heurística controlada: quando o arquivo veio sem cabeçalho, mas as primeiras
    # colunas têm padrão UG/Restrição, as colunas são mapeadas automaticamente.
    if "ug" not in mapa or "restricao" not in mapa:
        mapa_posicional = _mapear_colunas_por_conteudo(df)
        mapa.update({k: v for k, v in mapa_posicional.items() if k not in mapa})

    faltantes = [c for c in ["ug", "restricao"] if c not in mapa]
    if faltantes:
        colunas_encontradas = ", ".join(str(c) for c in list(df.columns)[:12])
        detalhe = f" Colunas encontradas: {colunas_encontradas}." if colunas_encontradas else ""
        raise ValueError(
            "Colunas obrigatórias ausentes: "
            + ", ".join(faltantes)
            + ". Esperado, no mínimo: UG e Restrição."
            + detalhe
            + " Verifique se a linha de cabeçalho contém colunas equivalentes a UG/Código UG e Restrição/Código Restrição."
        )
    return mapa


def _decodificar_csv(dados: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin1", "cp1252"):
        try:
            return dados.decode(enc)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin1", errors="replace")


def _remover_linha_sep_excel(texto: str) -> str:
    """Remove diretiva 'sep=;' gravada pelo Excel, mantendo o restante do arquivo."""
    linhas = texto.splitlines()
    if linhas and re.match(r"^\s*sep\s*=\s*[;,\t|]\s*$", linhas[0], flags=re.I):
        return "\n".join(linhas[1:])
    return texto


def _sniff_delimitador(texto: str) -> str | None:
    amostra = texto[:20000]
    try:
        dialect = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
        return dialect.delimiter
    except csv.Error:
        return None


def _ler_csv_com_separador(texto: str, sep: str, header: int | None = 0) -> pd.DataFrame:
    return pd.read_csv(
        StringIO(texto),
        sep=sep,
        dtype=str,
        header=header,
        engine="python",
        on_bad_lines="skip",
        keep_default_na=False,
    ).fillna("")


def _parece_csv_siafi(df_sem_cabecalho: pd.DataFrame) -> bool:
    if df_sem_cabecalho.empty or df_sem_cabecalho.shape[1] < 3:
        return False
    primeira_coluna = df_sem_cabecalho.iloc[:, 0].astype(str).str.strip().str.upper()
    return primeira_coluna.isin(["H", "D", "T"]).sum() >= 1 and (primeira_coluna == "D").any()


def _converter_csv_siafi_para_tabela(df_sem_cabecalho: pd.DataFrame) -> pd.DataFrame:
    """Converte arquivo CSV final do SIAFI/app, sem cabeçalho, para colunas internas padrão.

    Layout usual das linhas de dados: D;UG;Restrição;Motivo;Providência;Valor;|
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


def _linha_eh_cabecalho(valores: list[object]) -> bool:
    norm = [normalizar_coluna(v) for v in valores]
    tem_ug = any(v in ALIAS["ug"] for v in norm)
    tem_restricao = any(v in ALIAS["restricao"] for v in norm)
    return tem_ug and tem_restricao


def _promover_cabecalho_encontrado(df_sem_cabecalho: pd.DataFrame) -> pd.DataFrame | None:
    """Localiza cabeçalho em linhas iniciais, útil para CSV com título, observações ou 'sep=;' antes da tabela."""
    limite = min(30, len(df_sem_cabecalho))
    for idx in range(limite):
        valores = df_sem_cabecalho.iloc[idx].tolist()
        if _linha_eh_cabecalho(valores):
            cab = [texto_siafi(v, 80) or f"coluna_{i+1}" for i, v in enumerate(valores)]
            dados = df_sem_cabecalho.iloc[idx + 1:].copy()
            dados.columns = cab
            dados = dados.dropna(how="all").fillna("")
            # Remove linhas totalmente vazias após normalização textual.
            mask_vazia = dados.apply(lambda r: all(not limpar_espacos(x) for x in r), axis=1)
            dados = dados.loc[~mask_vazia]
            return dados.reset_index(drop=True)
    return None


def _serie_digitos(s: pd.Series) -> pd.Series:
    return s.astype(str).map(lambda x: re.sub(r"\D", "", x))


def _mapear_colunas_por_conteudo(df: pd.DataFrame) -> dict[str, str]:
    """Mapeia UG e Restrição por conteúdo quando não há cabeçalho confiável.

    Só aplica quando há evidência forte de códigos de UG com 6 dígitos e de restrição com 3 dígitos.
    """
    if df.empty or df.shape[1] < 2:
        return {}
    mapa: dict[str, str] = {}
    amostra = df.head(80)
    scores = []
    for col in df.columns:
        dig = _serie_digitos(amostra[col])
        ug_score = int(dig.str.fullmatch(r"\d{6}").sum())
        restr_score = int(dig.str.fullmatch(r"\d{3}").sum())
        scores.append((col, ug_score, restr_score))
    col_ug = max(scores, key=lambda x: x[1])
    col_restr = max([s for s in scores if s[0] != col_ug[0]], key=lambda x: x[2], default=(None, 0, 0))
    if col_ug[1] >= 1 and col_restr[2] >= 1:
        mapa["ug"] = col_ug[0]
        mapa["restricao"] = col_restr[0]
        # Mapeamento posicional auxiliar para layouts simples sem cabeçalho.
        cols = list(df.columns)
        try:
            i_ug = cols.index(col_ug[0])
            i_restr = cols.index(col_restr[0])
            if i_restr + 1 < len(cols):
                mapa.setdefault("motivo", cols[i_restr + 1])
            if i_restr + 2 < len(cols):
                mapa.setdefault("providencia", cols[i_restr + 2])
            if i_restr + 3 < len(cols):
                mapa.setdefault("valor", cols[i_restr + 3])
        except ValueError:
            pass
    return mapa


def _converter_linhas_raw_siafi(texto: str) -> pd.DataFrame | None:
    """Fallback para arquivos H/D/T que ficaram em uma única coluna por problema de separador."""
    registros = []
    competencia = ""
    for linha in texto.splitlines():
        l = linha.strip().strip('"')
        if not l:
            continue
        # Divide por qualquer delimitador comum, preservando campos vazios.
        partes = [p.strip().strip('"') for p in re.split(r"[;|\t,]", l)]
        if not partes:
            continue
        marca = partes[0].upper()
        if marca == "H" and len(partes) > 3:
            competencia = texto_siafi(partes[3], 20)
        elif marca == "D" and len(partes) >= 3:
            registros.append({
                "ug": partes[1] if len(partes) > 1 else "",
                "restricao": partes[2] if len(partes) > 2 else "",
                "motivo": partes[3] if len(partes) > 3 else "",
                "providencia": partes[4] if len(partes) > 4 else "",
                "valor": partes[5] if len(partes) > 5 else "",
                "competencia": competencia,
            })
    if registros:
        return pd.DataFrame(registros).fillna("")
    return None


def _ler_csv_robusto(dados: bytes) -> pd.DataFrame:
    texto = _remover_linha_sep_excel(_decodificar_csv(dados))

    # Fallback inicial para arquivos finais H/D/T que eventualmente não sejam lidos como tabela.
    raw_siafi = _converter_linhas_raw_siafi(texto)
    if raw_siafi is not None and not raw_siafi.empty:
        return raw_siafi

    candidatos: list[str] = []
    sniff = _sniff_delimitador(texto)
    if sniff:
        candidatos.append(sniff)
    candidatos.extend([sep for sep in CSV_SEPARADORES if sep not in candidatos])

    melhor_df = None
    melhor_score = -10_000

    for sep in candidatos:
        try:
            df_header = _ler_csv_com_separador(texto, sep=sep, header=0)
            df_no_header = _ler_csv_com_separador(texto, sep=sep, header=None)
        except Exception:
            continue

        # Prioridade 1: CSV final gerado para SIAFI/app, sem cabeçalho, com linhas H/D/T.
        if _parece_csv_siafi(df_no_header):
            return _converter_csv_siafi_para_tabela(df_no_header)

        # Prioridade 2: cabeçalho fora da primeira linha.
        df_promovido = _promover_cabecalho_encontrado(df_no_header)
        if df_promovido is not None and _tem_colunas_obrigatorias(df_promovido):
            return df_promovido

        # Prioridade 3: arquivo sem cabeçalho, mas com colunas posicionais detectáveis
        # por conteúdo. Isso evita perder a primeira linha quando o CSV começa
        # diretamente com registros, por exemplo: 153062;642;motivo;providência.
        mapa_sem_cabecalho = _mapear_colunas_por_conteudo(df_no_header)
        if mapa_sem_cabecalho:
            df_posicional = df_no_header.copy().fillna("")
            df_posicional.columns = [f"coluna_{i+1}" for i in range(df_posicional.shape[1])]
            return df_posicional

        # Prioridade 4: CSV tabular com cabeçalhos reconhecíveis.
        largura = int(df_header.shape[1])
        obrig = 1000 if _tem_colunas_obrigatorias(df_header) else 0
        posicional = 250 if _mapear_colunas_por_conteudo(df_header) else 0
        linhas = min(len(df_header), 100)
        score = obrig + posicional + largura + linhas
        if score > melhor_score:
            melhor_score = score
            melhor_df = df_header

    if melhor_df is None:
        raise ValueError("Não foi possível ler o arquivo CSV. Verifique a codificação, o separador e o conteúdo do arquivo.")

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
    registros: list[RegistroRestricao] = []
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
