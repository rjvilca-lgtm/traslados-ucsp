import io
import datetime as dt
import pandas as pd
import streamlit as st

import budget_core as core
import budget_data as bdata
from budget_core import MONTHS, TEXT_COLS, LINE_COLS, APPROVER_EMAIL, DOMAIN

st.set_page_config(page_title="Solicitud presupuestal", page_icon="📊",
                   layout="wide", initial_sidebar_state="collapsed")

# --- Store persistente en Google Sheets (auth cacheada; el core recibe el worksheet)
@st.cache_resource
def _get_worksheet():
    return core.build_worksheet(dict(st.secrets["gcp_service_account"]),
                                st.secrets["sheets"]["spreadsheet_id"])

try:
    core.set_worksheet(_get_worksheet())
except Exception as e:
    st.error("No se pudo conectar al almacén (Google Sheets). Revisa los secretos "
             f"[gcp_service_account] y [sheets], y que la hoja esté compartida con el robot.\n\n{e}")
    st.stop()

# --- Presupuesto vigente (Adj 2) de TI, solo lectura, cacheado por sesión (Fase 1)
@st.cache_resource
def _get_vigente_ws():
    p = st.secrets["presupuesto"]
    return bdata.build_vigente_ws(dict(st.secrets["gcp_service_account"]),
                                  p["vigente_spreadsheet_id"], p["vigente_worksheet"])

vigente_ok = True
try:
    bdata.set_vigente_ws(_get_vigente_ws())
except Exception as e:
    vigente_ok = False
    st.warning("No se pudo leer el presupuesto vigente (Adj 2). La captura funciona, pero la "
               f"validación de saldo no estará disponible hasta resolverlo.\n\n{e}")

st.markdown("""
<style>
.block-container {max-width: 1500px; padding-top: 1.2rem; padding-bottom: 3rem;}
.section-kicker {font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#315b9d;margin:.4rem 0 .35rem;}
.helper {background:#eef4ff;border:1px solid #dbe7ff;border-radius:10px;padding:11px 15px;color:#0759a6;margin:0 0 12px 0;font-size:.88rem;}
.chip {display:inline-block;background:#eef4ff;color:#315b9d;border-radius:14px;padding:3px 11px;font-size:.78rem;margin:2px 4px 2px 0;font-weight:600;}
.badge {display:inline-block;border-radius:14px;padding:3px 11px;font-size:.78rem;font-weight:700;}
.b-pend {background:#fef0c7;color:#b54708;} .b-ok {background:#ecfdf3;color:#137a4b;} .b-rej {background:#fee4e2;color:#b42318;}
div[data-testid="stDataFrame"] {border:1px solid #e4e7ec;border-radius:10px;overflow:hidden;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------- data helpers
def empty_df(n=1):
    return pd.DataFrame([{**{c:"" for c in TEXT_COLS}, **{m:0.0 for m in MONTHS}} for _ in range(n)],
                        columns=LINE_COLS)

def coerce(df):
    if df is None or len(df)==0: return empty_df(0)
    out=df.copy()
    for c in LINE_COLS:
        if c not in out.columns: out[c]="" if c in TEXT_COLS else 0.0
    for c in TEXT_COLS: out[c]=out[c].fillna("").astype(str)
    for m in MONTHS: out[m]=pd.to_numeric(out[m],errors="coerce").fillna(0.0)
    return out[LINE_COLS].reset_index(drop=True)

def drop_empty(df):
    df=coerce(df)
    if len(df)==0: return df
    ht=df[TEXT_COLS].astype(str).agg("".join,axis=1).str.strip()!=""
    ha=df[MONTHS].sum(axis=1)!=0
    return df[ht|ha].reset_index(drop=True)

def grid_total(df): return float(coerce(df)[MONTHS].sum().sum())
def money(v): return f"S/ {float(v or 0):,.2f}"
def ccs_of(df): return list(drop_empty(df)["Centro de costo"].astype(str))


# ------------------------------------------------------------- auth
def auth_configured():
    try: return "auth" in st.secrets
    except Exception: return False

def native_user():
    try:
        if getattr(st, "user", None) is not None and st.user.is_logged_in:
            return {"email": st.user.email, "name": getattr(st.user, "name", None) or st.user.email}
    except Exception:
        return None
    return None

def current_identity():
    nu = native_user()
    if nu: return nu
    return st.session_state.get("dev_user")

def _find_logo():
    from pathlib import Path
    for p in ["assets/logo.png", "assets/logo.jpg", "assets/logo.jpeg", "logo.png", "logo.jpg"]:
        fp = Path(__file__).resolve().parent / p
        if fp.exists():
            return str(fp)
    return None

def login_screen():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"], .stApp { background:#003a78; }
    [data-testid="stHeader"] { background:transparent; }
    .block-container { padding-top:12vh; }
    /* tarjeta blanca */
    .st-key-logincard {
        background:#ffffff; border-radius:16px; padding:44px 52px;
        box-shadow:0 20px 55px rgba(0,0,0,.28);
    }
    .login-title { text-align:center; font-family:Georgia,'Times New Roman',serif;
        font-weight:400; font-size:2.3rem; color:#2b2b2b; margin:0 0 30px; letter-spacing:.3px; }
    .login-logo-fallback { font-weight:800; color:#7a1f2b; font-size:1.15rem; line-height:1.15; }
    .login-logo-fallback span { color:#1f2937; }
    /* botón como enlace azul dentro de la tarjeta */
    .st-key-logincard .stButton>button {
        background:#ffffff; color:#0a3d7c; border:none; box-shadow:none;
        font-weight:600; font-size:1.06rem; text-align:left; padding:0; min-height:0;
    }
    .st-key-logincard .stButton>button:hover { color:#062a5a; background:#ffffff; }
    .st-key-logincard .stButton>button:focus { box-shadow:none; }
    </style>
    """, unsafe_allow_html=True)

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        with st.container(key="logincard", border=False):
            st.markdown('<div class="login-title">Accede a tu cuenta</div>', unsafe_allow_html=True)
            lc, rc = st.columns([5, 6], vertical_alignment="center")
            with lc:
                logo = _find_logo()
                if logo:
                    st.image(logo, width="stretch")
                else:
                    st.markdown('<div class="login-logo-fallback">Universidad Católica<br>'
                                '<span>San Pablo</span></div>', unsafe_allow_html=True)
            with rc:
                if auth_configured():
                    if st.button("Ingresa con tu\nSan Pablo Mail　›", width="stretch"):
                        st.login()
                else:
                    sel = st.selectbox("Usuario de prueba", list(core.MOCK_USERS.keys()),
                                       label_visibility="collapsed")
                    if st.button("Ingresa (modo dev)　›", width="stretch"):
                        st.session_state.dev_user = {"email": sel, "name": core.MOCK_USERS[sel]["name"]}
                        st.rerun()

# ------------------------------------------------------------- grid
def column_config():
    cfg = {"Centro de costo": st.column_config.TextColumn("Centro de costo", width="medium"),
           "Dimensión": st.column_config.TextColumn("Dim.", width="small"),
           "Partida": st.column_config.TextColumn("Partida", width="medium")}
    for m in MONTHS:
        cfg[m]=st.column_config.NumberColumn(m, format="%d", min_value=0.0, step=100.0, width="small")
    return cfg

def edit_grid(seed_key, mirror_key):
    seed = coerce(st.session_state[seed_key])
    edited = st.data_editor(seed, key=f"editor_{seed_key}", num_rows="dynamic",
                            width="stretch", hide_index=True,
                            column_config=column_config(), column_order=LINE_COLS)
    current = drop_empty(edited)
    st.session_state[mirror_key] = current
    return grid_total(current)

# ------------------------------------------------------------- state
def init_state():
    st.session_state.setdefault("tipo", "Traslado")
    if "origen_seed" not in st.session_state:
        st.session_state.origen_seed = coerce(pd.DataFrame([
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.016",
             **{m:(100000 if m=="Jun" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.033",
             **{m:(75000 if m=="Set" else 0) for m in MONTHS}}]))
    if "destino_seed" not in st.session_state:
        st.session_state.destino_seed = coerce(pd.DataFrame([
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.3.1.1.015",
             **{m:(40000 if m=="Set" else 60000 if m=="Oct" else 0) for m in MONTHS}},
            {"Centro de costo":"03.08.01.06.02","Dimensión":"02.01","Partida":"94.5.1.1.034",
             **{m:(75000 if m=="Nov" else 0) for m in MONTHS}}]))
    st.session_state.setdefault("single_seed", empty_df(1))
    for k in ["_origen_current","_destino_current","_single_current"]:
        st.session_state.setdefault(k, empty_df(0))
    st.session_state.setdefault("justificacion","")

# ------------------------------------------------------------- badges / views
def status_badge(status):
    cls = {core.STATUS_PENDING:"b-pend", core.STATUS_APPROVED:"b-ok",
           core.STATUS_AUTO:"b-ok", core.STATUS_REJECTED:"b-rej"}.get(status,"b-pend")
    return f'<span class="badge {cls}">{status}</span>'

def render_request_detail(req):
    st.markdown(f"**{req['tipo']}** · {money(req['monto'])} · {status_badge(req['status'])}", unsafe_allow_html=True)
    st.caption(f"Solicitante: {req['created_by_name']} ({req['created_by']}) · "
               f"Unidad: {req['unidad'] or '—'} · {req['periodo']} · {req['created_at']}")
    mov = req.get("movimiento", {})
    for side in ["origen","destino","single"]:
        rows = mov.get(side)
        if rows:
            st.markdown(f'<div class="section-kicker">{side}</div>', unsafe_allow_html=True)
            st.dataframe(coerce(pd.DataFrame(rows)), hide_index=True, width="stretch")
    if req.get("decision_note"):
        st.info(f"Nota de decisión: {req['decision_note']}")

def decision_panel(user, req):
    render_request_detail(req)
    if req["status"] != core.STATUS_PENDING:
        st.warning("Esta solicitud ya fue decidida.")
        return
    note = st.text_area("Nota (opcional)", key=f"note_{req['id']}")
    c1, c2 = st.columns(2)
    decided = None
    with c1:
        if st.button("✓ Aprobar", type="primary", width="stretch", key=f"ap_{req['id']}"):
            decided = core.STATUS_APPROVED
    with c2:
        if st.button("✗ Rechazar", width="stretch", key=f"rj_{req['id']}"):
            decided = core.STATUS_REJECTED
    if decided:
        core.update_request(req["id"], status=decided, approver=user["email"],
                            decided_at=dt.datetime.now().isoformat(timespec="seconds"),
                            decision_note=note or "")
        msg = "aprobada" if decided == core.STATUS_APPROVED else "rechazada"
        st.success(f"Solicitud {msg}. El solicitante verá el nuevo estado en «Mis solicitudes».")
        st.rerun()

# ------------------------------------------------------------- app
init_state()
identity = current_identity()

if not identity:
    login_screen(); st.stop()

# dominio institucional
if not identity["email"].lower().endswith("@" + DOMAIN):
    st.error(f"Acceso restringido a cuentas @{DOMAIN}.")
    if st.button("Cerrar sesión"):
        st.session_state.pop("dev_user", None)
        try: st.logout()
        except Exception: pass
        st.rerun()
    st.stop()

user = core.get_user(identity["email"])
if user is None:
    st.error(f"Tu cuenta ({identity['email']}) no tiene permisos asignados. Contacta a {APPROVER_EMAIL}.")
    if st.button("Cerrar sesión"):
        st.session_state.pop("dev_user", None)
        try: st.logout()
        except Exception: pass
        st.rerun()
    st.stop()

# barra superior
top1, top2 = st.columns([4,1])
with top1:
    st.title("Solicitud presupuestal")
with top2:
    st.markdown(f"<div style='text-align:right;padding-top:14px'>{user['name']}<br>"
                f"<span style='color:#667085;font-size:.8rem'>{user['email']}</span></div>", unsafe_allow_html=True)
    if st.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("dev_user", None)
        try: st.logout()
        except Exception: pass
        st.rerun()


# ---- diagnóstico Fase 1: consulta de saldo del vigente (solo lectura) ----
with st.sidebar:
    st.subheader("Consulta de saldo (vigente)")
    if not vigente_ok:
        st.caption("Presupuesto vigente no disponible.")
    else:
        cc_q = st.text_input("Centro de costo", key="q_cc", placeholder="03.01.01.01.01")
        cta_q = st.text_input("Cuenta contable", key="q_cta", placeholder="94.1.1.1.001")
        mes_q = st.selectbox("Acumulado hasta", MONTHS, index=0, key="q_mes")
        if cc_q and cta_q:
            if bdata.line_exists(cc_q, cta_q):
                idx = MONTHS.index(mes_q)
                saldo = bdata.cumulative_available(cc_q, cta_q, idx)
                st.metric(f"Saldo ERP acumulado a {mes_q}", f"S/ {saldo:,.2f}")
                st.caption("Solo vigente (PPTO−COMP−EJEC). No incluye movimientos de la app "
                           "aún no aplicados — eso llega en Fase 2.")
            else:
                st.warning("Esa combinación (CC, cuenta) no existe en el vigente.")

# ---- pestañas ----
tabs = ["Nueva solicitud", "Mis solicitudes"] + (["Aprobaciones"] if core.is_approver(user) else [])
t = st.tabs(tabs)

# ======================================================= NUEVA SOLICITUD
with t[0]:
    allowed = user.get("cost_centers", [])
    chips = " ".join(f'<span class="chip">{c}</span>' for c in allowed) if "*" not in allowed \
            else '<span class="chip">Todos los centros de costo</span>'
    st.markdown(f"Centros de costo habilitados: {chips}", unsafe_allow_html=True)

    st.subheader("1. Tipo de solicitud")
    tipo = st.radio("Movimiento", ["Traslado","Ampliación","Reducción"],
                    index=["Traslado","Ampliación","Reducción"].index(st.session_state.tipo),
                    horizontal=True, label_visibility="collapsed")
    st.session_state.tipo = tipo

    st.subheader("2. Datos generales")
    a,b,c = st.columns(3)
    with a: unidad = st.text_input("Unidad / departamento")
    with b: solicitante = st.text_input("Responsable", value=user["name"])
    with c: periodo = st.selectbox("Periodo", ["2026 · I Semestre","2026 · II Semestre"])

    st.subheader("3. Movimiento presupuestal")
    if tipo == "Traslado":
        st.markdown('<div class="helper">El total del origen debe igualar al destino. Edita como en Excel.</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">Origen</div>', unsafe_allow_html=True)
        o = edit_grid("origen_seed","_origen_current")
        st.markdown('<div class="section-kicker">Destino</div>', unsafe_allow_html=True)
        d = edit_grid("destino_seed","_destino_current")
        m1,m2,m3 = st.columns(3)
        m1.metric("Total origen", money(o)); m2.metric("Total destino", money(d))
        m3.metric("Estado", "✓ Balanceado" if abs(o-d)<.01 and o>0 else f"⚠ {money(abs(o-d))}")
        monto = o
        used_ccs = ccs_of(st.session_state._origen_current) + ccs_of(st.session_state._destino_current)
    else:
        label = "Destino (ampliación)" if tipo=="Ampliación" else "Presupuesto a reducir"
        st.markdown('<div class="helper">Edita como en Excel. Usa el + de la grilla para añadir filas.</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="section-kicker">{label}</div>', unsafe_allow_html=True)
        s = edit_grid("single_seed","_single_current")
        st.metric("Total solicitado", money(s))
        monto = s
        used_ccs = ccs_of(st.session_state._single_current)

    st.subheader("4. Justificación")
    st.session_state.justificacion = st.text_area("Motivo", value=st.session_state.justificacion, height=100,
        placeholder="Explica el motivo y, para ampliaciones con impacto en margen, el plan de compensación.",
        label_visibility="collapsed")

    # regla de aprobación (feedback anticipado)
    na = core.needs_approval(tipo, monto)
    if na:
        why = "las ampliaciones siempre requieren aprobación" if tipo=="Ampliación" \
              else f"el monto supera {money(core.TRASLADO_THRESHOLD)}"
        st.info(f"Esta solicitud **requerirá aprobación** de {APPROVER_EMAIL} ({why}).")
    else:
        st.info("Esta solicitud se **aprobará automáticamente** (no supera el umbral).")

    st.subheader("5. Enviar")
    # validaciones
    bad = core.disallowed_ccs(used_ccs, user)
    problems = []
    if bad:
        problems.append("Centros de costo fuera de tu permiso: " + ", ".join(bad))
    if tipo == "Traslado" and abs(o-d) >= .01:
        problems.append("El traslado no está balanceado.")
    if monto <= 0:
        problems.append("Agrega al menos una línea con monto.")

    for p in problems:
        st.warning("⚠ " + p)

    if st.button("Enviar solicitud", type="primary", width="stretch", disabled=bool(problems)):
        if tipo == "Traslado":
            mov = {"origen": drop_empty(st.session_state._origen_current).to_dict("records"),
                   "destino": drop_empty(st.session_state._destino_current).to_dict("records")}
        else:
            mov = {"single": drop_empty(st.session_state._single_current).to_dict("records")}
        req = core.new_request(user, tipo, periodo, unidad, solicitante, monto, mov)
        core.create_request(req)
        if req["needs_approval"]:
            st.success(f"Solicitud enviada a aprobación. {APPROVER_EMAIL} la revisará en la "
                       f"pestaña «Aprobaciones». Podrás seguir su estado en «Mis solicitudes».")
        else:
            st.success("Solicitud registrada y aprobada automáticamente.")
        st.caption(f"ID de solicitud: {req['id']}")

# ======================================================= MIS SOLICITUDES
with t[1]:
    mine = sorted(core.requests_for(user["email"]), key=lambda r: r["created_at"], reverse=True)
    if not mine:
        st.info("Aún no has enviado solicitudes.")
    else:
        df = pd.DataFrame([{"Fecha": r["created_at"], "Tipo": r["tipo"], "Monto": r["monto"],
                            "Estado": r["status"], "Aprobador": r.get("approver") or "—",
                            "ID": r["id"]} for r in mine])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"Monto": st.column_config.NumberColumn("Monto", format="S/ %.2f")})
        with st.expander("Ver detalle de una solicitud"):
            rid = st.selectbox("Solicitud", [r["id"] for r in mine],
                               format_func=lambda x: f"{x} · {core.get_request(x)['tipo']} · {money(core.get_request(x)['monto'])}")
            render_request_detail(core.get_request(rid))

# ======================================================= APROBACIONES
if core.is_approver(user):
    with t[2]:
        pend = sorted(core.pending_requests(), key=lambda r: r["created_at"])
        st.caption(f"{len(pend)} solicitud(es) pendiente(s)")
        if not pend:
            st.info("No hay solicitudes pendientes.")
        for req in pend:
            with st.container(border=True):
                st.markdown(f"**{req['tipo']}** · {money(req['monto'])} · {req['created_by_name']} "
                            f"· {req['created_at']}")
                with st.expander("Revisar y decidir"):
                    decision_panel(user, req)
