# Gerador de Arquivo CSV para Upload de Restrições Contábeis no SIAFI

Aplicativo Streamlit reescrito de forma modular para importar, validar, tratar e gerar arquivo `.csv` de restrições contábeis para uso no SIAFI.

## Funcionalidades

- Importação por PDF de Relatório de Conformidade Contábil do SIAFI.
- Importação por Excel (`.xlsx`) e CSV (`.csv`).
- Digitação manual de registros.
- Validação dos códigos de restrição contra a tabela interna `CONRESTCON`.
- Validação das Unidades Gestoras contra a biblioteca interna de UGs da UFMG.
- Detecção de duplicidades por UG + restrição + competência.
- Relatório de inconsistências em Excel.
- Modelo de planilha para preenchimento.
- Resumo por UG e por código de restrição.
- Exportação do CSV no layout com registros `H`, `D` e `T`.

## Estrutura

```text
app_restricoes_siafi_otimizado/
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── conrestcon.csv
│   └── ugs_validas.csv
├── modules/
│   ├── extrator_pdf_siafi.py
│   ├── gerador_csv.py
│   ├── importador_excel_csv.py
│   ├── models.py
│   ├── normalizacao.py
│   ├── reference_data.py
│   ├── relatorios.py
│   └── validador.py
└── outputs/
```

## Instalação

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Execução

```bash
streamlit run app.py
```

## Tabelas internas

- `data/conrestcon.csv`: códigos válidos de restrição contábil.
- `data/ugs_validas.csv`: Unidades Gestoras válidas, gerada a partir da planilha de UGs fornecida.

## Premissas adotadas

1. O CSV final segue o layout já existente no aplicativo anterior:
   - Cabeçalho: `H;nível;código responsável;mês; ; ;|`
   - Detalhe: `D;UG;restrição;motivo;providência;valor;|`
   - Totalizador: `T;quantidade;;;;;|`
2. A extração de PDF foi desenhada para relatórios pesquisáveis do SIAFI. PDFs escaneados dependem de OCR externo.
3. A rotina de PDF é tolerante a quebras de linha e repetições de cabeçalho/rodapé, mas layouts muito diferentes do modelo podem exigir ajuste no parser.
4. O aplicativo bloqueia a exportação final quando há UG inválida, restrição não cadastrada, duplicidade impeditiva ou campos essenciais vazios.

## Manutenção

Para atualizar a biblioteca de UGs ou a CONRESTCON, substitua os arquivos CSV dentro da pasta `data`, preservando os nomes das colunas:

- `codigo_ug`, `nome_ug`, `situacao`
- `codigo_restricao`, `descricao`

## Evoluções da versão v3

- Filtros por Unidade Gestora (UG), Restrição e busca textual com impacto direto na consulta, grade de edição, edição em lote, capitalização e estatísticas.
- Capitalização textual com seleção restrita às opções: Primeira letra maiúscula, minúsculas, MAIÚSCULAS e Capitalizar Cada Palavra.
- Preservação técnica, sempre que aplicável, de siglas, abreviações institucionais, símbolos financeiros, códigos contábeis e expressões padronizadas.
- Edição em lote com base nos filtros aplicados, com dupla confirmação e digitação da palavra APLICAR para reduzir risco de alterações acidentais.
- Botão para desfazer a última alteração em massa ou capitalização realizada durante a sessão.
- Contagem de UGs válidas sem restrição registrada no painel estatístico.
- Aba Parâmetros com a atribuição: Desenvolvido por Divisão de Contabilidade/DCF/UFMG.
- Manual do usuário em PDF disponível na pasta `docs/` e por botão de download no aplicativo.


## Revisão visual - layout harmonizado

Esta versão preserva a lógica da versão v3 e aplica apenas ajustes visuais no cabeçalho, hierarquia de títulos, espaçamentos, abas, botões e organização geral da página principal.
