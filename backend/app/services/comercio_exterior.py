"""Estadísticas externas independientes de las operaciones internas de MANACO."""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import unicodedata
from openpyxl import load_workbook


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').strip().lower()) if not unicodedata.combining(c)).replace(' ', '_')


def leer(path):
    registros, agregados, incidencias, hojas = [], [], [], []
    vistos = set()
    calidad = dict(leidas=0, duplicadas=0, invalidas=0, agregadas=0, conflictos=0)
    requeridas = {'pais_reportante', 'flujo_comercial', 'ano', 'codigo_sa6', 'categoria_calzado', 'socio_comercial', 'valor_usd', 'cantidad_pares'}
    libro = load_workbook(path, read_only=True, data_only=True)
    try:
        for hoja in libro:
            filas = iter(hoja.values)
            cab = [norm(v) for v in next(filas, ())]
            if not requeridas.issubset(cab):
                continue
            hojas.append(hoja.title)
            for numero, fila in enumerate(filas, 2):
                if all(v is None for v in fila):
                    continue
                calidad['leidas'] += 1
                r = dict(zip(cab, fila))
                ubicacion = {'hoja': hoja.title, 'fila': numero}
                try:
                    textos = [str(r[k] or '').strip() for k in ('pais_reportante', 'categoria_calzado', 'socio_comercial')]
                    flujo = {'importacion': 'Importación', 'exportacion': 'Exportación'}[norm(r['flujo_comercial'])]
                    anio, codigo, usd, pares = [Decimal(str(r[k])) for k in ('ano', 'codigo_sa6', 'valor_usd', 'cantidad_pares')]
                    if (not all(textos) or not all(v.is_finite() for v in (anio, codigo, usd, pares))
                            or anio != int(anio) or not 1900 <= anio <= 2100
                            or codigo != int(codigo) or not 100000 <= codigo <= 999999
                            or usd < 0 or pares < 0 or pares != int(pares)):
                        raise ValueError('Valores fuera de rango')
                except (ValueError, TypeError, KeyError, InvalidOperation, OverflowError):
                    calidad['invalidas'] += 1
                    incidencias.append({**ubicacion, 'motivo': 'Nulos, tipo de dato o rango inválido'})
                    continue
                registro = dict(anio=int(anio), codigo=str(int(codigo)), flujo=flujo,
                                pais_reportante=textos[0], categoria=textos[1], pais_socio=textos[2],
                                valor_comercial=usd, cantidad=int(pares), **ubicacion)
                firma = tuple(registro[k] for k in ('anio', 'codigo', 'flujo', 'pais_reportante', 'categoria', 'pais_socio', 'valor_comercial', 'cantidad'))
                if firma in vistos:
                    calidad['duplicadas'] += 1
                    incidencias.append({**ubicacion, 'motivo': 'Duplicado exacto excluido'})
                    continue
                vistos.add(firma)
                if norm(textos[2]) in {'mundo', 'world', 'total', 'todos_los_paises'}:
                    agregados.append(registro)
                    calidad['agregadas'] += 1
                else:
                    registros.append(registro)
    finally:
        libro.close()
    if not hojas:
        raise ValueError('No se encontraron hojas con las columnas de comercio exterior requeridas.')
    def clave(r):
        return tuple(r[k] for k in ('anio', 'codigo', 'flujo', 'pais_reportante', 'pais_socio'))
    frecuencias = Counter(clave(r) for r in registros)
    validos = []
    for r in registros:
        if frecuencias[clave(r)] > 1:
            calidad['conflictos'] += 1
            incidencias.append({'hoja': r['hoja'], 'fila': r['fila'], 'motivo': 'Clave repetida con importes distintos; excluida hasta revisión'})
        else:
            validos.append(r)
    return validos, agregados, calidad, incidencias, hojas


def indicadores(filas):
    resultado = {}
    for flujo, prefijo in [('Importación', 'importaciones'), ('Exportación', 'exportaciones')]:
        datos = [r for r in filas if r['flujo'] == flujo]
        resultado[prefijo] = float(sum((r['valor_comercial'] for r in datos), Decimal(0)))
        resultado[prefijo + '_pares'] = sum(r['cantidad'] for r in datos)
        base = [r for r in datos if r['cantidad'] > 0]
        denominador = sum(r['cantidad'] for r in base)
        resultado[prefijo + '_por_par'] = float(sum((r['valor_comercial'] for r in base), Decimal(0)) / denominador) if denominador else None
    resultado['saldo_usd'] = resultado['exportaciones'] - resultado['importaciones']
    resultado['saldo_pares'] = resultado['exportaciones_pares'] - resultado['importaciones_pares']
    resultado['registros'] = len(filas)
    return resultado


def dashboard(path: Path, anio=None, pais=None, categoria=None, flujo=None):
    todos, agregados, calidad, incidencias, hojas = leer(path)
    opciones = {campo: sorted({r[campo] for r in todos if 2020 <= r['anio'] <= 2024}) for campo in ('anio', 'pais_socio', 'categoria', 'flujo')}
    filas = [r for r in todos if 2020 <= r['anio'] <= 2024 and (anio is None or r['anio'] == anio)
             and (not pais or r['pais_socio'] == pais) and (not categoria or r['categoria'] == categoria) and (not flujo or r['flujo'] == flujo)]
    def agrupar(campo):
        grupos = defaultdict(list)
        for r in filas:
            grupos[r[campo]].append(r)
        return [dict(etiqueta=k, **indicadores(v)) for k, v in sorted(grupos.items())]
    categorias = agrupar('categoria')
    movimiento = sorted(categorias, key=lambda r: (r['importaciones_pares'] + r['exportaciones_pares'], r['etiqueta']))
    return dict(resumen=indicadores(filas), opciones=opciones, por_categoria=categorias, por_pais=agrupar('pais_socio'),
                por_anio=[dict(etiqueta=a, **indicadores([r for r in filas if r['anio'] == a])) for a in ([anio] if anio else range(2020, 2025))],
                mayor=movimiento[-1]['etiqueta'] if movimiento else None, menor=movimiento[0]['etiqueta'] if movimiento else None,
                registros=filas, agregados=agregados, calidad=calidad, incidencias=incidencias,
                fuente=dict(archivo=path.name, hojas=hojas, reportantes=sorted({r['pais_reportante'] for r in todos})))
