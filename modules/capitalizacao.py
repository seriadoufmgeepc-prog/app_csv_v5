from __future__ import annotations
import re
from .normalizacao import limpar_espacos

# Opções expostas ao usuário. Não acrescente novos rótulos na interface sem demanda formal.
OPCOES_CAPITALIZACAO = [
    "Primeira letra maiúscula",
    "minúsculas",
    "MAIÚSCULAS",
    "Capitalizar Cada Palavra",
]

# Termos que normalmente devem permanecer em caixa alta ou formato padronizado.
TERMOS_PRESERVADOS = {
    "UG", "UGS", "UASG", "SIAFI", "SIADS", "RMA", "RMB", "DCF", "PROPLAN", "PRA", "DTI", "STN", "MCASP",
    "NBC", "TSP", "CONRESTCON", "CSV", "PDF", "XLSX", "PCASP", "OB", "GRU", "TED", "RPNP", "RPP",
    "VPD", "VPA", "ISSQN", "IRRF", "PSS", "INSS", "FGTS", "R$", "CPF", "CNPJ", "UFMG",
    "TAE", "TAES", "PROGRAD", "PRPq", "PRPQ", "FACE", "FAFICH", "ICB", "ICEX", "IGC", "EBA", "EAD", "DED",
    "SIPAC", "SICPAT", "PNCP", "BGU", "UGR", "NE", "NL", "DH", "DU", "DARF", "GPS", "NS",
}


FORMA_PADRAO = {termo.upper(): termo.upper() for termo in TERMOS_PRESERVADOS}
FORMA_PADRAO.update({"PRPQ": "PRPq", "R$": "R$"})

MINUSCULAS_TITULO = {"a", "à", "ao", "aos", "as", "às", "com", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos", "o", "os", "ou", "para", "por", "sem", "sob", "sobre"}

RE_CODIGO = re.compile(r"^(?:\d+[\d./-]*|[A-Z]{2,}\d+[A-Z0-9./-]*|\d+[A-Z]+[A-Z0-9./-]*)$")
RE_MOEDA = re.compile(r"^(?:R\$|US\$|€|£)?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?$|^\d+(?:,\d+)?%$")
RE_SIGLA_COM_PONTOS = re.compile(r"^(?:[A-Z]\.){2,}$")


def _separar_pontuacao(token: str) -> tuple[str, str, str]:
    m = re.match(r"(^[^\wÀ-ÿ$€£]*)([\wÀ-ÿ$€£./-]+)([^\wÀ-ÿ$€£]*$)", token, flags=re.UNICODE)
    if not m:
        return "", token, ""
    pre, miolo, suf = m.group(1), m.group(2), m.group(3)
    # desloca pontuação final comum para o sufixo, preservando pontos internos de códigos/valores.
    while miolo and miolo[-1] in ".,;:!?":
        suf = miolo[-1] + suf
        miolo = miolo[:-1]
    return pre, miolo, suf


def _deve_preservar(token: str) -> bool:
    t = token.strip()
    if not t:
        return True
    _, miolo, _ = _separar_pontuacao(t)
    base = miolo.upper()
    if base in TERMOS_PRESERVADOS:
        return True
    if RE_MOEDA.match(miolo) or RE_CODIGO.match(miolo) or RE_SIGLA_COM_PONTOS.match(miolo):
        return True
    # Preserva siglas compostas com hífen/barra, como DCF/UFMG ou EAD/DED.
    if re.fullmatch(r"[A-ZÁÉÍÓÚÃÕÇ0-9]{2,}(?:[-/][A-ZÁÉÍÓÚÃÕÇ0-9]{2,})+", base):
        return True
    return False


def _token_preservado_padrao(token: str) -> str:
    pre, miolo, suf = _separar_pontuacao(token)
    base = miolo.upper()
    if base in FORMA_PADRAO:
        return f"{pre}{FORMA_PADRAO[base]}{suf}"
    if re.fullmatch(r"[A-ZÁÉÍÓÚÃÕÇ0-9]{2,}(?:[-/][A-ZÁÉÍÓÚÃÕÇ0-9]{2,})+", base):
        return f"{pre}{base}{suf}"
    return token


def _lower_preservando(token: str) -> str:
    return _token_preservado_padrao(token) if _deve_preservar(token) else token.lower()


def _upper_preservando(token: str) -> str:
    return _token_preservado_padrao(token) if _deve_preservar(token) else token.upper()


def _capitalizar_token(token: str, posicao: int = 0, titulo: bool = False) -> str:
    if _deve_preservar(token):
        return _token_preservado_padrao(token)
    pre, palavra, suf = _separar_pontuacao(token)
    if not palavra:
        return token
    palavra_lower = palavra.lower()
    if titulo and posicao > 0 and palavra_lower in MINUSCULAS_TITULO:
        nova = palavra_lower
    else:
        nova = palavra_lower[:1].upper() + palavra_lower[1:]
    return f"{pre}{nova}{suf}"


def capitalizar_texto_seguro(texto: object, modo: str = "Primeira letra maiúscula") -> str:
    """Transforma texto preservando siglas, códigos, símbolos financeiros e expressões institucionais.

    Modos válidos:
    - Primeira letra maiúscula
    - minúsculas
    - MAIÚSCULAS
    - Capitalizar Cada Palavra
    """
    original = limpar_espacos(texto)
    if not original:
        return ""
    if modo not in OPCOES_CAPITALIZACAO:
        modo = "Primeira letra maiúscula"

    partes = re.split(r"(\s+)", original)

    if modo == "minúsculas":
        return "".join(_lower_preservando(p) if not p.isspace() else p for p in partes)

    if modo == "MAIÚSCULAS":
        return "".join(_upper_preservando(p) if not p.isspace() else p for p in partes)

    if modo == "Capitalizar Cada Palavra":
        pos = 0
        saida = []
        for p in partes:
            if not p or p.isspace():
                saida.append(p)
                continue
            saida.append(_capitalizar_token(p, posicao=pos, titulo=True))
            pos += 1
        return "".join(saida)

    # Primeira letra maiúscula: aplica caixa baixa preservando termos protegidos e capitaliza o início de frases.
    saida = []
    capitalizar_proxima = True
    for token in partes:
        if not token or token.isspace():
            saida.append(token)
            continue
        if _deve_preservar(token):
            novo = _token_preservado_padrao(token)
        else:
            novo = token.lower()
            if capitalizar_proxima:
                novo = _capitalizar_token(novo, posicao=0, titulo=False)
        saida.append(novo)
        capitalizar_proxima = bool(re.search(r"[.!?;:]['\")\]]*$", token))
    return "".join(saida)


def aplicar_capitalizacao_df(df, colunas: list[str], modo: str = "Primeira letra maiúscula"):
    out = df.copy()
    for col in colunas:
        if col in out.columns:
            out[col] = out[col].apply(lambda x: capitalizar_texto_seguro(x, modo))
    return out
