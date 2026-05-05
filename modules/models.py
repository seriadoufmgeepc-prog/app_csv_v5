from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict

@dataclass
class RegistroRestricao:
    ug: str = ""
    restricao: str = ""
    motivo: str = ""
    providencia: str = ""
    valor: str = ""
    competencia: str = ""
    grupo: str = ""
    conta_contabil: str = ""
    equacao: str = ""
    situacao: str = ""
    origem: str = "Manual"
    arquivo_origem: str = ""
    linha_origem: str = ""
    pagina_pdf: str = ""

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

@dataclass
class MetadadosRelatorio:
    nivel: str = "1"
    codigo_responsavel: str = "153062"
    setorial_contabil: str = "153062"
    mes: str = ""
    ano: str = ""
    situacao: str = ""
    entidade: str = ""
    entidade_nome: str = ""
    data_consulta: str = ""
    layout_pdf_reconhecido: bool = False
