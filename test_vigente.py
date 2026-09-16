"""
Prueba de LECTURA de la hoja de presupuesto vigente (Adj 2) de TI.
  streamlit run test_vigente.py
Confirma que el robot puede abrirla y muestra sus columnas, sin tocar la app.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("Prueba de lectura — Presupuesto vigente (Adj 2)")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

try:
    sa_info = dict(st.secrets["gcp_service_account"])
    sid = st.secrets["presupuesto"]["vigente_spreadsheet_id"]
    wsname = st.secrets["presupuesto"]["vigente_worksheet"]
    st.success("1/3 · Secretos [presupuesto] encontrados.")
    st.caption(f"Robot: {sa_info.get('client_email','?')}")
except Exception as e:
    st.error(f"1/3 · Falta el bloque [presupuesto] o [gcp_service_account]: {e}")
    st.stop()

try:
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open_by_key(sid)
    st.success(f"2/3 · Hoja abierta por el robot: «{sh.title}».")
except gspread.exceptions.APIError as e:
    st.error("2/3 · El robot NO puede abrir la hoja. El propietario debe compartirla "
             f"(rol Lector) con el correo del robot de arriba. Detalle: {e}")
    st.stop()
except Exception as e:
    st.error(f"2/3 · Error abriendo la hoja. ¿El vigente_spreadsheet_id es correcto? {e}")
    st.stop()

try:
    ws = sh.worksheet(wsname)
except Exception as e:
    tabs = [w.title for w in sh.worksheets()]
    st.error(f"3/3 · No existe la pestaña «{wsname}». Pestañas disponibles: {tabs}. "
             f"Corrige vigente_worksheet en los secretos.")
    st.stop()

header = ws.row_values(1)
st.success(f"3/3 · Pestaña «{wsname}» leída. {len(header)} columnas.")
st.write("**Columnas (fila 1):**")
st.write(header)
st.caption(f"Filas totales (incl. cabecera): {ws.row_count} declaradas / "
           f"{len(ws.col_values(1))} con datos en columna A.")

need = ["CENTRO_COSTO", "CUENTA_CONTABLE"]
falt = [c for c in need if c not in header]
if falt:
    st.warning(f"Faltan columnas clave esperadas: {falt}. Revisa que sea la hoja/pestaña correcta.")
else:
    st.info("Columnas clave (CENTRO_COSTO, CUENTA_CONTABLE) presentes. Listo para Fase 1.")
