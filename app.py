
import io
from copy import deepcopy
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Solicitud presupuestal",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Set","Oct","Nov","Dic"]
TEXT_COLS = ["Centro de costo", "Dimensión", "Partida"]
LINE_COLS = TEXT_COLS + MONTHS

st.markdown("""
<style>
.block-container {max-width: 1450px; padding-top: 1.4rem; padding-bottom: 6rem;}
h1 {letter-spacing:-.6px;}
.section-kicker {font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#315b9d;margin:.3rem 0 .55rem;}
.helper {background:#e8f1ff;border-radius:10px;padding:13px 16px;color:#0759a6;margin:0 0 20px 0;}
.card {border:1px solid #e1e6ee;border-radius:12px;padding:14px 16px;margin-bottom:12px;background:#fff;}
.card-title {font-weight:750;font-size:1rem;margin-bottom:4px;}
.card-meta {color:#667085;font-size:.82rem;margin-bottom:10px;}
.total-box {background:#f7f9fc;border:1px solid #e5e9f0;border-radius:10px;padding:10px 14px;}
.balance-ok {color:#137a4b;font-weight:750;}
.balance-warn {color:#b54708;font-weight:750;}
.sticky-summary {position:fixed;bottom:0;left:0;right:0;background:white;border-top:1px solid #dfe4ea;padding:10px 4%;z-index:999;}
div[data-testid="stExpander"] {border-radius:10px;}
</style>
""", unsafe_allow_html=True)

def empty_line():
    return {c: "" if c in TEXT_COLS else 0.0 for c in LINE_COLS}

def clean_df(df):
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=LINE_COLS)
    out = df.copy()
    for c in LINE_COLS:
        if c not in out.columns:
            out[c] = "" if c in TEXT_COLS else 0.0
    for c in TEXT_COLS:
        out[c] = out[c].fillna("").astype(str).str.strip()
    for c in MONTHS:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)
    mask = (out[TEXT_COLS].astype(str).agg("".join, axis=1).str.strip() != "") | (out[MONTHS].sum(axis=1) != 0)
    return out.loc[mask, LINE_COLS].reset_index(drop=True)

def df_to_records(df):
    df = clean_df(df)
    return df.to_dict("records")

def records_to_df(records):
    if not records:
        return pd.DataFrame(columns=LINE_COLS)
    return clean_df(pd.DataFrame(records))

def line_total(line):
    return sum(float(line.get(m, 0) or 0) for m in MONTHS)

def money(v):
    return f"S/ {v:,.2f}"

def normalize_headers(headers):
    result = {}
    for c in headers:
        s = str(c).strip().replace("\n", " ")
        low = s.lower()
        if "centro" in low and "costo" in low:
            result[c] = "Centro de costo"
        elif "dimensión" in low or "dimension" in low:
            result[c] = "Dimensión"
        elif "partida" in low:
            result[c] = "Partida"
        else:
            for m in MONTHS:
                if low == m.lower():
                    result[c] = m
    return result

def parse_table(raw, header_row, next_header=None):
    """Extract only the movement table; stops before totals/approval sections."""
    end = next_header if next_header is not None else min(len(raw), header_row + 25)
    part = raw.iloc[header_row + 1:end].copy()
    part.columns = raw.iloc[header_row].tolist()
    part = part.rename(columns=normalize_headers(part.columns))
    keep = [c for c in LINE_COLS if c in part.columns]
    if not keep:
        return pd.DataFrame(columns=LINE_COLS)
    part = part[keep].copy()

    # Stop rows when the first meaningful cell is a section/approval label.
    bad_starts = (
        "total", "traslado de presupuesto", "ampliación de presupuesto",
        "reducción de presupuesto", "responsable del centro",
        "director de administración", "dirección de desarrollo",
        "representante ante rectorado", "campo obligatorio", "* para estos"
    )
    valid_rows = []
    for _, r in part.iterrows():
        vals = [str(r.get(c, "")).strip() if pd.notna(r.get(c, "")) else "" for c in TEXT_COLS]
        joined = " ".join(v.lower() for v in vals if v)
        if any(joined.startswith(x) for x in bad_starts):
            break
        if not any(vals) and all(float(pd.to_numeric(r.get(m, 0), errors="coerce") or 0) == 0 for m in MONTHS):
            # One completely blank row after data ends.
            if valid_rows:
                break
            continue
        valid_rows.append(r)

    if not valid_rows:
        return pd.DataFrame(columns=LINE_COLS)
    return clean_df(pd.DataFrame(valid_rows))

def read_excel(uploaded):
    xls = pd.ExcelFile(uploaded)
    sheet = "Formato" if "Formato" in xls.sheet_names else xls.sheet_names[0]
    raw = pd.read_excel(uploaded, sheet_name=sheet, header=None)

    header_rows = []
    for i, row in raw.iterrows():
        vals = [str(x).strip().replace("\n", " ") if pd.notna(x) else "" for x in row.tolist()]
        if any(v.lower() == "centro de costo" for v in vals):
            header_rows.append(i)

    result = {"origen": pd.DataFrame(columns=LINE_COLS),
              "destino": pd.DataFrame(columns=LINE_COLS),
              "single": pd.DataFrame(columns=LINE_COLS)}

    if header_rows:
        result["origen"] = parse_table(raw, header_rows[0], header_rows[1] if len(header_rows) > 1 else None)
        if len(header_rows) > 1:
            result["destino"] = parse_table(raw, header_rows[1], None)

    meta = {}
    for key, row in [("solicitante", 6), ("cargo", 7), ("unidad", 8)]:
        try:
            meta[key] = "" if pd.isna(raw.iloc[row, 3]) else str(raw.iloc[row, 3])
        except Exception:
            meta[key] = ""
    result["meta"] = meta

    # Detect type from the x marks in the first section.
    try:
        first_text = " ".join(str(x) for x in raw.iloc[:25].fillna("").values.flatten()).lower()
        if "1.2 ampliación" in first_text:
            result["tipo"] = "Ampliación"
        elif "1.3 reducción" in first_text:
            result["tipo"] = "Reducción"
        else:
            result["tipo"] = "Traslado"
    except Exception:
        result["tipo"] = "Traslado"

    return result, sheet

def init_state():
    if "tipo" not in st.session_state:
        st.session_state.tipo = "Traslado"
    if "origen" not in st.session_state:
        st.session_state.origen = [
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.016",
             **{m:(100000 if m=="Jun" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.033",
             **{m:(75000 if m=="Set" else 0) for m in MONTHS}},
        ]
    if "destino" not in st.session_state:
        st.session_state.destino = [
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.015",
             **{m:(40000 if m=="Set" else 60000 if m=="Oct" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.034",
             **{m:(85000 if m=="Nov" else 0) for m in MONTHS}},
        ]
    if "single" not in st.session_state:
        st.session_state.single = []
    if "justificacion" not in st.session_state:
        st.session_state.justificacion = ""
    if "solicitante" not in st.session_state:
        st.session_state.solicitante = ""
    if "cargo" not in st.session_state:
        st.session_state.cargo = ""
    if "unidad" not in st.session_state:
        st.session_state.unidad = ""

def render_line_list(side):
    records = st.session_state[side]
    label = "Origen" if side == "origen" else "Destino"
    for i, line in enumerate(records):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.3, 1.1, 2.0, .9])
            with c1:
                line["Centro de costo"] = st.text_input(
                    "Centro de costo", value=line.get("Centro de costo",""),
                    key=f"{side}_cc_{i}", placeholder="03.08.01.01.01"
                )
            with c2:
                line["Dimensión"] = st.text_input(
                    "Dimensión", value=line.get("Dimensión",""),
                    key=f"{side}_dim_{i}", placeholder="02.01"
                )
            with c3:
                line["Partida"] = st.text_input(
                    "Partida", value=line.get("Partida",""),
                    key=f"{side}_part_{i}", placeholder="94.3.1.1.016"
                )
            with c4:
                st.markdown(f"<div style='padding-top:30px;text-align:right'><b>{money(line_total(line))}</b></div>", unsafe_allow_html=True)

            b1, b2 = st.columns([1, 1])
            with b1:
                with st.expander("Editar distribución mensual", expanded=False):
                    mcols = st.columns(4)
                    for j, m in enumerate(MONTHS):
                        with mcols[j % 4]:
                            line[m] = st.number_input(
                                m, min_value=0.0, step=100.0,
                                value=float(line.get(m,0) or 0),
                                key=f"{side}_{m}_{i}"
                            )
            with b2:
                if st.button("Eliminar línea", key=f"{side}_del_{i}", type="secondary"):
                    records.pop(i)
                    st.rerun()

    if st.button(f"+ Agregar línea a {label}", key=f"{side}_add", use_container_width=True):
        records.append(empty_line())
        st.rerun()

    st.session_state[side] = records

def render_single():
    records = st.session_state.single
    for i, line in enumerate(records):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2.4, 1.1, 2.1])
            with c1:
                line["Centro de costo"] = st.text_input("Centro de costo", value=line.get("Centro de costo",""), key=f"single_cc_{i}")
            with c2:
                line["Dimensión"] = st.text_input("Dimensión", value=line.get("Dimensión",""), key=f"single_dim_{i}")
            with c3:
                line["Partida"] = st.text_input("Partida", value=line.get("Partida",""), key=f"single_part_{i}")
            with st.expander("Editar distribución mensual", expanded=False):
                mcols = st.columns(4)
                for j, m in enumerate(MONTHS):
                    with mcols[j % 4]:
                        line[m] = st.number_input(m, min_value=0.0, step=100.0, value=float(line.get(m,0) or 0), key=f"single_{m}_{i}")
            if st.button("Eliminar línea", key=f"single_del_{i}"):
                records.pop(i)
                st.rerun()
    if st.button("+ Agregar línea", key="single_add", use_container_width=True):
        records.append(empty_line())
        st.rerun()
    st.session_state.single = records

def total_records(records):
    return sum(line_total(x) for x in records)

init_state()

st.title("Nueva solicitud presupuestal")
st.caption("Traslado, ampliación o reducción de presupuesto")

with st.sidebar:
    st.header("Importar / exportar")
    uploaded = st.file_uploader("Importar datos desde Excel", type=["xlsx", "xls"])
    if uploaded and st.button("Importar datos", use_container_width=True):
        try:
            data, sheet = read_excel(uploaded)
            st.session_state.tipo = data["tipo"]
            st.session_state.origen = df_to_records(data["origen"])
            st.session_state.destino = df_to_records(data["destino"])
            st.session_state.single = df_to_records(data["destino"])
            st.session_state.solictante = data["meta"].get("solicitante","")
            st.session_state.solicitante = data["meta"].get("solicitante","")
            st.session_state.cargo = data["meta"].get("cargo","")
            st.session_state.unidad = data["meta"].get("unidad","")
            st.session_state.import_message = f"Importado correctamente desde «{sheet}»."
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo importar el archivo: {e}")
    if st.session_state.get("import_message"):
        st.success(st.session_state.import_message)
    st.divider()
    st.caption("El Excel se usa como fuente de datos; la distribución mensual se transforma a una interfaz web.")
    if st.button("Limpiar formulario", use_container_width=True):
        for k in ["origen","destino","single"]:
            st.session_state[k] = []
        st.session_state.justificacion = ""
        st.rerun()

# Progress
p = st.columns(4)
for i, txt in enumerate(["1 · Tipo", "2 · Movimiento", "3 · Justificación", "4 · Revisar"]):
    p[i].markdown(f"**{txt}**" if i < 2 else txt)

st.subheader("1. Tipo de solicitud")
tipo = st.radio(
    "Selecciona el movimiento", ["Traslado","Ampliación","Reducción"],
    index=["Traslado","Ampliación","Reducción"].index(st.session_state.tipo),
    horizontal=True, label_visibility="collapsed"
)
st.session_state.tipo = tipo

st.subheader("2. Datos generales")
a,b,c = st.columns(3)
with a:
    st.session_state.unidad = st.text_input("Unidad / departamento", st.session_state.unidad)
with b:
    st.session_state.solicitante = st.text_input("Responsable", st.session_state.solicitante)
with c:
    periodo = st.selectbox("Periodo", ["2026 · I Semestre","2026 · II Semestre"])

st.subheader("3. Movimiento presupuestal")
if tipo == "Traslado":
    st.markdown('<div class="helper">En un traslado, el total del origen debe coincidir con el total del destino. Puedes agregar o eliminar tantas líneas como necesites.</div>', unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div class="section-kicker">ORIGEN</div>', unsafe_allow_html=True)
        render_line_list("origen")
        st.markdown(f'<div class="total-box">Total origen: <b>{money(total_records(st.session_state.origen))}</b></div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-kicker">DESTINO</div>', unsafe_allow_html=True)
        render_line_list("destino")
        st.markdown(f'<div class="total-box">Total destino: <b>{money(total_records(st.session_state.destino))}</b></div>', unsafe_allow_html=True)

    o, d = total_records(st.session_state.origen), total_records(st.session_state.destino)
    diff = abs(o-d)
    st.divider()
    q1,q2,q3 = st.columns(3)
    q1.metric("Total origen", money(o))
    q2.metric("Total destino", money(d))
    q3.metric("Estado", "✓ Balanceado" if diff < .01 else f"⚠ Diferencia {money(diff)}")
else:
    label = "Destino" if tipo == "Ampliación" else "Presupuesto a reducir"
    st.markdown(f'<div class="helper">Agrega las líneas presupuestales que correspondan. La distribución mensual se edita solo cuando la necesites.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-kicker">{label.upper()}</div>', unsafe_allow_html=True)
    render_single()
    st.metric("Total solicitado", money(total_records(st.session_state.single)))

st.subheader("4. Justificación")
st.session_state.justificacion = st.text_area(
    "Motivo e impacto de la solicitud",
    value=st.session_state.justificacion,
    height=110,
    placeholder="Explica el motivo de la solicitud y, para ampliaciones con impacto negativo en margen, el plan de compensación.",
    label_visibility="collapsed"
)

st.subheader("5. Revisar y enviar")
if tipo == "Traslado":
    o, d = total_records(st.session_state.origen), total_records(st.session_state.destino)
    if abs(o-d) < .01:
        st.success(f"✓ Solicitud balanceada por {money(o)}")
    else:
        st.warning(f"⚠ El traslado no está balanceado. Diferencia: {money(abs(o-d))}")
else:
    st.success(f"✓ {tipo}: {money(total_records(st.session_state.single))}")

c1, c2 = st.columns(2)
with c1:
    st.button("Guardar borrador", use_container_width=True)
with c2:
    st.button("Enviar para aprobación", type="primary", use_container_width=True)
