from __future__ import annotations
from datetime import datetime
from pathlib import Path
import base64
import pandas as pd
import streamlit as st

from modules.models import RegistroRestricao, MetadadosRelatorio
from modules.reference_data import carregar_conrestcon, carregar_ugs_validas
from modules.importador_excel_csv import ler_tabela, dataframe_para_registros as tabela_para_registros
from modules.extrator_pdf_siafi import extrair_registros_pdf
from modules.validador import registros_para_dataframe, dataframe_para_registros, validar_registros
from modules.gerador_csv import gerar_csv_siafi, nome_csv_padrao
from modules.relatorios import gerar_xlsx_abas, modelo_importacao, resumo_por_ug, ugs_sem_restricao
from modules.normalizacao import codigo_ug, codigo_restricao, texto_siafi, moeda_para_digitos, normalizar_competencia
from modules.capitalizacao import aplicar_capitalizacao_df, OPCOES_CAPITALIZACAO

APP_TITLE = "Gerador de Arquivo CSV para Upload de Restrições Contábeis no SIAFI"
APP_SUBTITLE = "Importação, validação e tratamento de restrições contábeis por Excel, CSV, PDF SIAFI ou digitação manual."
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / "assets" / "proplan_ufmg.jpg"
MANUAL_PATH = APP_DIR / "docs" / "Manual_Usuario_App_Restricoes_SIAFI.pdf"

def inicializar_estado() -> None:
    if "reset_counter" not in st.session_state:
        st.session_state.reset_counter = 0
    if "registros" not in st.session_state:
        st.session_state.registros = []
    if "meta" not in st.session_state:
        st.session_state.meta = MetadadosRelatorio(mes=str(datetime.now().month).zfill(2), ano=str(datetime.now().year)).__dict__
    if "pdf_processado" not in st.session_state:
        st.session_state.pdf_processado = False

def reiniciar_sessao() -> None:
    contador = int(st.session_state.get("reset_counter", 0)) + 1
    st.session_state.clear()
    st.session_state.reset_counter = contador
    st.session_state.registros = []
    st.session_state.meta = MetadadosRelatorio(mes=str(datetime.now().month).zfill(2), ano=str(datetime.now().year)).__dict__
    st.session_state.pdf_processado = False
    st.rerun()

def adicionar_linha_referencia(df: pd.DataFrame) -> pd.DataFrame:
    df_ref = df.copy()
    df_ref.insert(0, "Linha", [int(i) + 1 for i in df_ref.index])
    return df_ref

def remover_colunas_referencia(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in ["Linha"] if c in df.columns], errors="ignore")

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.markdown("""
<style>
/* Base geral */
.block-container {
    padding-top: 1.35rem;
    padding-bottom: 2.4rem;
    max-width: 1380px;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.2rem;
}

/* Cabeçalho institucional */
.app-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    column-gap: 1.35rem;
    padding: 1.05rem 1.15rem 1.05rem 1.25rem;
    margin: .15rem 0 1.15rem 0;
    border: 1px solid #e6edf5;
    border-radius: 18px;
    background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.app-header-text {
    min-width: 0;
    padding-top: .05rem;
}
.app-title {
    font-size: clamp(1.26rem, 1.82vw, 1.58rem);
    line-height: 1.18;
    font-weight: 750;
    letter-spacing: -0.022em;
    color: #0f172a;
    margin: 0 0 .32rem 0;
    white-space: nowrap;
}
.app-subtitle {
    color: #475569;
    font-size: clamp(.90rem, 1.05vw, 1.00rem);
    line-height: 1.38;
    font-weight: 400;
    margin: 0;
}
.title-logo-box {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    min-width: 116px;
}
.title-logo-box img {
    width: 118px;
    max-width: 118px;
    height: auto;
    display: block;
    opacity: .96;
}

/* Cartões, mensagens e métricas */
.app-card {
    border: 1px solid #e7edf3;
    border-radius: 16px;
    padding: 1.0rem 1.15rem;
    background: #fbfdff;
    margin: .55rem 0 1.0rem 0;
    color: #334155;
}
.metric-card {
    border: 1px solid #e5e7eb;
    border-radius: 14px;
    padding: .85rem;
    background: white;
}
.small-muted {
    color: #64748b;
    font-size: .92rem;
}
.dev-credit {
    font-size: 1.00rem;
    color: #475569;
    line-height: 1.35;
    margin-top: .75rem;
}

/* Hierarquia interna */
h2, h3 {
    letter-spacing: -0.012em;
}
div[data-testid="stMarkdownContainer"] h3 {
    font-size: 1.12rem;
    margin-top: .75rem;
}
div[data-testid="stMarkdownContainer"] h4 {
    font-size: 1.02rem;
    margin-top: .85rem;
    color: #1e293b;
}

/* Abas e botões */
button[kind="primary"], .stDownloadButton button {
    border-radius: 10px !important;
}
.stTabs [data-baseweb="tab-list"] {
    gap: .25rem;
    margin-bottom: .35rem;
}
.stTabs [data-baseweb="tab"] {
    height: 2.55rem;
    padding: 0 .85rem;
}

/* Responsividade */
@media (max-width: 1180px) {
    .app-title { white-space: normal; font-size: 1.28rem; }
    .title-logo-box img { width: 108px; max-width: 108px; }
}
@media (max-width: 760px) {
    .app-header {
        grid-template-columns: 1fr;
        row-gap: .7rem;
        padding: .95rem 1.0rem;
    }
    .title-logo-box {
        justify-content: flex-start;
        min-width: 0;
    }
    .title-logo-box img { width: 96px; max-width: 96px; }
}
</style>
""", unsafe_allow_html=True)

conrestcon = carregar_conrestcon()
ugs_validas = carregar_ugs_validas()

inicializar_estado()

if LOGO_PATH.exists():
    logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
    logo_html = f'<img src="data:image/jpeg;base64,{logo_b64}" alt="Logo PROPLAN/UFMG">'
else:
    logo_html = ""

st.markdown(
    f"""
    <div class="app-header">
        <div class="app-header-text">
            <div class="app-title">{APP_TITLE}</div>
            <div class="app-subtitle">{APP_SUBTITLE}</div>
        </div>
        <div class="title-logo-box">{logo_html}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Opções")
    bloquear_duplicidade = st.checkbox("Bloquear duplicidades", value=True)

    st.divider()
    st.download_button(
        "Baixar modelo de planilha",
        data=modelo_importacao(),
        file_name="modelo_restricoes_siafi.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    if MANUAL_PATH.exists():
        with open(MANUAL_PATH, "rb") as f:
            st.download_button(
                "Baixar Manual do Usuário",
                data=f.read(),
                file_name="Manual_Usuario_App_Restricoes_SIAFI.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
    else:
        st.caption("Manual do usuário não localizado na pasta docs/.")

    with st.expander("Tabelas internas", expanded=False):
        st.caption("CONRESTCON: `data/conrestcon.csv`")
        st.caption("UGs válidas: `data/ugs_validas.csv`")

    st.markdown(
        '<div class="dev-credit"><strong>Desenvolvido por</strong><br>Divisão de Contabilidade/DCF/UFMG</div>',
        unsafe_allow_html=True,
    )

tab_imp, tab_conf, tab_resumo, tab_exp, tab_ref = st.tabs(["📥 Entrada de dados", "🛠️ Conferência e edição", "📊 Resumo", "📤 Exportação", "📚 Referências"])

with tab_imp:
    st.subheader("1. Entrada de dados")
    st.markdown('<div class="app-card">Selecione a origem dos dados. O aplicativo preserva zeros à esquerda, trata campos como texto e valida UG e restrição antes de gerar o arquivo final.</div>', unsafe_allow_html=True)
    origem = st.radio("Origem", ["PDF SIAFI", "Excel/CSV", "Digitação manual"], horizontal=True, key=f"origem_{st.session_state.reset_counter}")

    if origem == "PDF SIAFI":
        arq = st.file_uploader(
            "Anexar relatório PDF de Conformidade Contábil extraído do SIAFI",
            type=["pdf"],
            key=f"pdf_upload_{st.session_state.reset_counter}",
        )
        if arq is not None:
            processar_pdf = st.button("Processar PDF", type="primary")
            if processar_pdf:
                try:
                    meta, regs = extrair_registros_pdf(arq)
                    st.session_state.registros = regs
                    st.session_state.meta.update(meta.__dict__)
                    st.session_state.pdf_processado = True
                    st.success(f"PDF processado. {len(regs)} restrições identificadas automaticamente.")
                except Exception as e:
                    st.error(str(e))
        else:
            st.caption("Anexe um relatório PDF para habilitar o processamento.")

    elif origem == "Excel/CSV":
        arq = st.file_uploader("Anexar planilha Excel ou CSV", type=["xlsx", "xls", "csv"], key=f"planilha_upload_{st.session_state.reset_counter}")
        if arq:
            try:
                df = ler_tabela(arq)
                st.dataframe(df.head(100), use_container_width=True)
                if st.button("Processar planilha", type="primary"):
                    regs = tabela_para_registros(df, "Excel/CSV", arq.name)
                    st.session_state.registros = regs
                    st.success(f"Planilha processada. {len(regs)} registros carregados.")
            except Exception as e:
                st.error(str(e))

    else:
        st.info("Digite ou cole registros na tabela. Para adicionar linhas, use o editor abaixo.")
        df_manual = registros_para_dataframe(st.session_state.registros)
        if df_manual.empty:
            df_manual = pd.DataFrame([RegistroRestricao(origem="Manual").to_dict()])
        edit = st.data_editor(df_manual, num_rows="dynamic", use_container_width=True, key=f"manual_editor_{st.session_state.reset_counter}")
        if st.button("Aplicar registros digitados", type="primary"):
            regs=[]
            for _, row in edit.fillna("").iterrows():
                regs.append(RegistroRestricao(
                    ug=codigo_ug(row.get("ug", "")), restricao=codigo_restricao(row.get("restricao", "")),
                    motivo=texto_siafi(row.get("motivo", "")), providencia=texto_siafi(row.get("providencia", "")),
                    valor=moeda_para_digitos(row.get("valor", "")), competencia=normalizar_competencia(row.get("competencia", "")),
                    grupo=texto_siafi(row.get("grupo", ""), 120), conta_contabil=texto_siafi(row.get("conta_contabil", ""), 40),
                    equacao=texto_siafi(row.get("equacao", ""), 40), situacao=texto_siafi(row.get("situacao", ""), 80),
                    origem="Manual", arquivo_origem="Digitação manual"
                ))
            st.session_state.registros = [r for r in regs if any([r.ug, r.restricao, r.motivo, r.providencia])]
            st.success(f"{len(st.session_state.registros)} registros manuais aplicados.")

with tab_conf:
    st.subheader("2. Conferência, filtros, edição e validação")
    regs = st.session_state.registros
    df_regs = registros_para_dataframe(regs)
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(regs))
    c2.metric("UGs distintas", df_regs["ug"].nunique() if not df_regs.empty else 0)
    c3.metric("Restrições distintas", df_regs["restricao"].nunique() if not df_regs.empty else 0)
    if df_regs.empty:
        st.warning("Nenhum registro carregado.")
    else:
        st.markdown("#### Filtros de consulta e edição")
        f1, f2, f3 = st.columns([1.3, 1.3, 1])
        op_ugs = sorted([x for x in df_regs["ug"].astype(str).unique() if x])
        op_restr = sorted([x for x in df_regs["restricao"].astype(str).unique() if x])
        filtro_ugs = f1.multiselect("Filtrar por UG", op_ugs, placeholder="Todas as UGs")
        filtro_restr = f2.multiselect("Filtrar por Restrição", op_restr, placeholder="Todas as restrições")
        filtro_texto = f3.text_input("Busca textual", placeholder="Motivo, providência, grupo...")

        mask = pd.Series(True, index=df_regs.index)
        if filtro_ugs:
            mask &= df_regs["ug"].astype(str).isin(filtro_ugs)
        if filtro_restr:
            mask &= df_regs["restricao"].astype(str).isin(filtro_restr)
        if filtro_texto:
            cols_busca = [c for c in ["motivo", "providencia", "grupo", "situacao", "conta_contabil", "equacao"] if c in df_regs.columns]
            mask &= df_regs[cols_busca].astype(str).apply(lambda col: col.str.contains(filtro_texto, case=False, na=False)).any(axis=1)
        df_filtrado = df_regs.loc[mask].copy()
        st.caption(f"{len(df_filtrado)} de {len(df_regs)} registros exibidos pelos filtros atuais.")

        with st.expander("Edição em lote com base nos filtros aplicados", expanded=False):
            st.warning("A edição em lote será aplicada somente aos registros atualmente filtrados. Revise os filtros antes de confirmar.")
            b1, b2 = st.columns(2)
            campo_lote = b1.selectbox("Campo a alterar em lote", ["motivo", "providencia", "competencia", "grupo", "situacao", "conta_contabil", "equacao"])
            valor_lote = b2.text_area("Novo valor", height=100, placeholder="Informe o conteúdo que substituirá o campo selecionado nos registros filtrados")
            ccap1, ccap2 = st.columns(2)
            aplicar_cap = ccap1.checkbox("Aplicar capitalização automática ao novo valor", value=True)
            modo_cap = ccap2.selectbox("Modo de capitalização", OPCOES_CAPITALIZACAO, help="Transformação textual controlada, com preservação técnica de siglas, códigos e símbolos financeiros.")
            st.info(f"Registros que serão afetados: {len(df_filtrado)}. A ação usará os filtros atualmente aplicados.")
            confirmar_lote = st.checkbox("Confirmo que revisei os filtros e desejo aplicar a alteração em lote")
            chave_lote = st.text_input("Digite APLICAR para habilitar a edição em lote", value="", key="chave_lote")
            if st.button("Aplicar edição em lote", type="primary", disabled=not confirmar_lote or chave_lote.strip().upper() != "APLICAR" or df_filtrado.empty):
                st.session_state.backup_registros = st.session_state.registros
                df_base = df_regs.copy()
                novo_valor = valor_lote
                if aplicar_cap and campo_lote in ["motivo", "providencia", "grupo", "situacao"]:
                    novo_valor = aplicar_capitalizacao_df(pd.DataFrame({campo_lote: [novo_valor]}), [campo_lote], modo_cap).iloc[0][campo_lote]
                df_base.loc[mask, campo_lote] = novo_valor
                st.session_state.registros = dataframe_para_registros(df_base)
                st.success(f"Edição em lote aplicada em {int(mask.sum())} registro(s).")
                st.rerun()

        with st.expander("Capitalização automática segura nos registros filtrados", expanded=False):
            st.caption("Preserva siglas, códigos, símbolos financeiros e expressões institucionais como SIAFI, UFMG, RMA, RMB, TED, OB, GRU, PCASP, R$ e códigos numéricos.")
            colunas_cap = st.multiselect("Campos para capitalizar", ["motivo", "providencia", "grupo", "situacao"], default=["motivo", "providencia"])
            modo_cap_massa = st.selectbox("Modo", OPCOES_CAPITALIZACAO, key="modo_cap_massa")
            st.info(f"Registros que serão afetados pela capitalização: {len(df_filtrado)}.")
            confirmar_cap = st.checkbox("Confirmo a aplicação da capitalização nos registros filtrados", key="confirmar_cap")
            chave_cap = st.text_input("Digite APLICAR para habilitar a capitalização", value="", key="chave_cap")
            if st.button("Aplicar capitalização nos filtrados", disabled=not confirmar_cap or chave_cap.strip().upper() != "APLICAR" or df_filtrado.empty):
                st.session_state.backup_registros = st.session_state.registros
                df_base = df_regs.copy()
                df_base.loc[mask, colunas_cap] = aplicar_capitalizacao_df(df_base.loc[mask, colunas_cap], colunas_cap, modo_cap_massa)
                st.session_state.registros = dataframe_para_registros(df_base)
                st.success(f"Capitalização aplicada em {int(mask.sum())} registro(s).")
                st.rerun()

        if st.session_state.get("backup_registros") is not None:
            if st.button("Desfazer última alteração em massa/capitalização"):
                st.session_state.registros = st.session_state.backup_registros
                st.session_state.backup_registros = None
                st.success("Última alteração em massa desfeita.")
                st.rerun()

        st.caption("Edite os dados filtrados antes da validação final. Salvar substitui apenas os registros exibidos nos filtros.")
        df_editor = adicionar_linha_referencia(df_filtrado)
        edited = st.data_editor(
            df_editor,
            num_rows="dynamic",
            use_container_width=True,
            height=420,
            key=f"editor_conferencia_{st.session_state.reset_counter}",
            disabled=["Linha"],
            column_config={"Linha": st.column_config.NumberColumn("Linha", help="Referência visual da linha no conjunto de dados carregado. Não compõe a base final nem o CSV.", width="small")},
        )
        edited_sem_ref = remover_colunas_referencia(edited)
        if st.button("Salvar alterações da grade filtrada", type="primary"):
            df_base = df_regs.loc[~mask].copy()
            df_novo = pd.concat([df_base, edited_sem_ref], ignore_index=True)
            st.session_state.registros = dataframe_para_registros(df_novo)
            st.success("Alterações da grade filtrada salvas.")
            st.rerun()
        inconsist = validar_registros(dataframe_para_registros(pd.concat([df_regs.loc[~mask].copy(), edited_sem_ref], ignore_index=True)), conrestcon, ugs_validas, bloquear_duplicidade)
        if inconsist.empty:
            st.success("Validação concluída sem inconsistências impeditivas.")
        else:
            st.error(f"Foram identificadas {len(inconsist)} inconsistências.")
            st.dataframe(inconsist, use_container_width=True, height=320)
            st.download_button("Baixar relatório de inconsistências em Excel", gerar_xlsx_abas({"Inconsistências": inconsist}), "relatorio_inconsistencias.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_resumo:
    st.subheader("3. Resumo estatístico")
    df_regs = registros_para_dataframe(st.session_state.registros)
    if df_regs.empty:
        sem = ugs_sem_restricao(df_regs, ugs_validas)
        st.metric("UGs válidas sem restrição registrada", len(sem))
        st.dataframe(sem, use_container_width=True)
        st.warning("Nenhum registro de restrição carregado.")
    else:
        st.markdown("#### Filtros estatísticos")
        s1, s2 = st.columns(2)
        filtro_ugs_resumo = s1.multiselect("UG", sorted(df_regs["ug"].astype(str).unique()), key="filtro_ug_resumo")
        filtro_restr_resumo = s2.multiselect("Restrição", sorted(df_regs["restricao"].astype(str).unique()), key="filtro_restr_resumo")
        mask_resumo = pd.Series(True, index=df_regs.index)
        if filtro_ugs_resumo:
            mask_resumo &= df_regs["ug"].astype(str).isin(filtro_ugs_resumo)
        if filtro_restr_resumo:
            mask_resumo &= df_regs["restricao"].astype(str).isin(filtro_restr_resumo)
        df_resumo = df_regs.loc[mask_resumo].copy()
        r_ug = resumo_por_ug(df_resumo, ugs_validas)
        r_restr = df_resumo.groupby("restricao").size().reset_index(name="quantidade").merge(conrestcon, left_on="restricao", right_on="codigo_restricao", how="left").drop(columns=["codigo_restricao"]) if not df_resumo.empty else pd.DataFrame(columns=["restricao", "quantidade", "descricao"])
        sem = ugs_sem_restricao(df_regs, ugs_validas)
        m1, m2, m3 = st.columns(3)
        m1.metric("Registros analisados", len(df_resumo))
        m2.metric("UGs com restrição", df_regs["ug"].nunique())
        m3.metric("UGs válidas sem restrição registrada", len(sem))
        st.markdown("#### Restrições por UG")
        st.dataframe(r_ug, use_container_width=True)
        st.markdown("#### Frequência por código de restrição")
        st.dataframe(r_restr.sort_values("quantidade", ascending=False), use_container_width=True)
        st.markdown("#### UGs válidas sem restrição registrada")
        st.dataframe(sem, use_container_width=True, height=260)
        st.download_button("Baixar resumo em Excel", gerar_xlsx_abas({"Registros filtrados": df_resumo, "Resumo por UG": r_ug, "Resumo por Restrição": r_restr, "UGs sem restrição": sem}), "resumo_restricoes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with tab_exp:
    st.subheader("4. Exportação")
    meta = st.session_state.meta
    c1, c2, c3, c4 = st.columns(4)
    nivel = c1.selectbox("Nível", ["1", "2"], index=0 if meta.get("nivel", "1") == "1" else 1)
    codigo_responsavel = c2.text_input("Código responsável", value=meta.get("codigo_responsavel", "153062"))
    mes = c3.text_input("Mês", value=meta.get("mes", str(datetime.now().month).zfill(2)), max_chars=2)
    ano = c4.text_input("Ano", value=meta.get("ano", str(datetime.now().year)), max_chars=4)
    regs = st.session_state.registros
    inconsist = validar_registros(regs, conrestcon, ugs_validas, bloquear_duplicidade)
    if not regs:
        st.warning("Carregue registros antes da exportação.")
    elif not inconsist.empty:
        st.error("A geração do CSV final está bloqueada até a correção das inconsistências.")
        st.download_button("Baixar apenas registros válidos para conferência", gerar_xlsx_abas({"Registros": registros_para_dataframe(regs), "Inconsistências": inconsist}), "conferencia_restricoes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        csv_final = gerar_csv_siafi(nivel, codigo_responsavel, mes, regs)
        st.text_area("Pré-visualização do CSV", csv_final[:5000], height=220)
        st.download_button("Baixar CSV final para upload no SIAFI", data=csv_final.encode("utf-8-sig"), file_name=nome_csv_padrao(mes, ano, codigo_responsavel), mime="text/csv", type="primary")

with tab_ref:
    st.subheader("5. Tabelas internas de referência")
    st.markdown("#### CONRESTCON")
    busca = st.text_input("Filtrar CONRESTCON por código ou descrição")
    df_con = conrestcon.copy()
    if busca:
        mask = df_con.apply(lambda col: col.astype(str).str.contains(busca, case=False, na=False)).any(axis=1)
        df_con = df_con[mask]
    st.dataframe(df_con, use_container_width=True, height=300)
    st.markdown("#### Unidades Gestoras válidas")
    busca_ug = st.text_input("Filtrar UGs por código ou nome")
    df_ug = ugs_validas.copy()
    if busca_ug:
        mask = df_ug.apply(lambda col: col.astype(str).str.contains(busca_ug, case=False, na=False)).any(axis=1)
        df_ug = df_ug[mask]
    st.dataframe(df_ug, use_container_width=True, height=300)
