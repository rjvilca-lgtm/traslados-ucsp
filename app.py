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
.block-container {max-width: 1450px; padding-top: 1.4rem; padding-bottom: 7rem;}
h1 {letter-spacing:-.6px;}
.section-kicker {font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#315b9d;margin:.3rem 0 .55rem;}
.helper {background:#e8f1ff;border-radius:10px;padding:13px 16px;color:#0759a6;margin:0 0 20px 0;font-size:.9rem;}
.card {border:1px solid #e1e6ee;border-radius:12px;padding:14px 16px;margin-bottom:12px;background:#fff;}
.card-title {font-weight:750;font-size:1rem;margin-bottom:4px;}
.card-meta {color:#667085;font-size:.82rem;margin-bottom:10px;}
.total-box {background:#f7f9fc;border:1px solid #e5e9f0;border-radius:10px;padding:10px 14px;}
.balance-ok {color:#137a4b;font-weight:750;}
.balance-warn {color:#b54708;font-weight:750;}
.line-total {padding-top:30px;text-align:right;font-weight:750;font-size:1.02rem;}
.line-total.zero {color:#b42318;}
.chips {color:#475467;font-size:.8rem;margin:4px 0 2px;line-height:1.5;}
.chips .empty {color:#98a2b3;font-style:italic;}
.chips b {color:#1d2939;}
.flag {font-size:.78rem;color:#b54708;margin-top:4px;font-weight:600;}
.sticky-summary {position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #dfe4ea;
                 padding:12px 4%;z-index:999;box-shadow:0 -4px 14px rgba(16,24,40,.06);}
.sticky-summary .wrap {max-width:1450px;margin:0 auto;display:flex;align-items:center;gap:28px;flex-wrap:wrap;}
.sticky-summary .item {font-size:.9rem;color:#475467;}
.sticky-summary .item b {color:#101828;font-size:1.05rem;}
.sticky-summary .status-ok {background:#ecfdf3;color:#137a4b;padding:6px 14px;border-radius:20px;font-weight:700;}
.sticky-summary .status-warn {background:#fef0c7;color:#b54708;padding:6px 14px;border-radius:20px;font-weight:700;}
.step {font-size:.85rem;color:#98a2b3;}
.step.done {color:#137a4b;font-weight:700;}
.step.active {color:#315b9d;font-weight:800;}
div[data-testid="stExpander"] {border-radius:10px;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ helpers
def empty_line():
    line = {c: "" if c in TEXT_COLS else 0.0 for c in LINE_COLS}
    return line

def new_id():
    st.session_state._next_id += 1
    return st.session_state._next_id

def ensure_ids(records):
    """Give every line a stable id so widget keys don't shift on delete/reorder."""
    for line in records:
        if "_lid" not in line:
            line["_lid"] = new_id()
    return records

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
    return ensure_ids(df.to_dict("records"))

def records_to_df(records):
    if not records:
        return pd.DataFrame(columns=LINE_COLS)
    return clean_df(pd.DataFrame(records))

def line_total(line):
    return sum(float(line.get(m, 0) or 0) for m in MONTHS)

def money(v):
    return f"S/ {v:,.2f}"

def money_short(v):
    v = float(v or 0)
    if abs(v) >= 1000:
        return f"{v/1000:,.0f}k".replace(",", " ")
    return f"{v:,.0f}"

def month_chips(line):
    parts = [f"{m} <b>{money_short(line.get(m,0))}</b>" for m in MONTHS if float(line.get(m,0) or 0)]
    if not parts:
        return "<span class='empty'>Sin distribución mensual — abre el editor para cargar montos</span>"
    return " · ".join(parts)

def line_flag(line):
    total = line_total(line)
    has_text = any(str(line.get(c,"")).strip() for c in TEXT_COLS)
    if total > 0 and not str(line.get("Partida","")).strip():
        return "⚠ Falta la partida para esta línea con monto"
    if has_text and total == 0:
        return "⚠ Línea con datos pero sin monto mensual"
    return ""

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
    end = next_header if next_header is not None else min(len(raw), header_row + 25)
    part = raw.iloc[header_row + 1:end].copy()
    part.columns = raw.iloc[header_row].tolist()
    part = part.rename(columns=normalize_headers(part.columns))
    keep = [c for c in LINE_COLS if c in part.columns]
    if not keep:
        return pd.DataFrame(columns=LINE_COLS)
    part = part[keep].copy()

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

# ------------------------------------------------------------------ state
def init_state():
    st.session_state.setdefault("_next_id", 0)
    if "tipo" not in st.session_state:
        st.session_state.tipo = "Traslado"
    if "origen" not in st.session_state:
        st.session_state.origen = ensure_ids([
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.016",
             **{m:(100000 if m=="Jun" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.033",
             **{m:(75000 if m=="Set" else 0) for m in MONTHS}},
        ])
    if "destino" not in st.session_state:
        st.session_state.destino = ensure_ids([
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.015",
             **{m:(40000 if m=="Set" else 60000 if m=="Oct" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.034",
             **{m:(85000 if m=="Nov" else 0) for m in MONTHS}},
        ])
    st.session_state.setdefault("single", [])
    st.session_state.setdefault("justificacion", "")
    st.session_state.setdefault("solicitante", "")
    st.session_state.setdefault("cargo", "")
    st.session_state.setdefault("unidad", "")

# ------------------------------------------------------------------ seeded widgets
# Pattern: seed session_state once from the data dict, let the widget own it,
# then read back. Avoids the value=+key= collision and positional-key bugs.
def seeded_text(label, lid, field, line, **kw):
    k = f"L{lid}::{field}"
    if k not in st.session_state:
        st.session_state[k] = str(line.get(field, ""))
    st.text_input(label, key=k, **kw)
    line[field] = st.session_state[k]

def seeded_num(label, lid, field, line, **kw):
    k = f"L{lid}::{field}"
    if k not in st.session_state:
        st.session_state[k] = float(line.get(field, 0) or 0)
    st.number_input(label, key=k, **kw)
    line[field] = st.session_state[k]

def month_editor(lid, line):
    with st.expander("Editar distribución mensual", expanded=False):
        mcols = st.columns(4)
        for j, m in enumerate(MONTHS):
            with mcols[j % 4]:
                seeded_num(m, lid, m, line, min_value=0.0, step=100.0)

# ------------------------------------------------------------------ rendering
def render_line_list(side):
    records = ensure_ids(st.session_state[side])
    label = "Origen" if side == "origen" else "Destino"

    if not records:
        st.markdown('<div class="helper">Aún no hay líneas. Agrega la primera con el botón de abajo.</div>',
                    unsafe_allow_html=True)

    delete_id = None
    for line in records:
        lid = line["_lid"]
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.3, 1.1, 2.0, .9])
            with c1:
                seeded_text("Centro de costo", lid, "Centro de costo", line, placeholder="03.08.01.01.01")
            with c2:
                seeded_text("Dimensión", lid, "Dimensión", line, placeholder="02.01")
            with c3:
                seeded_text("Partida", lid, "Partida", line, placeholder="94.3.1.1.016")
            with c4:
                total = line_total(line)
                zero = "zero" if total == 0 else ""
                st.markdown(f"<div class='line-total {zero}'>{money(total)}</div>", unsafe_allow_html=True)

            st.markdown(f"<div class='chips'>{month_chips(line)}</div>", unsafe_allow_html=True)
            flag = line_flag(line)
            if flag:
                st.markdown(f"<div class='flag'>{flag}</div>", unsafe_allow_html=True)

            e_col, d_col, x_col = st.columns([2, 1, 1])
            with e_col:
                month_editor(lid, line)
            with d_col:
                if st.button("Duplicar", key=f"{side}_dup_{lid}", use_container_width=True):
                    copy = deepcopy(line)
                    copy["_lid"] = new_id()
                    records.insert(records.index(line) + 1, copy)
                    st.rerun()
            with x_col:
                if st.button("Eliminar", key=f"{side}_del_{lid}", use_container_width=True):
                    delete_id = lid

    if delete_id is not None:
        st.session_state[side] = [l for l in records if l["_lid"] != delete_id]
        st.rerun()

    if st.button(f"+ Agregar línea a {label}", key=f"{side}_add", use_container_width=True):
        nl = empty_line(); nl["_lid"] = new_id()
        records.append(nl)
        st.rerun()

    st.session_state[side] = records

def render_single():
    records = ensure_ids(st.session_state.single)

    if not records:
        st.markdown('<div class="helper">Aún no hay líneas. Agrega la primera con el botón de abajo.</div>',
                    unsafe_allow_html=True)

    delete_id = None
    for line in records:
        lid = line["_lid"]
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.4, 1.1, 2.1, .9])
            with c1:
                seeded_text("Centro de costo", lid, "Centro de costo", line, placeholder="03.08.01.01.01")
            with c2:
                seeded_text("Dimensión", lid, "Dimensión", line, placeholder="02.01")
            with c3:
                seeded_text("Partida", lid, "Partida", line, placeholder="94.3.1.1.016")
            with c4:
                total = line_total(line)
                zero = "zero" if total == 0 else ""
                st.markdown(f"<div class='line-total {zero}'>{money(total)}</div>", unsafe_allow_html=True)

            st.markdown(f"<div class='chips'>{month_chips(line)}</div>", unsafe_allow_html=True)
            flag = line_flag(line)
            if flag:
                st.markdown(f"<div class='flag'>{flag}</div>", unsafe_allow_html=True)

            e_col, d_col, x_col = st.columns([2, 1, 1])
            with e_col:
                month_editor(lid, line)
            with d_col:
                if st.button("Duplicar", key=f"single_dup_{lid}", use_container_width=True):
                    copy = deepcopy(line)
                    copy["_lid"] = new_id()
                    records.insert(records.index(line) + 1, copy)
                    st.rerun()
            with x_col:
                if st.button("Eliminar", key=f"single_del_{lid}", use_container_width=True):
                    delete_id = lid

    if delete_id is not None:
        st.session_state.single = [l for l in records if l["_lid"] != delete_id]
        st.rerun()

    if st.button("+ Agregar línea", key="single_add", use_container_width=True):
        nl = empty_line(); nl["_lid"] = new_id()
        records.append(nl)
        st.rerun()

    st.session_state.single = records

def total_records(records):
    return sum(line_total(x) for x in records)

# ------------------------------------------------------------------ app
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
            if data["tipo"] == "Traslado":
                st.session_state.origen = df_to_records(data["origen"])
                st.session_state.destino = df_to_records(data["destino"])
                st.session_state.single = []
            else:
                # Amp/Red: la única tabla del formato llega en "origen".
                st.session_state.single = df_to_records(data["origen"])
                st.session_state.origen = []
                st.session_state.destino = []
            st.session_state.solicitante = data["meta"].get("solicitante", "")
            st.session_state.cargo = data["meta"].get("cargo", "")
            st.session_state.unidad = data["meta"].get("unidad", "")
            st.session_state.import_message = f"Importado correctamente desde «{sheet}» ({data['tipo']})."
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo importar el archivo: {e}")
    if st.session_state.get("import_message"):
        st.success(st.session_state.import_message)
    st.divider()
    st.caption("El Excel se usa como fuente de datos; la distribución mensual se transforma a una interfaz web.")
    if st.button("Limpiar formulario", use_container_width=True):
        for k in ["origen", "destino", "single"]:
            st.session_state[k] = []
        st.session_state.justificacion = ""
        st.rerun()

# Progress — refleja estado real
tipo = st.session_state.tipo
has_movement = (total_records(st.session_state.origen) > 0 or total_records(st.session_state.single) > 0)
has_just = bool(st.session_state.justificacion.strip())
done = [True, has_movement, has_just, has_movement and has_just]
p = st.columns(4)
for i, txt in enumerate(["1 · Tipo", "2 · Movimiento", "3 · Justificación", "4 · Revisar"]):
    cls = "done" if done[i] else ("active" if (i == 0 or done[i-1]) else "")
    p[i].markdown(f"<div class='step {cls}'>{'✓ ' if done[i] else ''}{txt}</div>", unsafe_allow_html=True)

st.subheader("1. Tipo de solicitud")
tipo = st.radio(
    "Selecciona el movimiento", ["Traslado", "Ampliación", "Reducción"],
    index=["Traslado", "Ampliación", "Reducción"].index(st.session_state.tipo),
    horizontal=True, label_visibility="collapsed"
)
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
    st.markdown('<div class="helper">En un traslado, el total del origen debe coincidir con el total del destino. '
                'Puedes agregar, duplicar o eliminar tantas líneas como necesites.</div>', unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown('<div class="section-kicker">ORIGEN</div>', unsafe_allow_html=True)
        render_line_list("origen")
        st.markdown(f'<div class="total-box">Total origen: <b>{money(total_records(st.session_state.origen))}</b></div>',
                    unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-kicker">DESTINO</div>', unsafe_allow_html=True)
        render_line_list("destino")
        st.markdown(f'<div class="total-box">Total destino: <b>{money(total_records(st.session_state.destino))}</b></div>',
                    unsafe_allow_html=True)
else:
    label = "Destino" if tipo == "Ampliación" else "Presupuesto a reducir"
    st.markdown('<div class="helper">Agrega las líneas presupuestales que correspondan. '
                'La distribución mensual se edita solo cuando la necesites.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-kicker">{label.upper()}</div>', unsafe_allow_html=True)
    render_single()

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
    balanced = abs(o - d) < .01
    if balanced and o > 0:
        st.success(f"✓ Solicitud balanceada por {money(o)}")
    elif not balanced:
        st.warning(f"⚠ El traslado no está balanceado. Diferencia: {money(abs(o - d))}")
    else:
        st.info("Agrega líneas de origen y destino para continuar.")
else:
    total_single = total_records(st.session_state.single)
    if total_single > 0:
        st.success(f"✓ {tipo}: {money(total_single)}")
    else:
        st.info("Agrega al menos una línea con monto para continuar.")

c1, c2 = st.columns(2)
with c1:
    st.button("Guardar borrador", use_container_width=True)
with c2:
    can_submit = (balanced and o > 0) if tipo == "Traslado" else (total_records(st.session_state.single) > 0)
    st.button("Enviar para aprobación", type="primary", use_container_width=True, disabled=not can_submit)

# ------------------------------------------------------------------ sticky balance bar
if tipo == "Traslado":
    o, d = total_records(st.session_state.origen), total_records(st.session_state.destino)
    balanced = abs(o - d) < .01
    status = (f"<span class='status-ok'>✓ Balanceado</span>" if balanced and o > 0
              else f"<span class='status-warn'>⚠ Diferencia {money(abs(o - d))}</span>")
    st.markdown(f"""
    <div class="sticky-summary"><div class="wrap">
        <div class="item">Origen <b>{money(o)}</b></div>
        <div class="item">Destino <b>{money(d)}</b></div>
        <div class="item">{status}</div>
    </div></div>
    """, unsafe_allow_html=True)
else:
    total_single = total_records(st.session_state.single)
    st.markdown(f"""
    <div class="sticky-summary"><div class="wrap">
        <div class="item">{tipo} — total <b>{money(total_single)}</b></div>
    </div></div>
    """, unsafe_allow_html=True)
