import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NAMESPACE = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'rel': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'pkg': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

ESTADOS_OC = [
    ('No Aprobado', 'No Aprobado'),
    ('Aprobado', 'Aprobado'),
    ('En curso', 'En curso'),
    ('Terminado', 'Terminado'),
]

# La importacion intenta respetar la realidad de una PYME: la planilla puede
# venir con encabezados parecidos, no siempre identicos, y aun asi deberia leerse.
HEADER_MAP = {
    'FECHA': 'fecha',
    'PRESUPUESTO': 'presupuesto',
    'N PRESUPUESTO': 'presupuesto',
    'DESCRIPCION': 'descripcion',
    'SOLICITANTE': 'solicitante',
    'VALOR': 'monto',
    'MONTO': 'monto',
    'ORDEN DE COMPRA': 'nota_pedido',
    'NOTA DE PEDIDO': 'nota_pedido',
    'NOTA DE PEDIDO O.C': 'nota_pedido',
    'ESTADO O.C': 'estado_oc',
    'OBSERVACION O.C': 'observacion_oc',
    'RECEPCION': 'recepcion',
    'ESTADO RECEPCION': 'estado_recepcion',
    'GUIA DE DESPACHO': 'guia_despacho',
    'FACTURA': 'factura',
    'FECHA DE FACTURACION': 'fecha_facturacion',
    'FECHA DE PAGO': 'fecha_pago',
}

SPANISH_MONTHS = {
    'ene': 1, 'enero': 1,
    'feb': 2, 'febrero': 2,
    'mar': 3, 'marzo': 3,
    'abr': 4, 'abril': 4,
    'may': 5, 'mayo': 5,
    'jun': 6, 'junio': 6,
    'jul': 7, 'julio': 7,
    'ago': 8, 'agosto': 8,
    'sep': 9, 'sept': 9, 'septiembre': 9, 'set': 9, 'setiembre': 9,
    'oct': 10, 'octubre': 10,
    'nov': 11, 'noviembre': 11,
    'dic': 12, 'diciembre': 12,
}

EXCEL_EPOCH = date(1899, 12, 30)


def normalizar_estado_oc(valor):
    # Normaliza distintas variantes que suelen venir desde Excel para no romper
    # reportes ni filtros por simples diferencias de escritura.
    texto = str(valor or '').strip()
    if not texto:
        return ''

    normalizado = unicodedata.normalize('NFKD', texto)
    normalizado = normalizado.encode('ascii', 'ignore').decode('ascii').lower()
    normalizado = ' '.join(normalizado.replace('_', ' ').replace('-', ' ').split())

    equivalencias = {
        'no aprobado': 'No Aprobado',
        'aprobado': 'Aprobado',
        'en curso': 'En curso',
        'en proceso': 'En curso',
        'terminado': 'Terminado',
        'realizado': 'Terminado',
        'finalizado': 'Terminado',
        'completado': 'Terminado',
    }
    return equivalencias.get(normalizado, texto)


@dataclass
class PresupuestoImportado:
    fila_origen: int
    fecha: date | None
    fecha_texto: str
    presupuesto: str
    descripcion: str
    solicitante: str
    monto: Decimal | None
    nota_pedido: str
    estado_oc: str
    observacion_oc: str
    recepcion: str
    estado_recepcion: str
    guia_despacho: str
    factura: str
    fecha_facturacion: date | None
    fecha_facturacion_texto: str
    fecha_pago: date | None
    fecha_pago_texto: str


@dataclass
class ResultadoImportacionPresupuesto:
    hoja: str
    registros: list[PresupuestoImportado]


def normalizar_encabezado(valor):
    texto = unicodedata.normalize('NFKD', str(valor or ''))
    texto = texto.encode('ascii', 'ignore').decode('ascii')
    texto = texto.replace('\n', ' ')
    return ' '.join(texto.strip().upper().split())


def indice_columna(referencia):
    letras = ''.join(car for car in referencia if car.isalpha()).upper()
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra) - 64)
    return indice - 1


def formatear_celda(celda, shared_strings):
    tipo = celda.attrib.get('t')
    if tipo == 'inlineStr':
        textos = [nodo.text or '' for nodo in celda.findall('.//main:t', NAMESPACE)]
        return ''.join(textos).strip()

    valor = celda.find('main:v', NAMESPACE)
    if valor is None or valor.text is None:
        return ''

    texto = valor.text.strip()
    if tipo == 's':
        return shared_strings[int(texto)]
    if tipo == 'b':
        return 'TRUE' if texto == '1' else 'FALSE'
    return texto


def parsear_shared_strings(archivo_zip):
    if 'xl/sharedStrings.xml' not in archivo_zip.namelist():
        return []

    xml = ET.fromstring(archivo_zip.read('xl/sharedStrings.xml'))
    valores = []
    for item in xml.findall('main:si', NAMESPACE):
        partes = [nodo.text or '' for nodo in item.findall('.//main:t', NAMESPACE)]
        valores.append(''.join(partes))
    return valores


def leer_primera_hoja(contenido):
    # La operacion usa la primera hoja disponible como fuente oficial de carga.
    # Eso simplifica el uso diario y evita pedir configuraciones extra al usuario.
    with ZipFile(BytesIO(contenido)) as archivo_zip:
        workbook = ET.fromstring(archivo_zip.read('xl/workbook.xml'))
        relaciones = ET.fromstring(archivo_zip.read('xl/_rels/workbook.xml.rels'))
        mapa_relaciones = {
            relacion.attrib['Id']: relacion.attrib['Target']
            for relacion in relaciones.findall('pkg:Relationship', NAMESPACE)
        }

        primera_hoja = workbook.find('main:sheets/main:sheet', NAMESPACE)
        if primera_hoja is None:
            raise ValueError('La planilla no contiene hojas disponibles.')

        hoja = primera_hoja.attrib['name']
        rel_id = primera_hoja.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        ruta_hoja = 'xl/' + str(PurePosixPath(mapa_relaciones[rel_id]))
        sheet_xml = ET.fromstring(archivo_zip.read(ruta_hoja))
        shared_strings = parsear_shared_strings(archivo_zip)

    return hoja, sheet_xml, shared_strings


def filas_de_hoja(sheet_xml, shared_strings):
    for fila in sheet_xml.findall('main:sheetData/main:row', NAMESPACE):
        valores = {}
        for celda in fila.findall('main:c', NAMESPACE):
            indice = indice_columna(celda.attrib.get('r', 'A1'))
            valores[indice] = formatear_celda(celda, shared_strings)
        yield int(fila.attrib.get('r', '0') or 0), valores


def parsear_decimal(valor):
    texto = str(valor or '').strip()
    if not texto:
        return None

    limpio = texto.replace('$', '').replace(' ', '')
    if ',' in limpio and '.' in limpio:
        limpio = limpio.replace('.', '').replace(',', '.')
    elif ',' in limpio:
        limpio = limpio.replace('.', '').replace(',', '.')
    else:
        limpio = limpio.replace(',', '')

    try:
        return Decimal(limpio)
    except InvalidOperation:
        return None


def serial_excel_a_fecha(valor):
    try:
        serial = int(float(valor))
    except (TypeError, ValueError):
        return None

    if serial <= 0:
        return None
    return EXCEL_EPOCH + timedelta(days=serial)


def parsear_fecha_texto(valor):
    # Acepta formatos manuales frecuentes y tambien seriales de Excel para poder
    # absorber planillas heterogeneas sin exigir limpieza previa.
    texto = str(valor or '').strip()
    if not texto:
        return None, ''

    if texto.isdigit():
        fecha = serial_excel_a_fecha(texto)
        if fecha is not None:
            return fecha, fecha.strftime('%d/%m/%Y')

    for formato in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            fecha = datetime.strptime(texto, formato).date()
            return fecha, fecha.strftime('%d/%m/%Y')
        except ValueError:
            continue

    normalizado = unicodedata.normalize('NFKD', texto)
    normalizado = normalizado.encode('ascii', 'ignore').decode('ascii').lower()
    normalizado = normalizado.replace('.', ' ').replace(',', ' ')
    normalizado = ' '.join(normalizado.split())

    match = re.match(r'^(\d{1,2})\s+de\s+([a-z]+)\s+del?\s+(\d{2,4})$', normalizado)
    if not match:
        match = re.match(r'^(\d{1,2})[\s/-]+([a-z]+)[\s/-]+(\d{2,4})$', normalizado)

    if not match:
        return None, texto

    dia = int(match.group(1))
    mes_texto = match.group(2)
    anio = int(match.group(3))
    if anio < 100:
        anio += 2000

    mes = SPANISH_MONTHS.get(mes_texto)
    if mes is None:
        return None, texto

    try:
        fecha = date(anio, mes, dia)
    except ValueError:
        return None, texto

    return fecha, fecha.strftime('%d/%m/%Y')


def parsear_planilla_presupuestos(archivo):
    # Esta funcion traduce la planilla de control externa al modelo interno del sistema.
    # Desde aqui nacen el seguimiento operativo, el dashboard y la cobranza.
    archivo.seek(0)
    contenido = archivo.read()
    archivo.seek(0)

    hoja, sheet_xml, shared_strings = leer_primera_hoja(contenido)
    filas = list(filas_de_hoja(sheet_xml, shared_strings))
    if not filas:
        raise ValueError('La planilla no contiene filas para importar.')

    _, encabezados_crudos = filas[0]
    encabezados = {}
    for indice, valor in encabezados_crudos.items():
        clave = HEADER_MAP.get(normalizar_encabezado(valor))
        if clave:
            encabezados[clave] = indice

    if 'presupuesto' not in encabezados or 'descripcion' not in encabezados:
        raise ValueError('La planilla debe incluir al menos las columnas PRESUPUESTO y DESCRIPCION.')

    registros = []
    for fila_origen, celdas in filas[1:]:
        datos = {}
        for clave, indice in encabezados.items():
            datos[clave] = str(celdas.get(indice, '') or '').strip()

        if not any(datos.values()):
            continue

        # Se conserva tanto la fecha parseada como su texto normalizado para no
        # perder informacion cuando el origen viene inconsistente o incompleto.
        fecha, fecha_texto = parsear_fecha_texto(datos.get('fecha', ''))
        fecha_facturacion, fecha_facturacion_texto = parsear_fecha_texto(datos.get('fecha_facturacion', ''))
        fecha_pago, fecha_pago_texto = parsear_fecha_texto(datos.get('fecha_pago', ''))

        registros.append(
            PresupuestoImportado(
                fila_origen=fila_origen,
                fecha=fecha,
                fecha_texto=fecha_texto,
                presupuesto=datos.get('presupuesto', ''),
                descripcion=datos.get('descripcion', ''),
                solicitante=datos.get('solicitante', ''),
                monto=parsear_decimal(datos.get('monto', '')),
                nota_pedido=datos.get('nota_pedido', ''),
                estado_oc=normalizar_estado_oc(datos.get('estado_oc', '')),
                observacion_oc=datos.get('observacion_oc', ''),
                recepcion=datos.get('recepcion', ''),
                estado_recepcion=datos.get('estado_recepcion', ''),
                guia_despacho=datos.get('guia_despacho', ''),
                factura=datos.get('factura', ''),
                fecha_facturacion=fecha_facturacion,
                fecha_facturacion_texto=fecha_facturacion_texto,
                fecha_pago=fecha_pago,
                fecha_pago_texto=fecha_pago_texto,
            )
        )

    if not registros:
        raise ValueError('La planilla no contiene registros utiles para importar.')

    return ResultadoImportacionPresupuesto(hoja=hoja, registros=registros)
