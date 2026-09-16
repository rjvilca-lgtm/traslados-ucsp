"""
Prueba de conexión a Google Sheets. Corre esto ANTES de migrar budget_core.
  streamlit run test_sheets.py
Verifica: credenciales válidas + hoja compartida con el robot + lectura/escritura.
"""
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.title("Prueba de conexión — Google Sheets")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# 1) ¿Están los secretos?
try:
    sa_info = dict(st.secrets["gcp_service_account"])
    spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    st.success("1/4 · Secretos [gcp_service_account] y [sheets] encontrados.")
    st.caption(f"Robot: {sa_info.get('client_email','?')}")
except Exception as e:
    st.error(f"1/4 · Falta o está mal el bloque de secretos: {e}")
    st.stop()

# 2) ¿Las credenciales cargan? (detecta private_key mal pegada)
try:
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    st.success("2/4 · Credenciales válidas (private_key OK).")
except Exception as e:
    st.error(f"2/4 · Las credenciales no cargan — revisa el private_key y sus \\n. Detalle: {e}")
    st.stop()

# 3) ¿Puede abrir la hoja? (detecta hoja no compartida con el robot)
try:
    sh = client.open_by_key(spreadsheet_id)
    st.success(f"3/4 · Hoja abierta: «{sh.title}».")
except gspread.exceptions.APIError as e:
    st.error("3/4 · No puede abrir la hoja. ¿La compartiste como Editor con el correo del robot? "
             f"Detalle: {e}")
    st.stop()
except Exception as e:
    st.error(f"3/4 · Error abriendo la hoja. ¿El spreadsheet_id es correcto? Detalle: {e}")
    st.stop()

# 4) ¿Puede escribir y leer?
try:
    ws = sh.sheet1
    ws.update_acell("A1", "conexión OK")
    val = ws.acell("A1").value
    st.success(f"4/4 · Escritura y lectura OK. A1 = «{val}».")
    st.balloons()
    st.info("Todo listo. Puedes borrar este archivo y seguimos con la migración de budget_core.")
except Exception as e:
    st.error(f"4/4 · Abre la hoja pero no puede escribir. ¿El rol es Editor (no Lector)? Detalle: {e}")
