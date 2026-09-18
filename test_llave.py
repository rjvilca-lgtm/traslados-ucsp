"""
Prueba del fix de llave (CC, cuenta, dimensión) contra el VIGENTE COMPLETO de TI.
  streamlit run test_llave.py
Responde: ¿hay cuentas con >1 dimensión? ¿la columna DIMENSION viene punteada y casa
con la tabla de equivalencias? ¿algún dato raro? No toca la app ni escribe nada.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import dim_equiv as de

st.title("Prueba de llave — vigente completo")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

try:
    sa = dict(st.secrets["gcp_service_account"])
    p = st.secrets["presupuesto"]
    creds = Credentials.from_service_account_info(sa, scopes=SCOPES)
    sh = gspread.authorize(creds).open_by_key(p["vigente_spreadsheet_id"])
    ws = sh.worksheet(p["vigente_worksheet"])
    rows = ws.get_all_records()
    st.success(f"Vigente leído: {len(rows)} filas.")
except Exception as e:
    st.error(f"No se pudo leer el vigente: {e}")
    st.stop()

# 1) ¿La misma (CC, cuenta) aparece con más de una dimensión?  -> justifica la llave de 3
from collections import defaultdict
por_par = defaultdict(set)
por_terna = set()
sin_dim = 0
for r in rows:
    cc = str(r.get("CENTRO_COSTO", "")).strip()
    cta = str(r.get("CUENTA_CONTABLE", "")).strip()
    dim = str(r.get("DIMENSION", "")).strip()
    if not cc or not cta:
        continue
    if not dim:
        sin_dim += 1
    por_par[(cc, cta)].add(dim)
    por_terna.add((cc, cta, dim))

multi = {k: v for k, v in por_par.items() if len(v) > 1}
st.subheader("1 · ¿Cuentas con más de una dimensión?")
st.write(f"Pares (CC, cuenta) únicos: **{len(por_par)}** · Ternas (CC, cuenta, dim) únicas: **{len(por_terna)}**")
if multi:
    st.success(f"Sí: **{len(multi)}** par(es) (CC, cuenta) tienen 2+ dimensiones. "
               "Confirma que la llave de 3 campos era necesaria.")
    ej = list(multi.items())[:8]
    st.table([{"Centro de costo": k[0], "Cuenta": k[1], "Dimensiones": ", ".join(sorted(v))}
              for k, v in ej])
else:
    st.warning("No se encontró ningún (CC, cuenta) con dos dimensiones en el vigente completo. "
               "Con estos datos, (CC, cuenta) habría bastado — la llave de 3 no estorba, "
               "pero conviene que confirmes con TI si el caso existe en la práctica.")

# 2) ¿La columna DIMENSION viene punteada y casa con la tabla de equivalencias?
st.subheader("2 · ¿DIMENSION es punteada y está en la tabla de equivalencias?")
dims = sorted({str(r.get("DIMENSION", "")).strip() for r in rows if str(r.get("DIMENSION", "")).strip()})
desconocidas = [d for d in dims if not de.es_punteada_valida(d)]
st.write(f"Dimensiones distintas en el vigente: **{len(dims)}**")
if desconocidas:
    st.error(f"Estas dimensiones del vigente NO están en la tabla de equivalencias: {desconocidas}. "
             "Habría que agregarlas a dim_equiv.py (o revisar si el formato no es el esperado).")
else:
    st.success("Todas las dimensiones del vigente existen en la tabla de equivalencias. ✓")

# 3) Coherencia PROYECTO (numérica) vs DIMENSION (punteada) según la tabla
st.subheader("3 · ¿PROYECTO (numérica) concuerda con DIMENSION (punteada)?")
incoh = []
for r in rows:
    dim = str(r.get("DIMENSION", "")).strip()
    proj = str(r.get("PROYECTO", "")).strip()
    if not dim or not proj:
        continue
    esperado = de.punteada_a_numerica(dim)
    if esperado is not None and str(proj).replace(".0", "") != esperado:
        incoh.append((dim, proj, esperado))
if incoh:
    st.warning(f"{len(incoh)} fila(s) donde PROYECTO no coincide con la traducción de DIMENSION. "
               "Ejemplos (DIMENSION, PROYECTO_en_hoja, PROYECTO_esperado):")
    st.table([{"DIMENSION": a, "PROYECTO (hoja)": b, "esperado": c} for a, b, c in incoh[:10]])
else:
    st.success("PROYECTO y DIMENSION concuerdan en todas las filas. La traducción es sólida. ✓")

if sin_dim:
    st.warning(f"Aviso: {sin_dim} fila(s) sin DIMENSION. Revisa si son válidas.")

st.divider()
st.caption("Si 1 muestra cuentas con múltiples dimensiones y 2/3 salen en verde, "
           "la llave está validada contra datos reales y podemos generar el CSV (Fase 2b).")
