import io
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Solicitud presupuestal — grilla",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MONTHS = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Set","Oct","Nov","Dic"]
TEXT_COLS = ["Centro de costo", "Dimensión", "Partida"]
LINE_COLS = TEXT_COLS + MONTHS

st.markdown("""
<style>
.block-container {max-width: 1500px; padding-top: 1.4rem; padding-bottom: 6.5rem;}
h1 {letter-spacing:-.6px;}
.section-kicker {font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#315b9d;margin:.4rem 0 .35rem;}
.helper {background:#eef4ff;border:1px solid #dbe7ff;border-radius:10px;padding:11px 15px;color:#0759a6;margin:0 0 14px 0;font-size:.88rem;}
.sticky-summary {position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e4e7ec;
                 padding:11px 4%;z-index:999;box-shadow:0 -4px 14px rgba(16,24,40,.05);}
.sticky-summary .wrap {max-width:1500px;margin:0 auto;display:flex;align-items:center;gap:26px;flex-wrap:wrap;}
.sticky-summary .item {font-size:.88rem;color:#475467;}
.sticky-summary .item b {color:#101828;font-size:1.02rem;}
.sticky-summary .status-ok {background:#ecfdf3;color:#137a4b;padding:5px 13px;border-radius:20px;font-weight:700;}
.sticky-summary .status-warn {background:#fef0c7;color:#b54708;padding:5px 13px;border-radius:20px;font-weight:700;}
/* data_editor: quitar el ruido visual y redondear */
div[data-testid="stDataFrame"] {border:1px solid #e4e7ec;border-radius:10px;overflow:hidden;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ data helpers
def empty_df(n=1):
    rows = [{**{c: "" for c in TEXT_COLS}, **{m: 0.0 for m in MONTHS}} for _ in range(n)]
    return pd.DataFrame(rows, columns=LINE_COLS)

def coerce(df):
    if df is None or len(df) == 0:
        return empty_df(0)
    out = df.copy()
    for c in LINE_COLS:
        if c not in out.columns:
            out[c] = "" if c in TEXT_COLS else 0.0
    for c in TEXT_COLS:
        out[c] = out[c].fillna("").astype(str)
    for m in MONTHS:
        out[m] = pd.to_numeric(out[m], errors="coerce").fillna(0.0)
    return out[LINE_COLS].reset_index(drop=True)

def drop_empty(df):
    df = coerce(df)
    if len(df) == 0:
        return df
    has_text = df[TEXT_COLS].astype(str).agg("".join, axis=1).str.strip() != ""
    has_amt = df[MONTHS].sum(axis=1) != 0
    return df[has_text | has_amt].reset_index(drop=True)

def grid_total(df):
    return float(coerce(df)[MONTHS].sum().sum())

def money(v):
    return f"S/ {v:,.2f}"

# ------------------------------------------------------------------ excel import
def normalize_headers(headers):
    result = {}
    for c in headers:
        low = str(c).strip().replace("\n", " ").lower()
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
    end = next_header if next_header is not None else min(len(raw), header_row + 25)
    part = raw.iloc[header_row + 1:end].copy()
    part.columns = raw.iloc[header_row].tolist()
    part = part.rename(columns=normalize_headers(part.columns))
    keep = [c for c in LINE_COLS if c in part.columns]
    if not keep:
        return empty_df(0)
    part = part[keep].copy()
    bad_starts = ("total", "traslado", "ampliación", "reducción", "responsable",
                  "director", "dirección", "representante", "campo obligatorio", "* para")
    valid = []
    for _, r in part.iterrows():
        vals = [str(r.get(c, "")).strip() if pd.notna(r.get(c, "")) else "" for c in TEXT_COLS]
        joined = " ".join(v.lower() for v in vals if v)
        if any(joined.startswith(x) for x in bad_starts):
            break
        if not any(vals) and all(float(pd.to_numeric(r.get(m, 0), errors="coerce") or 0) == 0 for m in MONTHS):
            if valid:
                break
            continue
        valid.append(r)
    return drop_empty(pd.DataFrame(valid)) if valid else empty_df(0)

def detect_tipo(raw):
    """Lee la marca 'X' junto a la opción — no la mera presencia del texto."""
    options = {"traslado": "Traslado", "ampliación": "Ampliación",
               "ampliacion": "Ampliación", "reducción": "Reducción", "reduccion": "Reducción"}
    for i in range(min(len(raw), 15)):
        row = [str(x).strip() if pd.notna(x) else "" for x in raw.iloc[i].tolist()]
        label = row[0].lower()
        matched = next((v for k, v in options.items() if label.startswith(k)), None)
        if matched:
            if any(cell.lower() in ("x", "✔", "✓", "sí", "si", "1") for cell in row[1:]):
                return matched
    return "Traslado"

def read_excel(uploaded):
    xls = pd.ExcelFile(uploaded)
    sheet = "Formato" if "Formato" in xls.sheet_names else xls.sheet_names[0]
    raw = pd.read_excel(uploaded, sheet_name=sheet, header=None)
    header_rows = [i for i, row in raw.iterrows()
                   if any(str(x).strip().lower() == "centro de costo" for x in row.tolist())]
    origen = destino = empty_df(0)
    if header_rows:
        origen = parse_table(raw, header_rows[0], header_rows[1] if len(header_rows) > 1 else None)
        if len(header_rows) > 1:
            destino = parse_table(raw, header_rows[1], None)
    meta = {}
    for key, r in [("solicitante", 6), ("cargo", 7), ("unidad", 8)]:
        try:
            meta[key] = "" if pd.isna(raw.iloc[r, 3]) else str(raw.iloc[r, 3])
        except Exception:
            meta[key] = ""
    return {"tipo": detect_tipo(raw), "origen": origen, "destino": destino, "meta": meta}, sheet

# ------------------------------------------------------------------ excel export
def export_datos_entrada():
    tipo = st.session_state.tipo
    rows = []
    if tipo == "Traslado":
        for side, key in [("Origen", "_origen_current"), ("Destino", "_destino_current")]:
            for _, r in drop_empty(st.session_state.get(key, empty_df(0))).iterrows():
                rows.append({"Tipo": tipo, "Lado": side, **{c: r[c] for c in LINE_COLS}})
    else:
        for _, r in drop_empty(st.session_state.get("_single_current", empty_df(0))).iterrows():
            rows.append({"Tipo": tipo, "Lado": tipo, **{c: r[c] for c in LINE_COLS}})
    df = pd.DataFrame(rows, columns=["Tipo", "Lado"] + LINE_COLS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="DATOS_ENTRADA", index=False)
    return buf.getvalue()

# ------------------------------------------------------------------ state
def init_state():
    if "tipo" not in st.session_state:
        st.session_state.tipo = "Traslado"
    if "origen_seed" not in st.session_state:
        st.session_state.origen_seed = coerce(pd.DataFrame([
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.016",
             **{m:(100000 if m=="Jun" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.033",
             **{m:(75000 if m=="Set" else 0) for m in MONTHS}},
        ]))
    if "destino_seed" not in st.session_state:
        st.session_state.destino_seed = coerce(pd.DataFrame([
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.015",
             **{m:(40000 if m=="Set" else 60000 if m=="Oct" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.034",
             **{m:(75000 if m=="Nov" else 0) for m in MONTHS}},
        ]))
    st.session_state.setdefault("single_seed", empty_df(1))
    for k in ["_origen_current", "_destino_current", "_single_current"]:
        st.session_state.setdefault(k, empty_df(0))
    st.session_state.setdefault("justificacion", "")
    st.session_state.setdefault("solicitante", "")
    st.session_state.setdefault("unidad", "")

# ------------------------------------------------------------------ grid widget
def column_config():
    cfg = {
        "Centro de costo": st.column_config.TextColumn("Centro de costo", width="medium"),
        "Dimensión": st.column_config.TextColumn("Dim.", width="small"),
        "Partida": st.column_config.TextColumn("Partida", width="medium"),
    }
    for m in MONTHS:
        cfg[m] = st.column_config.NumberColumn(m, format="%d", min_value=0.0, step=100.0, width="small")
    return cfg

def edit_grid(seed_key, mirror_key):
    """El editor es dueño de la edición (vía su key). Solo espejamos para totales/export."""
    seed = coerce(st.session_state[seed_key])
    edited = st.data_editor(
        seed, key=f"editor_{seed_key}", num_rows="dynamic",
        use_container_width=True, hide_index=True,
        column_config=column_config(), column_order=LINE_COLS,
    )
    current = drop_empty(edited)
    st.session_state[mirror_key] = current
    return grid_total(current)

# ------------------------------------------------------------------ app
init_state()

st.title("Nueva solicitud presupuestal")
st.caption("Captura en grilla — mismo modelo mental que tu Excel")

with st.sidebar:
    st.header("Importar / exportar")
    uploaded = st.file_uploader("Importar desde Excel (Formato)", type=["xlsx", "xls"])
    if uploaded and st.button("Importar datos", use_container_width=True):
        try:
            data, sheet = read_excel(uploaded)
            st.session_state.tipo = data["tipo"]
            if data["tipo"] == "Traslado":
                st.session_state.origen_seed = coerce(data["origen"])
                st.session_state.destino_seed = coerce(data["destino"])
                st.session_state.single_seed = empty_df(1)
            else:
                st.session_state.single_seed = coerce(data["origen"])
            st.session_state.solicitante = data["meta"].get("solicitante", "")
            st.session_state.unidad = data["meta"].get("unidad", "")
            for k in ["editor_origen_seed", "editor_destino_seed", "editor_single_seed"]:
                st.session_state.pop(k, None)
            st.session_state.import_message = f"Importado desde «{sheet}» — tipo: {data['tipo']}."
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo importar: {e}")
    if st.session_state.get("import_message"):
        st.success(st.session_state.import_message)
    st.divider()
    st.download_button(
        "Descargar DATOS_ENTRADA (.xlsx)", data=export_datos_entrada(),
        file_name="datos_entrada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.subheader("1. Tipo de solicitud")
tipo = st.radio("Movimiento", ["Traslado", "Ampliación", "Reducción"],
                index=["Traslado","Ampliación","Reducción"].index(st.session_state.tipo),
                horizontal=True, label_visibility="collapsed")
st.session_state.tipo = tipo

st.subheader("2. Datos generales")
a, b, c = st.columns(3)
with a:
    st.session_state.unidad = st.text_input("Unidad / departamento", st.session_state.unidad)
with b:
    st.session_state.solicitante = st.text_input("Responsable", st.session_state.solicitante)
with c:
    periodo = st.selectbox("Periodo", ["2026 · I Semestre", "2026 · II Semestre"])

st.subheader("3. Movimiento presupuestal")
if tipo == "Traslado":
    st.markdown('<div class="helper">Edita como en Excel: teclea, tabula entre meses, pega rangos. '
                'Usa el <b>+</b> al final de la grilla para añadir filas y el ícono de papelera para quitarlas. '
                'El total del origen debe igualar al destino.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-kicker">Origen</div>', unsafe_allow_html=True)
    o = edit_grid("origen_seed", "_origen_current")
    st.markdown('<div class="section-kicker">Destino</div>', unsafe_allow_html=True)
    d = edit_grid("destino_seed", "_destino_current")

    diff = abs(o - d)
    st.markdown("")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total origen", money(o))
    m2.metric("Total destino", money(d))
    m3.metric("Estado", "✓ Balanceado" if diff < .01 and o > 0 else f"⚠ {money(diff)}")
else:
    label = "Destino (ampliación)" if tipo == "Ampliación" else "Presupuesto a reducir"
    st.markdown('<div class="helper">Edita como en Excel: teclea, tabula entre meses, pega rangos. '
                'Usa el <b>+</b> al final de la grilla para añadir filas.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-kicker">{label}</div>', unsafe_allow_html=True)
    s = edit_grid("single_seed", "_single_current")
    st.metric("Total solicitado", money(s))

st.subheader("4. Justificación")
st.session_state.justificacion = st.text_area(
    "Motivo", value=st.session_state.justificacion, height=110,
    placeholder="Explica el motivo y, para ampliaciones con impacto negativo en margen, el plan de compensación.",
    label_visibility="collapsed")

st.subheader("5. Revisar y enviar")
if tipo == "Traslado":
    o = grid_total(st.session_state.get("_origen_current", empty_df(0)))
    d = grid_total(st.session_state.get("_destino_current", empty_df(0)))
    balanced = abs(o - d) < .01
    if balanced and o > 0:
        st.success(f"✓ Solicitud balanceada por {money(o)}")
    elif not balanced:
        st.warning(f"⚠ El traslado no está balanceado. Diferencia: {money(abs(o - d))}")
    else:
        st.info("Agrega líneas de origen y destino para continuar.")
    can_submit = balanced and o > 0
else:
    s = grid_total(st.session_state.get("_single_current", empty_df(0)))
    if s > 0:
        st.success(f"✓ {tipo}: {money(s)}")
    else:
        st.info("Agrega al menos una línea con monto para continuar.")
    can_submit = s > 0

c1, c2 = st.columns(2)
with c1:
    st.button("Guardar borrador", use_container_width=True)
with c2:
    st.button("Enviar para aprobación", type="primary", use_container_width=True, disabled=not can_submit)

# ------------------------------------------------------------------ sticky bar
if tipo == "Traslado":
    o = grid_total(st.session_state.get("_origen_current", empty_df(0)))
    d = grid_total(st.session_state.get("_destino_current", empty_df(0)))
    balanced = abs(o - d) < .01
    status = ("<span class='status-ok'>✓ Balanceado</span>" if balanced and o > 0
              else f"<span class='status-warn'>⚠ Diferencia {money(abs(o - d))}</span>")
    st.markdown(f"""<div class="sticky-summary"><div class="wrap">
        <div class="item">Origen <b>{money(o)}</b></div>
        <div class="item">Destino <b>{money(d)}</b></div>
        <div class="item">{status}</div></div></div>""", unsafe_allow_html=True)
else:
    s = grid_total(st.session_state.get("_single_current", empty_df(0)))
    st.markdown(f"""<div class="sticky-summary"><div class="wrap">
        <div class="item">{tipo} — total <b>{money(s)}</b></div></div></div>""", unsafe_allow_html=True)
