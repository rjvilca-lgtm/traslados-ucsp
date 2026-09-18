"""
Fase 2b — GENERADOR del archivo de carga ERP (formato Adj 1), CSV latin-1.

Entrada: solicitudes 'Ejecutada' + la foto final del corte (budget_cutoff, que ya trae
el saldo absoluto = PPTO_vigente + Σ deltas ejecutados) + catálogo CC->LINEA.
Salida: una fila por terna (CC, cuenta, dimensión) AFECTADA, con los 12 meses ABSOLUTOS,
dimensión traducida a numérica. Encoding latin-1, coma, fin de línea CRLF.
Sin Streamlit: testeable offline.
"""
import io
import csv
import dim_equiv as de
import budget_cutoff as bcut

PRESUPUESTO_DEFAULT = "PPTO2026"

# Cabecera EXACTA del formato Adj 1 (verificada contra PLANTILLA_CARGAPPTO).
FIXED_COLS = ["PRESUPUESTO", "LINEA", "CENTRO_COSTO", "CUENTA_CONTABLE", "DIMENSION", "TIPO"]
MONTH_HEADERS = ["31/01/2026", "28/02/2026", "31/03/2026", "30/04/2026", "31/05/2026",
                 "30/06/2026", "31/07/2026", "31/08/2026", "30/09/2026", "31/10/2026",
                 "30/11/2026", "31/12/2026"]
HEADER = FIXED_COLS + MONTH_HEADERS


def _fmt(v):
    """805.0 -> '805' ; -244.73 -> '-244.73' (punto decimal)."""
    r = round(float(v or 0), 2)
    return str(int(r)) if r == int(r) else f"{r:.2f}"


def affected_ternas(executed_requests):
    """Conjunto de ternas (CC, cuenta, dim) tocadas por las solicitudes ejecutadas."""
    ternas = set()
    for req in executed_requests:
        mov = req.get("movimiento", {}) or {}
        for _, line in bcut._iter_lines(mov):
            ternas.add(bcut._key(line))
    return ternas


def generate(executed_requests, final_snapshot, catalogo, presupuesto=PRESUPUESTO_DEFAULT):
    """
    Devuelve (csv_bytes, filas, warnings).
      csv_bytes: archivo listo para descargar (latin-1).
      filas: lista de dicts (para previsualizar en la app).
      warnings: problemas por terna (LINEA o dimensión faltante) — la fila se OMITE.
    """
    ternas = affected_ternas(executed_requests)
    filas, warnings = [], []

    for terna in sorted(ternas):
        cc, cuenta, dim = terna
        rec = final_snapshot.get(terna)
        if rec is None:
            warnings.append(f"{cc}/{cuenta}/{dim}: no está en el vigente; se omite.")
            continue
        linea = catalogo.get(str(cc).strip())
        if not linea:
            warnings.append(f"{cc}/{cuenta}/{dim}: sin LINEA en el catálogo; se omite.")
            continue
        dimnum = de.punteada_a_numerica(dim)
        if dimnum is None:
            warnings.append(f"{cc}/{cuenta}/{dim}: dimensión sin equivalencia numérica; se omite.")
            continue
        tipo = (rec.get("attrs", {}) or {}).get("TIPO", "N") or "N"
        meses = [_fmt(x) for x in rec["ppto"]]  # 12 absolutos ya calculados por el corte
        fila = [presupuesto, str(linea), cc, cuenta, dimnum, tipo] + meses
        filas.append(dict(zip(HEADER, fila)))

    # Serializar CSV (coma, CRLF, latin-1)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=",", lineterminator="\r\n")
    w.writerow(HEADER)
    for f in filas:
        w.writerow([f[c] for c in HEADER])
    csv_bytes = buf.getvalue().encode("latin-1", errors="replace")
    return csv_bytes, filas, warnings
