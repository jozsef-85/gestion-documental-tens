from io import BytesIO
from zipfile import ZipFile


def construir_xlsx_prueba(*, encabezado_presupuesto='PRESUPUESTO', encabezado_monto='ORDEN DE COMPRA'):
    workbook_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <sheets>
            <sheet name="Hoja1" sheetId="1" r:id="rId1"/>
        </sheets>
    </workbook>
    """

    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
        <Relationship Id="rId1"
            Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
            Target="worksheets/sheet1.xml"/>
    </Relationships>
    """

    shared_strings_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="23" uniqueCount="23">
        <si><t>FECHA</t></si>
        <si><t>{encabezado_presupuesto}</t></si>
        <si><t>DESCRIPCION</t></si>
        <si><t>SOLICITANTE</t></si>
        <si><t>{encabezado_monto}</t></si>
        <si><t>NOTA DE PEDIDO</t></si>
        <si><t>FACTURA</t></si>
        <si><t>FECHA DE PAGO</t></si>
        <si><t>ESTADO O.C</t></si>
        <si><t>OBSERVACION O.C</t></si>
        <si><t>ESTADO RECEPCION</t></si>
        <si><t>Presupuesto 1</t></si>
        <si><t>Servicio de prueba</t></si>
        <si><t>Usuario 1</t></si>
        <si><t>OC-001</t></si>
        <si><t>FAC-100</t></si>
        <si><t>Presupuesto 2</t></si>
        <si><t>Servicio 2</t></si>
        <si><t>Usuario 2</t></si>
        <si><t>17 de enero del 2025</t></si>
        <si><t>En curso</t></si>
        <si><t>Observacion de prueba</t></si>
        <si><t>Recibido parcialmente</t></si>
    </sst>
    """

    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
        <sheetData>
            <row r="1">
                <c r="A1" t="s"><v>0</v></c>
                <c r="B1" t="s"><v>1</v></c>
                <c r="C1" t="s"><v>2</v></c>
                <c r="D1" t="s"><v>3</v></c>
                <c r="E1" t="s"><v>4</v></c>
                <c r="F1" t="s"><v>5</v></c>
                <c r="G1" t="s"><v>6</v></c>
                <c r="H1" t="s"><v>7</v></c>
                <c r="I1" t="s"><v>8</v></c>
                <c r="J1" t="s"><v>9</v></c>
                <c r="K1" t="s"><v>10</v></c>
            </row>
            <row r="2">
                <c r="A2"><v>45587</v></c>
                <c r="B2" t="s"><v>11</v></c>
                <c r="C2" t="s"><v>12</v></c>
                <c r="D2" t="s"><v>13</v></c>
                <c r="E2"><v>2572978</v></c>
                <c r="F2" t="s"><v>14</v></c>
                <c r="G2" t="s"><v>15</v></c>
                <c r="I2" t="s"><v>20</v></c>
                <c r="J2" t="s"><v>21</v></c>
                <c r="K2" t="s"><v>22</v></c>
            </row>
            <row r="3">
                <c r="A3" t="s"><v>19</v></c>
                <c r="B3" t="s"><v>16</v></c>
                <c r="C3" t="s"><v>17</v></c>
                <c r="D3" t="s"><v>18</v></c>
                <c r="E3"><v>500000</v></c>
            </row>
        </sheetData>
    </worksheet>
    """

    buffer = BytesIO()
    with ZipFile(buffer, 'w') as archivo_zip:
        archivo_zip.writestr('xl/workbook.xml', workbook_xml)
        archivo_zip.writestr('xl/_rels/workbook.xml.rels', rels_xml)
        archivo_zip.writestr('xl/sharedStrings.xml', shared_strings_xml)
        archivo_zip.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    buffer.seek(0)
    return buffer
