"""
Fase 2b — GENERADOR del archivo de carga ERP (formato Adj 1), CSV latin-1.

Modelo (corregido): los traslados modifican el presupuesto ORIGINAL (Adj 1).
  absoluto_mes = PPTO_mes(Adj1) + delta_neto_mes   (por terna CC/cuenta/dim)
El SALDO se valida aparte, contra el vigente (Adj 2), en budget_cutoff. Aquí solo se
construye el archivo con las solicitudes YA 'Ejecutada'.

LINEA, DIMENSION (numérica) y TIPO se toman de Adj 1 (que ya los trae). El catálogo
CC->LINEA queda como respaldo si una línea no estuviera en Adj 1.
Salida: una fila por terna afectada, 12 meses absolutos. latin-1, coma, CRLF.
"""
import io
import csv
import dim_equiv as de
import budget_cutoff as bcut

PRESUPUESTO_DEFAULT = "PPTO2026"

FIXED_COLS = ["PRESUPUESTO", "LINEA", "CENTRO_COSTO", "CUENTA_CONTABLE", "DIMENSION", "TIPO"]
MONTH_HEADERS = ["31/01/2026", "28/02/2026", "31/03/2026", "30/04/2026", "31/05/2026",
                 "30/06/2026", "31/07/2026", "31/08/2026", "30/09/2026", "31/10/2026",
                 "30/11/2026", "31/12/2026"]
HEADER = FIXED_COLS + MONTH_HEADERS


def _fmt(v):
    r = round(float(v or 0), 2)
    return str(int(r)) if r == int(r) else f"{r:.2f}"


def net_deltas(executed_requests):
    """
    Delta neto por terna y mes de las solicitudes ejecutadas.
    origen resta, destino/single suma. -> {terna: [12 deltas]}
    """
    deltas = {}
    for req in executed_requests:
        mov = req.get("movimiento", {}) or {}
        for rol, line in bcut._iter_lines(mov):
            terna = bcut._key(line)
            signo = -1.0 if rol == "origen" else 1.0
            arr = deltas.setdefault(terna, [0.0] * 12)
            for idx, monto in bcut._months_of(line):
                arr[idx] += signo * abs(monto)
    return deltas


def generate(executed_requests, adj1_data, catalogo=None, presupuesto=PRESUPUESTO_DEFAULT):
    """
    executed_requests: solicitudes 'Ejecutada'.
    adj1_data: dict de budget_data.load_adj1() -> {terna: {'ppto':[12],'linea','tipo','dim_num'}}.
    catalogo: {CC: LINEA} de respaldo (opcional).
    Devuelve (csv_bytes, filas, warnings). Cada terna afectada -> una fila con 12 absolutos.
    """
    catalogo = catalogo or {}
    deltas = net_deltas(executed_requests)
    filas, warnings = [], []

    for terna in sorted(deltas):
        cc, cuenta, dim = terna
        base = adj1_data.get(terna)
        if base is None:
            warnings.append(f"{cc}/{cuenta}/{dim}: no esta en el presupuesto original (Adj 1); se omite.")
            continue
        linea = base.get("linea") or catalogo.get(str(cc).strip())
        if not linea:
            warnings.append(f"{cc}/{cuenta}/{dim}: sin LINEA en Adj 1 ni en el catalogo; se omite.")
            continue
        dim_num = base.get("dim_num") or de.punteada_a_numerica(dim)
        if not dim_num:
            warnings.append(f"{cc}/{cuenta}/{dim}: dimension sin equivalencia numerica; se omite.")
            continue
        tipo = base.get("tipo", "N") or "N"
        absolutos = [base["ppto"][m] + deltas[terna][m] for m in range(12)]
        fila = [presupuesto, str(linea), cc, cuenta, str(dim_num), tipo] + [_fmt(x) for x in absolutos]
        filas.append(dict(zip(HEADER, fila)))

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=",", lineterminator="\r\n")
    w.writerow(HEADER)
    for f in filas:
        w.writerow([f[c] for c in HEADER])
    csv_bytes = buf.getvalue().encode("latin-1", errors="replace")
    return csv_bytes, filas, warnings
