"""
Inspección de la pestaña Ppto_2026_original (Adj 1) del store.
  streamlit run test_adj1.py
Reporta columnas, formato de DIMENSION, y cruce de llave con el catálogo/equivalencias.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import dim_equiv as de

st.title("Inspección — Ppto_2026_original (Adj 1)")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
PESTANA = st.secrets.get("adj1", {}).get("worksheet", "Ppto_2026_original")

try:
    sa = dict(st.secrets["gcp_service_account"])
    sid = st.secrets["sheets"]["spreadsheet_id"]  # mismo store
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    sh = gspread.authorize(creds).open_by_key(sid)
    ws = sh.worksheet(PESTANA)
    rows = ws.get_all_records()
    st.success(f"Pestaña «{PESTANA}» leída: {len(rows)} filas.")
except Exception as e:
    st.error(f"No se pudo leer «{PESTANA}» del store: {e}")
    st.stop()

if not rows:
    st.warning("La pestaña está vacía.")
    st.stop()

header = list(rows[0].keys())
st.subheader("1 · Columnas")
st.write(header)

esperadas = ["PRESUPUESTO", "LINEA", "CENTRO_COSTO", "CUENTA_CONTABLE", "DIMENSION", "TIPO"]
faltan = [c for c in esperadas if c not in header]
if faltan:
    st.error(f"Faltan columnas esperadas del formato Adj 1: {faltan}")
else:
    st.success("Columnas fijas del Adj 1 presentes. ✓")

# meses: ¿fechas (31/01/2026...) o PPTO_1..12?
meses_fecha = [c for c in header if "/2026" in str(c)]
meses_ppto = [c for c in header if str(c).upper().startswith("PPTO_")]
st.write(f"Columnas de mes tipo fecha: **{len(meses_fecha)}** · tipo PPTO_n: **{len(meses_ppto)}**")
st.caption(f"Ejemplos de mes: {(meses_fecha or meses_ppto)[:4]}")

st.subheader("2 · Formato de DIMENSION (¿numérica o punteada?)")
dims = sorted({str(r.get("DIMENSION", "")).strip() for r in rows if str(r.get("DIMENSION", "")).strip()})
st.write(f"Valores distintos: {dims[:30]}")
# ¿parecen numéricos (22, 30) o punteados (01.03)?
tiene_punto = any("." in d for d in dims)
if tiene_punto:
    st.info("DIMENSION parece **punteada** (tiene puntos). Se usará normalizada tal cual.")
    desconocidas = [d for d in dims if not de.es_punteada_valida(d)]
else:
    st.info("DIMENSION parece **numérica** (enteros). Se traducirá a punteada al leer.")
    desconocidas = [d for d in dims if de.numerica_a_punteada(d) is None]
if desconocidas:
    st.error(f"Dimensiones sin equivalencia en dim_equiv: {desconocidas}")
else:
    st.success("Todas las dimensiones tienen equivalencia en la tabla. ✓")

st.subheader("3 · Llave (CC, cuenta, dim) — ¿única?")
from collections import Counter
def norm_dim(v):
    v = str(v).strip()
    if "." in v:
        return de.normaliza_punteada(v)
    return de.numerica_a_punteada(v) or v
ternas = Counter((str(r.get("CENTRO_COSTO","")).strip(),
                  str(r.get("CUENTA_CONTABLE","")).strip(),
                  norm_dim(r.get("DIMENSION",""))) for r in rows)
dups = [k for k, n in ternas.items() if n > 1]
st.write(f"Ternas únicas: **{len(ternas)}** de **{len(rows)}** filas.")
if dups:
    st.warning(f"Hay {len(dups)} terna(s) repetida(s). Ejemplo: {dups[:3]}")
else:
    st.success("La llave (CC, cuenta, dim) es única en Adj 1. ✓")

st.divider()
st.caption("Con columnas OK, dimensión mapeada y llave única, puedo construir el lector de Adj 1.")
