import io
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Solicitud presupuestal",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Set","Oct","Nov","Dic"]
LINE_COLS = ["Centro de costo", "Dimensión", "Partida"] + MONTHS
NUMERIC_COLS = MONTHS

st.markdown("""
<style>
.block-container {max-width: 1450px; padding-top: 1.5rem; padding-bottom: 5rem;}
h1 {letter-spacing:-.5px;}
.small-muted {color:#667085;font-size:.82rem;}
.section-title {font-size:.78rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em;color:#315b9d;margin:.4rem 0 .7rem;}
.total-card {background:#f8fafc;border:1px solid #e6eaf0;border-radius:10px;padding:.7rem 1rem;}
.total-label {font-size:.68rem;color:#667085;text-transform:uppercase;}
.total-value {font-size:1.15rem;font-weight:800;}
.status-ok {color:#18764b;font-weight:800;}
.status-warn {color:#a45c12;font-weight:800;}
div[data-testid="stDataEditor"] {border-radius:10px;}
</style>
""", unsafe_allow_html=True)

def empty_df():
    return pd.DataFrame(columns=LINE_COLS)

def normalize_df(df):
    """Normalizes imported Excel data into the web app line format."""
    df = df.copy()
    # Normalize header names.
    rename = {}
    for c in df.columns:
        s = str(c).strip().replace("\n", " ")
        low = s.lower()
        if "centro" in low and "costo" in low:
            rename[c] = "Centro de costo"
        elif "dimensión" in low or "dimension" in low:
            rename[c] = "Dimensión"
        elif "partida" in low:
            rename[c] = "Partida"
        else:
            for m in MONTHS:
                if low == m.lower():
                    rename[c] = m
    df = df.rename(columns=rename)
    keep = [c for c in LINE_COLS if c in df.columns]
    if not keep:
        return empty_df()
    df = df[keep].copy()
    for c in LINE_COLS:
        if c not in df.columns:
            df[c] = "" if c in ["Centro de costo","Dimensión","Partida"] else 0.0
    for c in MONTHS:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    for c in ["Centro de costo","Dimensión","Partida"]:
        df[c] = df[c].fillna("").astype(str).str.strip()
    # Keep only meaningful rows.
    df = df[(df["Centro de costo"] != "") | (df["Partida"] != "") | (df[MONTHS].sum(axis=1) != 0)]
    return df[LINE_COLS].reset_index(drop=True)

def read_excel(uploaded):
    """Reads the workbook supplied by the user and extracts the Formato sheet."""
    xls = pd.ExcelFile(uploaded)
    sheet = "Formato" if "Formato" in xls.sheet_names else xls.sheet_names[0]
    raw = pd.read_excel(uploaded, sheet_name=sheet, header=None)
    # The source template has the movement tables beginning around rows 26/44.
    header_rows = []
    for i, row in raw.iterrows():
        vals = [str(x).strip().replace("\n"," ") if pd.notna(x) else "" for x in row.tolist()]
        if any("Centro de costo" in x for x in vals):
            header_rows.append(i)
    result = {}
    if header_rows:
        # First table = Origen; second = Destino.
        for idx, h in enumerate(header_rows[:2]):
            end = header_rows[idx+1] if idx+1 < len(header_rows) else len(raw)
            part = raw.iloc[h+1:end].copy()
            part.columns = raw.iloc[h].tolist()
            part = part.loc[:, ~part.columns.duplicated()]
            norm = normalize_df(part)
            result["origen" if idx == 0 else "destino"] = norm
    else:
        # Fallback: try regular header import.
        regular = pd.read_excel(uploaded, sheet_name=sheet)
        result["destino"] = normalize_df(regular)
    # Extract basic metadata from known cells of the template.
    meta = {}
    try:
        meta["solicitante"] = raw.iloc[6,3] if pd.notna(raw.iloc[6,3]) else ""
        meta["cargo"] = raw.iloc[7,3] if pd.notna(raw.iloc[7,3]) else ""
        meta["unidad"] = raw.iloc[8,3] if pd.notna(raw.iloc[8,3]) else ""
    except Exception:
        pass
    result["meta"] = meta
    return result, sheet

def total(df):
    if df.empty:
        return 0.0
    return float(df[MONTHS].sum().sum())

def format_soles(v):
    return f"S/ {v:,.2f}"

def editor(df, key):
    edited = st.data_editor(
        df,
        key=key,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "Centro de costo": st.column_config.TextColumn("Centro de costo", width="medium"),
            "Dimensión": st.column_config.TextColumn("Dimensión", width="small"),
            "Partida": st.column_config.TextColumn("Partida", width="medium"),
            **{m: st.column_config.NumberColumn(m, min_value=0, step=0.01, format="%.2f") for m in MONTHS},
        },
    )
    return edited

def init():
    if "tipo" not in st.session_state:
        st.session_state.tipo = "Traslado"
    if "origen" not in st.session_state:
        st.session_state.origen = pd.DataFrame([
            ["03.08.01.06.02","02.01","94.3.1.1.016",0,0,0,0,0,100000,0,0,0,0,0,0],
            ["03.08.01.06.02","02.01","94.5.1.1.033",0,0,0,0,0,0,75000,0,0,0,0,0],
        ], columns=LINE_COLS)
    if "destino" not in st.session_state:
        st.session_state.destino = pd.DataFrame([
            ["03.08.01.06.02","02.01","94.3.1.1.015",0,0,0,0,0,0,0,0,40000,60000,0,0],
            ["03.08.01.06.02","02.01","94.5.1.1.034",0,0,0,0,0,0,0,0,0,0,0,85000],
        ], columns=LINE_COLS)
    if "single" not in st.session_state:
        st.session_state.single = pd.DataFrame(columns=LINE_COLS)
    if "justificacion" not in st.session_state:
        st.session_state.justificacion = ""

init()

st.title("Nueva solicitud presupuestal")
st.markdown('<div class="small-muted">Traslado, ampliación o reducción de presupuesto · Prototipo Streamlit</div>', unsafe_allow_html=True)

# Sidebar: import/export
with st.sidebar:
    st.header("Herramientas")
    uploaded = st.file_uploader(
        "Importar desde Excel",
        type=["xlsx","xls"],
        help="Puedes importar el formato actual de traslado/ampliación de presupuesto.",
    )
    if uploaded is not None:
        if st.button("Importar datos", use_container_width=True):
            try:
                data, sheet = read_excel(uploaded)
                if "origen" in data:
                    st.session_state.origen = data["origen"]
                if "destino" in data:
                    st.session_state.destino = data["destino"]
                if data.get("meta"):
                    st.session_state.solicitante = str(data["meta"].get("solicitante",""))
                    st.session_state.cargo = str(data["meta"].get("cargo",""))
                    st.session_state.unidad = str(data["meta"].get("unidad",""))
                st.session_state.import_message = f"Importado correctamente desde la hoja «{sheet}»."
            except Exception as e:
                st.error(f"No se pudo importar el archivo: {e}")
    if "import_message" in st.session_state:
        st.success(st.session_state.import_message)

    st.divider()
    st.caption("La importación conserva centro de costo, dimensión, partida y distribución mensual.")
    if st.button("Limpiar formulario", use_container_width=True):
        st.session_state.origen = empty_df()
        st.session_state.destino = empty_df()
        st.session_state.single = empty_df()
        st.session_state.justificacion = ""
        st.rerun()

# Step indicator
steps = ["1 · Tipo", "2 · Partidas", "3 · Justificación", "4 · Revisar"]
cols = st.columns(4)
for i, s in enumerate(steps):
    cols[i].markdown(f"**{s}**" if i < 2 else s)

st.subheader("1. Tipo de solicitud")
tipo = st.radio(
    "Selecciona el movimiento",
    ["Traslado", "Ampliación", "Reducción"],
    index=["Traslado","Ampliación","Reducción"].index(st.session_state.tipo),
    horizontal=True,
)
st.session_state.tipo = tipo

st.subheader("2. Datos generales")
c1,c2,c3 = st.columns(3)
with c1:
    departamento = st.selectbox("Departamento / unidad", ["Arquitectura e Ingenierías de la Construcción","Otra unidad"])
with c2:
    solicitante = st.text_input("Responsable", value=st.session_state.get("solicitante",""))
with c3:
    periodo = st.selectbox("Periodo", ["2026 · I Semestre","2026 · II Semestre"])

if tipo == "Traslado":
    st.subheader("3. Movimiento presupuestal")
    st.info("En un traslado, el total del origen debe coincidir con el total del destino. Puedes agregar o eliminar tantas líneas como necesites.")

    a,b = st.columns(2)
    with a:
        st.markdown('<div class="section-title">Origen</div>', unsafe_allow_html=True)
        st.session_state.origen = editor(st.session_state.origen, "editor_origen")
        st.caption(f"Total origen: **{format_soles(total(st.session_state.origen))}**")
    with b:
        st.markdown('<div class="section-title">Destino</div>', unsafe_allow_html=True)
        st.session_state.destino = editor(st.session_state.destino, "editor_destino")
        st.caption(f"Total destino: **{format_soles(total(st.session_state.destino))}**")

    o = total(st.session_state.origen)
    d = total(st.session_state.destino)
    diff = abs(o-d)
    x,y,z = st.columns(3)
    x.metric("Total origen", format_soles(o))
    y.metric("Total destino", format_soles(d))
    z.metric("Validación", "✓ Balanceado" if diff < .01 else f"⚠ Diferencia {format_soles(diff)}")

else:
    st.subheader("3. Partidas presupuestales")
    label = "Destino" if tipo == "Ampliación" else "Presupuesto a reducir"
    st.info(f"Agrega tantas líneas como necesites. Cada línea puede distribuirse entre los 12 meses.")
    st.markdown(f'<div class="section-title">{label}</div>', unsafe_allow_html=True)
    st.session_state.single = editor(st.session_state.single, "editor_single")
    st.metric("Total solicitado", format_soles(total(st.session_state.single)))

st.subheader("4. Justificación")
st.session_state.justificacion = st.text_area(
    "Motivo e impacto de la solicitud",
    value=st.session_state.justificacion,
    height=110,
    placeholder="Explica el motivo de la solicitud y, para ampliaciones con impacto negativo en margen, el plan de compensación.",
)

st.subheader("5. Revisar y enviar")
if tipo == "Traslado":
    o, d = total(st.session_state.origen), total(st.session_state.destino)
    if abs(o-d) < .01:
        st.success(f"✓ Solicitud balanceada: {format_soles(o)}")
    else:
        st.warning(f"⚠ El traslado no está balanceado. Diferencia: {format_soles(abs(o-d))}")
else:
    st.success(f"✓ {tipo}: {format_soles(total(st.session_state.single))}")

if st.button("Generar Excel de la solicitud", use_container_width=True):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        info = pd.DataFrame({
            "Campo":["Tipo","Departamento","Responsable","Periodo","Justificación"],
            "Valor":[tipo,departamento,solicitante,periodo,st.session_state.justificacion]
        })
        info.to_excel(writer, sheet_name="Solicitud", index=False)
        if tipo == "Traslado":
            st.session_state.origen.assign(TotalLinea=st.session_state.origen[MONTHS].sum(axis=1)).to_excel(writer, sheet_name="Origen", index=False)
            st.session_state.destino.assign(TotalLinea=st.session_state.destino[MONTHS].sum(axis=1)).to_excel(writer, sheet_name="Destino", index=False)
        else:
            st.session_state.single.assign(TotalLinea=st.session_state.single[MONTHS].sum(axis=1)).to_excel(writer, sheet_name="Partidas", index=False)
    st.download_button(
        "Descargar Excel",
        output.getvalue(),
        file_name=f"solicitud_presupuestal_{datetime.now():%Y%m%d_%H%M}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.markdown("---")
st.caption("Prototipo UX · La lógica de aprobación y las tablas maestras pueden conectarse posteriormente a tu base de datos.")
