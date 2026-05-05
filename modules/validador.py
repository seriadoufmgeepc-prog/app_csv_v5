from __future__ import annotations
from collections import Counter
import pandas as pd
from .models import RegistroRestricao
from .normalizacao import limpar_espacos

COLS_INCONSIST = ["origem", "arquivo_origem", "linha_origem", "pagina_pdf", "ug", "restricao", "tipo_erro", "descricao", "sugestao"]

def validar_registros(registros: list[RegistroRestricao], conrestcon: pd.DataFrame, ugs_validas: pd.DataFrame, bloquear_duplicidade: bool=True) -> pd.DataFrame:
    codigos_validos = set(conrestcon["codigo_restricao"].astype(str).str.zfill(3))
    ugs_validas_set = set(ugs_validas["codigo_ug"].astype(str).str.zfill(6))
    problemas=[]
    chaves = Counter((r.ug, r.restricao, r.competencia) for r in registros)
    for idx, r in enumerate(registros, start=1):
        base = {"origem": r.origem, "arquivo_origem": r.arquivo_origem, "linha_origem": r.linha_origem or str(idx), "pagina_pdf": r.pagina_pdf, "ug": r.ug, "restricao": r.restricao}
        if not r.ug or len(r.ug)!=6 or not r.ug.isdigit():
            problemas.append({**base, "tipo_erro":"UG inválida", "descricao":"A UG deve conter 6 dígitos.", "sugestao":"Informe uma UG com 6 dígitos."})
        elif r.ug not in ugs_validas_set:
            problemas.append({**base, "tipo_erro":"UG não cadastrada", "descricao":"A UG não consta na biblioteca interna de UGs válidas.", "sugestao":"Verifique a UG ou atualize data/ugs_validas.csv."})
        if not r.restricao or len(r.restricao)!=3 or not r.restricao.isdigit():
            problemas.append({**base, "tipo_erro":"Restrição inválida", "descricao":"A restrição deve conter 3 dígitos.", "sugestao":"Informe o código CONRESTCON com 3 dígitos."})
        elif r.restricao not in codigos_validos:
            problemas.append({**base, "tipo_erro":"Restrição não cadastrada", "descricao":"O código não consta na tabela CONRESTCON interna.", "sugestao":"Consulte a aba CONRESTCON ou atualize data/conrestcon.csv."})
        if not limpar_espacos(r.motivo):
            problemas.append({**base, "tipo_erro":"Motivo vazio", "descricao":"O campo motivo está vazio.", "sugestao":"Preencha o motivo antes da geração do arquivo final."})
        if not limpar_espacos(r.providencia):
            problemas.append({**base, "tipo_erro":"Providência vazia", "descricao":"O campo providência está vazio.", "sugestao":"Preencha a providência antes da geração do arquivo final."})
        if len(r.motivo) > 1024 or len(r.providencia) > 1024:
            problemas.append({**base, "tipo_erro":"Texto excedente", "descricao":"Motivo ou providência excede 1024 caracteres.", "sugestao":"Reduza o texto para o limite aceito."})
        if bloquear_duplicidade and chaves[(r.ug, r.restricao, r.competencia)] > 1:
            problemas.append({**base, "tipo_erro":"Duplicidade", "descricao":"Existe mais de um registro com a mesma UG, restrição e competência.", "sugestao":"Mantenha apenas um registro ou diferencie a competência."})
    return pd.DataFrame(problemas, columns=COLS_INCONSIST)

def registros_para_dataframe(registros: list[RegistroRestricao]) -> pd.DataFrame:
    return pd.DataFrame([r.to_dict() for r in registros])

def dataframe_para_registros(df: pd.DataFrame) -> list[RegistroRestricao]:
    if df.empty:
        return []
    campos = set(RegistroRestricao().__dict__.keys())
    regs=[]
    for _, row in df.fillna("").iterrows():
        d={c: str(row.get(c, "")) for c in campos}
        regs.append(RegistroRestricao(**d))
    return regs
