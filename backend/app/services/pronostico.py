"""Pronóstico de demanda mensual.

Se comparan tres modelos sencillos y explicables con validación sobre los
últimos 3 meses completos (error porcentual absoluto medio, MAPE) y se usa el
de menor error para cada serie:

1. Promedio móvil (3 meses): referencia mínima.
2. Promedio móvil estacional: promedio de los últimos 3 meses sin efecto
   estacional × índice estacional del mes proyectado.
3. Regresión lineal (scikit-learn): tendencia + variables del mes del año.

Si el historial es corto (menos de 12 meses) solo se usa el promedio móvil.
TensorFlow/Keras queda como opción futura cuando haya historial suficiente.
"""
from datetime import date, datetime

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LinearRegression
except ImportError:  # el sistema funciona aunque scikit-learn no esté instalado
    LinearRegression = None


def sumar_meses(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def serie_mensual(conn, nivel: str, suc: int | None, medida: str = "unidades"):
    """Devuelve (meses completos, {clave: valores}, {clave: valor del mes en curso}).
    nivel TOTAL -> clave 'T'; CATEGORIA -> id_categoria; PRODUCTO -> id_producto (siempre incluye 'T')."""
    filas = conn.execute(
        """SELECT date_trunc('month', v.fecha)::date AS mes, p.id_producto, p.id_categoria,
                  sum(d.cantidad - d.cantidad_devuelta) AS unidades,
                  sum(d.subtotal * (d.cantidad - d.cantidad_devuelta)::numeric / d.cantidad) AS ingresos
             FROM ventas v JOIN detalle_venta d USING (id_venta)
             JOIN variantes_producto var USING (id_variante) JOIN productos p USING (id_producto)
            WHERE v.estado <> 'ANULADA' AND (%(s)s::int IS NULL OR v.id_sucursal = %(s)s)
            GROUP BY 1, 2, 3""",
        {"s": suc},
    ).fetchall()
    hoy = date.today()
    mes_actual = date(hoy.year, hoy.month, 1)
    if not filas:
        return [], {}, {}
    df = pd.DataFrame(filas)
    df["valor"] = df[medida].astype(float)
    df["mes"] = pd.to_datetime(df["mes"]).dt.date
    if nivel == "CATEGORIA":
        df["clave"] = df["id_categoria"]
    elif nivel == "PRODUCTO":
        df["clave"] = df["id_producto"]
    else:
        df["clave"] = "T"
    inicio = min(df["mes"])
    meses = []
    m = inicio
    while m < mes_actual:
        meses.append(m)
        m = sumar_meses(m, 1)
    completos = df[df["mes"] < mes_actual]
    actual = df[df["mes"] == mes_actual]
    series, parcial = {}, {}
    tabla = completos.pivot_table(index="clave", columns="mes", values="valor", aggfunc="sum").reindex(columns=meses).fillna(0)
    for clave, fila in tabla.iterrows():
        series[clave] = [float(x) for x in fila.values]
    series["T"] = [float(x) for x in completos.groupby("mes")["valor"].sum().reindex(meses).fillna(0).values]
    for clave, v in actual.groupby("clave")["valor"].sum().items():
        parcial[clave] = float(v)
    parcial["T"] = float(actual["valor"].sum())
    return meses, series, parcial


# --------------------------------------------------------------------- modelos
def _promedio_movil(y, meses, futuros):
    nivel = float(np.mean(y[-3:])) if len(y) else 0.0
    return [nivel for _ in futuros]


def _indices(y, meses):
    s = pd.Series(y, index=[m.month for m in meses])
    media = s.mean()
    idx = {}
    for mes in range(1, 13):
        v = s[s.index == mes]
        idx[mes] = 0.75 * max(0.15, float(v.mean()) / media) + 0.25 if len(v) and media > 0 else 1.0
    return idx


def _estacional(y, meses, futuros):
    idx = _indices(y, meses)
    ult = list(zip(y[-3:], meses[-3:]))
    nivel = float(np.mean([v / idx[m.month] for v, m in ult])) if ult else 0.0
    return [max(0.0, nivel * idx[f.month]) for f in futuros]


def _regresion(y, meses, futuros):
    def X(ms, t0):
        filas = []
        for k, m in enumerate(ms):
            fila = [t0 + k] + [1.0 if m.month == j else 0.0 for j in range(1, 13)]
            filas.append(fila)
        return np.array(filas)

    modelo = LinearRegression().fit(X(meses, 0), np.array(y))
    return [max(0.0, float(v)) for v in modelo.predict(X(futuros, len(meses)))]


MODELOS = {
    "Promedio móvil (3 meses)": (_promedio_movil, 3),
    "Promedio móvil estacional": (_estacional, 12),
    "Regresión lineal (scikit-learn)": (_regresion, 15),
}


def pronosticar(y: list[float], meses: list[date], horizonte: int = 3) -> dict | None:
    n = len(y)
    if n < 4:
        return None
    futuros = [sumar_meses(meses[-1], k + 1) for k in range(horizonte)]
    resultados = {}
    for nombre, (fn, minimo) in MODELOS.items():
        if n - 3 < minimo or (fn is _regresion and LinearRegression is None):
            continue
        errores = []
        for t in range(n - 3, n):
            pred = fn(y[:t], meses[:t], [meses[t]])[0]
            if y[t] > 0:
                errores.append(abs(pred - y[t]) / y[t])
        mape = float(np.mean(errores)) if errores else None
        resultados[nombre] = mape
    if not resultados:
        return None
    validos = {k: v for k, v in resultados.items() if v is not None}
    elegido = min(validos, key=validos.get) if validos else "Promedio móvil (3 meses)"
    fn = MODELOS[elegido][0]
    return {
        "modelo": elegido,
        "mape": validos.get(elegido),
        "mape_por_modelo": resultados,
        "meses": [f.isoformat() for f in futuros],
        "pronostico": [round(v, 2) for v in fn(y, meses, futuros)],
    }


def ahora() -> datetime:
    return datetime.now()
