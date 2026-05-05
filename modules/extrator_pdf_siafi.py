from __future__ import annotations
import re
from typing import Tuple
from pypdf import PdfReader
from .models import RegistroRestricao, MetadadosRelatorio
from .normalizacao import limpar_espacos, texto_siafi, codigo_ug, codigo_restricao, moeda_para_digitos, normalizar_competencia

RE_UG = re.compile(r"UG:\s*(\d{6})\s*-\s*(.+?)(?=\n(?:Grupo:|Restrição:|001|Versão|$))", re.S)
RE_GRUPO = re.compile(r"Grupo:\s*(\d{3})\s*-\s*(.+)")
RE_RESTR = re.compile(r"Restrição:\s*(\d{3})\s*-\s*(.+)")
RE_VALOR = re.compile(r"Valor:\s*([\d\.]+,\d{2})")

def extrair_paginas(uploaded_file) -> list[str]:
    reader = PdfReader(uploaded_file)
    textos = []
    for page in reader.pages:
        textos.append(page.extract_text() or "")
    return textos

def extrair_metadados(texto_total: str) -> MetadadosRelatorio:
    meta = MetadadosRelatorio()
    meta.layout_pdf_reconhecido = "RELATÓRIO DE CONFORMIDADE CONTÁBIL" in texto_total or "RELATORIO DE CONFORMIDADE CONTABIL" in texto_total
    m = re.search(r"Mês de Referência:\s*([^\n]+)", texto_total)
    comp = ""
    if m:
        comp = normalizar_competencia(m.group(1))
    if "/" not in comp:
        # Em alguns PDFs o extrator inverte a ordem: "Mar/2026Mês de Referência".
        m = re.search(r"([A-Za-zçÇãÃéÉ]{3,9}\s*/\s*\d{4})\s*Mês de Referência", texto_total)
        if m:
            comp = normalizar_competencia(m.group(1))
    if "/" in comp:
        meta.mes, meta.ano = (comp.split("/") + [""])[:2]
    m = re.search(r"Setorial Contábil:\s*(\d{6})\s*-\s*([^\n]+)", texto_total)
    if m:
        meta.codigo_responsavel = m.group(1)
        meta.setorial_contabil = m.group(1)
    m = re.search(r"Entidade:\s*\n?\s*(\d)\s*-\s*([^\n]+)", texto_total)
    if m:
        meta.situacao = limpar_espacos(m.group(2))
    m = re.search(r"Data e hora da consulta:[\s\S]{0,80}?(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", texto_total)
    if m:
        meta.data_consulta = limpar_espacos(m.group(1))
    return meta

def _limpar_texto_pagina(texto: str) -> str:
    texto = texto.replace("\r", "\n")
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto

def _campo_multilinha(bloco: str, nome: str, proximos: list[str]) -> str:
    padrao = rf"{nome}:\s*(.*?)(?=\n(?:{'|'.join(map(re.escape, proximos))}):|\n(?:001|Versão|Operação|Unidade Gestora)|$)"
    m = re.search(padrao, bloco, flags=re.S)
    if not m:
        return ""
    valor = m.group(1)
    # Remove paginação/rodapé que costuma vir colada ao último campo do PDF.
    valor = re.sub(r"\s*\d+\s+de\s+\d+\s*\d{0,3}\s*$", "", valor)
    valor = re.sub(r"\s*Versão Data/Hora[\s\S]*$", "", valor)
    return texto_siafi(valor)

def _separar_restricoes(bloco_ug: str) -> list[tuple[str, str]]:
    matches = list(RE_RESTR.finditer(bloco_ug))
    partes=[]
    for i,m in enumerate(matches):
        ini=m.start()
        fim=matches[i+1].start() if i+1 < len(matches) else len(bloco_ug)
        partes.append((m.group(1), bloco_ug[ini:fim]))
    return partes

def extrair_registros_pdf(uploaded_file) -> Tuple[MetadadosRelatorio, list[RegistroRestricao]]:
    paginas = extrair_paginas(uploaded_file)
    texto_total = "\n".join(paginas)
    meta = extrair_metadados(texto_total)
    if not texto_total.strip():
        raise ValueError("O PDF não possui texto pesquisável. Será necessário OCR antes da importação automática.")
    if not meta.layout_pdf_reconhecido:
        raise ValueError("O layout do PDF não foi reconhecido como Relatório de Conformidade Contábil do SIAFI.")
    registros=[]
    for n_pagina, texto in enumerate(paginas, start=1):
        texto=_limpar_texto_pagina(texto)
        m_ug = RE_UG.search(texto)
        if not m_ug:
            continue
        ug = codigo_ug(m_ug.group(1))
        ug_nome = texto_siafi(m_ug.group(2), 180)
        situacao = "Com Restrição" if re.search(r"\nCom Restrição\n", texto) else "Sem Restrição"
        grupo_atual = ""
        linhas = texto.splitlines()
        for i, linha in enumerate(linhas):
            gm = RE_GRUPO.search(linha)
            if gm:
                grupo_atual = f"{gm.group(1)} - {limpar_espacos(gm.group(2))}"
            rm = RE_RESTR.search(linha)
            if rm:
                bloco = "\n".join(linhas[i:])
                next_restr = re.search(r"\nRestrição:\s*\d{3}\s*-", bloco[1:])
                if next_restr:
                    bloco = bloco[:next_restr.start()+1]
                # se houver novo Grupo antes da próxima restrição, corta para não engolir a próxima seção
                next_group = re.search(r"\nGrupo:\s*\d{3}\s*-", bloco[1:])
                if next_group:
                    bloco = bloco[:next_group.start()+1]
                valor = ""
                vm = RE_VALOR.search(bloco)
                if vm:
                    valor = moeda_para_digitos(vm.group(1))
                registros.append(RegistroRestricao(
                    ug=ug,
                    restricao=codigo_restricao(rm.group(1)),
                    motivo=_campo_multilinha(bloco, "Motivo", ["Providência", "Valor", "Restrição", "Grupo"]),
                    providencia=_campo_multilinha(bloco, "Providência", ["Restrição", "Grupo", "Valor"]),
                    valor=valor,
                    competencia=f"{meta.mes}/{meta.ano}" if meta.mes and meta.ano else "",
                    grupo=grupo_atual,
                    situacao=situacao,
                    origem="PDF SIAFI",
                    arquivo_origem=getattr(uploaded_file, "name", ""),
                    pagina_pdf=str(n_pagina),
                ))
    return meta, registros
