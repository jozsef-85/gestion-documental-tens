from django import forms
import logging

from .models import AsignacionTrabajo, Cliente, Documento, PersonalTrabajo, RegistroPresupuesto
from .presupuestos import ESTADOS_OC, normalizar_estado_oc, parsear_fecha_texto


security_logger = logging.getLogger('security')


MAX_DOCUMENT_UPLOAD_SIZE = 15 * 1024 * 1024
MAX_SPREADSHEET_UPLOAD_SIZE = 10 * 1024 * 1024
MAX_PERSONAL_UPLOAD_SIZE = 10 * 1024 * 1024

ALLOWED_DOCUMENT_EXTENSIONS = {
    '.pdf',
    '.doc',
    '.docx',
    '.xls',
    '.xlsx',
    '.ppt',
    '.pptx',
    '.txt',
    '.csv',
    '.jpg',
    '.jpeg',
    '.png',
}
ALLOWED_DOCUMENT_CONTENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    'image/jpeg',
    'image/png',
}
ALLOWED_SPREADSHEET_EXTENSIONS = {'.xls', '.xlsx'}
ALLOWED_SPREADSHEET_CONTENT_TYPES = {
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/octet-stream',
}
ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES = {
    'application/pdf',
    'image/jpeg',
    'image/png',
}
ALLOWED_CURRICULUM_EXTENSIONS = {'.pdf', '.doc', '.docx'}
ALLOWED_CURRICULUM_CONTENT_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def clean_optional_text(value, *, empty_to_none=False):
    texto = str(value or '').strip()
    if not texto:
        return None if empty_to_none else ''
    return texto


def validate_uploaded_file(archivo, *, allowed_extensions, allowed_content_types, max_size, label):
    nombre = archivo.name.lower()

    if not any(nombre.endswith(extension) for extension in allowed_extensions):
        extensiones = ', '.join(sorted(allowed_extensions))
        security_logger.warning(
            'Archivo rechazado por extensión: label=%s filename=%s content_type=%s',
            label,
            archivo.name,
            getattr(archivo, 'content_type', ''),
        )
        raise forms.ValidationError(
            f'El {label} debe tener uno de estos formatos permitidos: {extensiones}.'
        )

    if archivo.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        security_logger.warning(
            'Archivo rechazado por tamaño: label=%s filename=%s size=%s max_size=%s',
            label,
            archivo.name,
            archivo.size,
            max_size,
        )
        raise forms.ValidationError(
            f'El {label} supera el tamaño máximo permitido de {max_size_mb} MB.'
        )

    content_type = getattr(archivo, 'content_type', '') or ''
    if content_type and content_type not in allowed_content_types:
        security_logger.warning(
            'Archivo rechazado por content_type: label=%s filename=%s content_type=%s',
            label,
            archivo.name,
            content_type,
        )
        raise forms.ValidationError(
            f'El tipo de archivo informado para el {label} no está permitido.'
        )

    return archivo


class DocumentoForm(forms.ModelForm):
    presupuestos = forms.ModelMultipleChoiceField(
        label='Registros de control vinculados',
        queryset=RegistroPresupuesto.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['presupuestos'].queryset = RegistroPresupuesto.objects.select_related('carga').order_by('-carga__fecha_carga', 'presupuesto')
        self.fields['estado'].choices = [choice for choice in self.fields['estado'].choices if choice[0] != 'eliminado']
        self.fields['archivo_actual'].required = not bool(self.instance.pk)
        self.fields['titulo'].help_text = 'Usa un nombre facil de reconocer, por ejemplo contrato, informe o respaldo.'
        self.fields['descripcion'].help_text = 'Explica brevemente para que sirve el documento o que contiene.'
        self.fields['tipo_documento'].help_text = 'Selecciona la categoria que mejor describe el archivo.'
        self.fields['departamento'].help_text = 'Area responsable o dueña del documento.'
        if self.instance.pk:
            self.fields['archivo_actual'].help_text = 'El archivo actual se conserva. Para reemplazarlo sin perder trazabilidad, usa "Agregar versión".'
        else:
            self.fields['archivo_actual'].help_text = 'Formatos permitidos: PDF, Office, texto, CSV e imagenes. Maximo 15 MB.'
        self.fields['estado'].help_text = 'Activo aparece en el repositorio principal. Archivado se conserva sin destacar.'
        self.fields['nivel_confidencialidad'].help_text = 'Define que tan restringido debe considerarse el archivo. Alta queda visible solo para administradores, editores y creador.'
        self.fields['presupuestos'].help_text = 'Relaciona este archivo con uno o mas seguimientos para encontrar fotos, informes, certificados o respaldos mas rapido.'

    def clean_archivo_actual(self):
        archivo = self.cleaned_data.get('archivo_actual')
        if self.instance.pk:
            if self.files.get('archivo_actual'):
                raise forms.ValidationError(
                    'Para reemplazar el archivo usa "Agregar versión" y asi mantienes el historial del documento.'
                )
            return self.instance.archivo_actual

        return validate_uploaded_file(
            archivo,
            allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
            allowed_content_types=ALLOWED_DOCUMENT_CONTENT_TYPES,
            max_size=MAX_DOCUMENT_UPLOAD_SIZE,
            label='documento',
        )

    class Meta:
        model = Documento
        fields = ['titulo', 'descripcion', 'tipo_documento', 'departamento', 'archivo_actual', 'estado', 'nivel_confidencialidad', 'presupuestos']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Contrato marco cliente ACME'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Resumen corto del contenido del archivo'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'archivo_actual': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'nivel_confidencialidad': forms.Select(attrs={'class': 'form-select'}),
        }


class VersionDocumentoForm(forms.Form):
    numero_version = forms.CharField(
        label='Nueva version',
        max_length=20,
        help_text='Ejemplo: 1.1, 2.0 o 2026-03.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 1.1'}),
    )
    archivo = forms.FileField(
        label='Archivo actualizado',
        help_text='Sube el archivo que reemplazara la version actual. Maximo 15 MB.',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'}),
    )
    comentario = forms.CharField(
        label='Que cambio en esta version',
        required=False,
        help_text='Opcional. Sirve para explicar correcciones, nuevas firmas o cambios de contenido.',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Ej: Se agrego firma del cliente y se corrigio la fecha'}),
    )

    def __init__(self, *args, **kwargs):
        self.documento = kwargs.pop('documento', None)
        super().__init__(*args, **kwargs)

    def clean_numero_version(self):
        numero_version = self.cleaned_data['numero_version'].strip()
        if not self.documento:
            return numero_version

        if numero_version == self.documento.version_actual:
            raise forms.ValidationError('Esa version ya es la version actual del documento.')

        if self.documento.versiones.filter(numero_version=numero_version).exists():
            raise forms.ValidationError('Ya existe una version registrada con ese numero.')

        return numero_version

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        return validate_uploaded_file(
            archivo,
            allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
            allowed_content_types=ALLOWED_DOCUMENT_CONTENT_TYPES,
            max_size=MAX_DOCUMENT_UPLOAD_SIZE,
            label='archivo actualizado',
        )


class CargaPresupuestoForm(forms.Form):
    nombre = forms.CharField(label='Nombre de la carga', max_length=200, required=False)
    archivo = forms.FileField(label='Planilla Excel')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ej: Carga marzo 2026',
            'autocomplete': 'off',
        })
        self.fields['archivo'].widget.attrs.update({
            'class': 'form-control',
            'accept': '.xls,.xlsx',
        })
        self.fields['archivo'].error_messages['required'] = 'Selecciona la planilla Excel que quieres importar.'

    def clean_nombre(self):
        return clean_optional_text(self.cleaned_data.get('nombre'))

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        return validate_uploaded_file(
            archivo,
            allowed_extensions=ALLOWED_SPREADSHEET_EXTENSIONS,
            allowed_content_types=ALLOWED_SPREADSHEET_CONTENT_TYPES,
            max_size=MAX_SPREADSHEET_UPLOAD_SIZE,
            label='planilla',
        )


class RegistroPresupuestoForm(forms.ModelForm):
    estado_oc = forms.ChoiceField(
        label='Estado de orden de compra',
        required=False,
        choices=[('', 'Selecciona un estado')] + ESTADOS_OC,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    documentos_relacionados = forms.ModelMultipleChoiceField(
        label='Documentos de respaldo',
        queryset=Documento.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['documentos_relacionados'].queryset = Documento.objects.order_by('titulo')
        self.fields['cliente'].label = 'Cliente'
        self.fields['presupuesto'].label = 'Presupuesto'
        self.fields['tipo_trabajo'].label = 'Tipo de trabajo'
        self.fields['ubicacion_obra'].label = 'Ubicacion de obra'
        self.fields['descripcion'].label = 'Descripcion del trabajo'
        self.fields['solicitante'].label = 'Solicitante'
        self.fields['monto'].label = 'Monto'
        self.fields['fecha_texto'].label = 'Fecha de solicitud'
        self.fields['nota_pedido'].label = 'Nota de pedido'
        self.fields['estado_oc'].label = 'Estado de la orden de compra (O.C.)'
        self.fields['observacion_oc'].label = 'Observaciones de la orden de compra'
        self.fields['recepcion'].label = 'Recepcion'
        self.fields['estado_recepcion'].label = 'Estado de recepcion'
        self.fields['guia_despacho'].label = 'Guia de despacho'
        self.fields['factura'].label = 'Factura'
        self.fields['fecha_facturacion_texto'].label = 'Fecha de facturacion'
        self.fields['fecha_pago_texto'].label = 'Fecha de pago'
        self.fields['estado_manual'].label = 'Estado manual de seguimiento'
        self.fields['observaciones'].label = 'Observaciones internas'
        self.fields['cliente'].help_text = 'Selecciona el cliente para identificar rapido a que obra o servicio corresponde.'
        self.fields['presupuesto'].help_text = 'Codigo o nombre con el que identificas este trabajo.'
        self.fields['tipo_trabajo'].help_text = 'Ayuda a separar instalaciones, mantenciones, reparaciones o certificaciones.'
        self.fields['ubicacion_obra'].help_text = 'Direccion, faena, planta o referencia donde se ejecuta el trabajo.'
        self.fields['fecha_texto'].help_text = 'Acepta fechas como 17/01/2025.'
        self.fields['nota_pedido'].help_text = 'Completa este dato cuando el trabajo ya fue aceptado por el cliente.'
        self.fields['estado_oc'].help_text = 'O.C. significa orden de compra.'
        self.fields['recepcion'].help_text = 'Registra recepcion, entrega, visita tecnica, pruebas o hitos relevantes del trabajo.'
        self.fields['estado_manual'].help_text = 'Usa este campo solo si necesitas corregir el estado calculado automaticamente.'
        self.fields['documentos_relacionados'].help_text = 'Selecciona respaldos como contratos, guias, fotos, informes o certificados relacionados.'

        self.fields['cliente'].widget.attrs.update({'class': 'form-select'})
        self.fields['descripcion'].widget.attrs.update({'rows': 4, 'placeholder': 'Describe el alcance del trabajo o servicio'})
        self.fields['tipo_trabajo'].widget.attrs.update({'class': 'form-select'})
        self.fields['ubicacion_obra'].widget.attrs.update({'placeholder': 'Ej: Obra edificio Vista Norte, piso 3'})
        self.fields['solicitante'].widget.attrs.update({'placeholder': 'Ej: VSPT / Cristian Martinez'})
        self.fields['monto'].widget.attrs.update({'placeholder': 'Ej: 2572978', 'inputmode': 'decimal', 'min': '0'})
        self.fields['fecha_texto'].widget.attrs.update({'inputmode': 'numeric', 'autocomplete': 'off'})
        self.fields['nota_pedido'].widget.attrs.update({'placeholder': 'Ej: 4503257316'})
        self.fields['observacion_oc'].widget.attrs.update({'rows': 3, 'placeholder': 'Comentarios de aprobacion, restricciones o contexto'})
        self.fields['recepcion'].widget.attrs.update({'rows': 3, 'placeholder': 'Detalle de visita tecnica, recepcion, pruebas o hitos asociados'})
        self.fields['estado_recepcion'].widget.attrs.update({'placeholder': 'Ej: Recibido parcialmente'})
        self.fields['guia_despacho'].widget.attrs.update({'placeholder': 'Ej: GD-55'})
        self.fields['factura'].widget.attrs.update({'placeholder': 'Ej: N° 780'})
        self.fields['fecha_facturacion_texto'].widget.attrs.update({'inputmode': 'numeric', 'autocomplete': 'off'})
        self.fields['fecha_pago_texto'].widget.attrs.update({'inputmode': 'numeric', 'autocomplete': 'off'})
        self.fields['observaciones'].widget.attrs.update({'rows': 4, 'placeholder': 'Notas internas para seguimiento del registro'})
        self.fields['presupuesto'].error_messages['required'] = 'Ingresa el codigo o nombre del presupuesto.'
        self.fields['monto'].error_messages['invalid'] = 'Ingresa un monto valido sin letras ni simbolos extra.'
        if self.instance.pk:
            self.fields['documentos_relacionados'].initial = self.instance.documentos.all()
            self.fields['estado_oc'].initial = normalizar_estado_oc(self.instance.estado_oc)

    class Meta:
        model = RegistroPresupuesto
        fields = [
            'cliente',
            'presupuesto',
            'tipo_trabajo',
            'ubicacion_obra',
            'descripcion',
            'solicitante',
            'monto',
            'fecha_texto',
            'nota_pedido',
            'estado_oc',
            'observacion_oc',
            'recepcion',
            'estado_recepcion',
            'guia_despacho',
            'factura',
            'fecha_facturacion_texto',
            'fecha_pago_texto',
            'estado_manual',
            'observaciones',
            'documentos_relacionados',
        ]
        widgets = {
            'cliente': forms.Select(attrs={'class': 'form-select'}),
            'presupuesto': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_trabajo': forms.Select(attrs={'class': 'form-select'}),
            'ubicacion_obra': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control'}),
            'solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'monto': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fecha_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 17/01/2025'}),
            'nota_pedido': forms.TextInput(attrs={'class': 'form-control'}),
            'observacion_oc': forms.Textarea(attrs={'class': 'form-control'}),
            'recepcion': forms.Textarea(attrs={'class': 'form-control'}),
            'estado_recepcion': forms.TextInput(attrs={'class': 'form-control'}),
            'guia_despacho': forms.TextInput(attrs={'class': 'form-control'}),
            'factura': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_facturacion_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 23/01/2025'}),
            'fecha_pago_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 30/01/2025'}),
            'estado_manual': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control'}),
        }

    def clean_fecha_texto(self):
        texto = self.cleaned_data.get('fecha_texto', '')
        fecha, texto_normalizado = parsear_fecha_texto(texto)
        self.cleaned_data['fecha'] = fecha
        return texto_normalizado or texto

    def clean_estado_oc(self):
        return normalizar_estado_oc(self.cleaned_data.get('estado_oc', ''))

    def clean_monto(self):
        monto = self.cleaned_data.get('monto')
        if monto is not None and monto < 0:
            raise forms.ValidationError('El monto no puede ser negativo.')
        return monto

    def clean_fecha_facturacion_texto(self):
        texto = self.cleaned_data.get('fecha_facturacion_texto', '')
        fecha, texto_normalizado = parsear_fecha_texto(texto)
        self.cleaned_data['fecha_facturacion'] = fecha
        return texto_normalizado or texto

    def clean_fecha_pago_texto(self):
        texto = self.cleaned_data.get('fecha_pago_texto', '')
        fecha, texto_normalizado = parsear_fecha_texto(texto)
        self.cleaned_data['fecha_pago'] = fecha
        return texto_normalizado or texto

    def save(self, commit=True):
        instancia = super().save(commit=False)
        instancia.fecha = self.cleaned_data.get('fecha')
        instancia.fecha_facturacion = self.cleaned_data.get('fecha_facturacion')
        instancia.fecha_pago = self.cleaned_data.get('fecha_pago')
        if commit:
            instancia.save()
            instancia.documentos.set(self.cleaned_data.get('documentos_relacionados', []))
        return instancia


class ClienteForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].help_text = 'Nombre comercial o razon social del cliente.'
        self.fields['rut'].help_text = 'Opcional. Si aun no lo tienes, dejalo vacio.'
        self.fields['contacto'].help_text = 'Persona de contacto principal para seguimiento comercial.'
        self.fields['email'].help_text = 'Correo principal para coordinacion o cobranza.'
        self.fields['telefono'].help_text = 'Telefono directo o celular de referencia.'
        self.fields['direccion'].help_text = 'Direccion comercial, sucursal o referencia de despacho.'
        self.fields['activo'].help_text = 'Puedes desactivar el cliente sin perder su historial.'
        self.fields['nombre'].error_messages['required'] = 'Ingresa el nombre del cliente.'
        self.fields['email'].error_messages['invalid'] = 'Ingresa un correo valido, por ejemplo contacto@empresa.cl.'
        self.fields['nombre'].widget.attrs.update({'placeholder': 'Ej: Constructora Norte'})
        self.fields['rut'].widget.attrs.update({'placeholder': 'Ej: 76.123.456-7', 'autocomplete': 'off'})
        self.fields['contacto'].widget.attrs.update({'placeholder': 'Ej: Maria Perez'})
        self.fields['email'].widget.attrs.update({'placeholder': 'Ej: contacto@empresa.cl', 'autocomplete': 'email'})
        self.fields['telefono'].widget.attrs.update({'placeholder': 'Ej: +56 9 1234 5678', 'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel'})
        self.fields['direccion'].widget.attrs.update({'placeholder': 'Ej: Av. Apoquindo 1234, Las Condes'})

    class Meta:
        model = Cliente
        fields = ['nombre', 'rut', 'contacto', 'email', 'telefono', 'direccion', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'rut': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.Select(choices=[(True, 'Activo'), (False, 'Inactivo')], attrs={'class': 'form-select'}),
        }

    def clean_nombre(self):
        nombre = clean_optional_text(self.cleaned_data.get('nombre'))
        if not nombre:
            raise forms.ValidationError('Ingresa el nombre del cliente.')
        return nombre

    def clean_rut(self):
        rut = clean_optional_text(self.cleaned_data.get('rut'), empty_to_none=True)
        return rut.upper() if rut else None

    def clean_contacto(self):
        return clean_optional_text(self.cleaned_data.get('contacto'))

    def clean_telefono(self):
        return clean_optional_text(self.cleaned_data.get('telefono'))

    def clean_direccion(self):
        return clean_optional_text(self.cleaned_data.get('direccion'))


class PersonalTrabajoForm(forms.ModelForm):
    class Meta:
        model = PersonalTrabajo
        fields = [
            'nombre',
            'cargo',
            'area',
            'activo',
            'email',
            'telefono',
            'fecha_ingreso',
            'certificado_fonasa',
            'certificado_pago_afp',
            'examen_altura_espacio_confinado',
            'afiliacion_mutualidad',
            'curriculum',
            'certificado_antecedentes',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan Perez Soto'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Electricista, Supervisor, Ayudante'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Operaciones, Terreno, Administracion'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@empresa.cl'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: +56 9 1234 5678'}),
            'fecha_ingreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'certificado_fonasa': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'certificado_pago_afp': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'examen_altura_espacio_confinado': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'afiliacion_mutualidad': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'curriculum': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            'certificado_antecedentes': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.jpg,.jpeg,.png'}),
            'activo': forms.Select(choices=[(True, 'Activo'), (False, 'Inactivo')], attrs={'class': 'form-select'}),
        }

        labels = {
            'certificado_fonasa': 'Certificado afiliacion Fonasa',
            'certificado_pago_afp': 'Certificado pago AFP',
            'examen_altura_espacio_confinado': 'Examen altura y espacio confinado',
            'afiliacion_mutualidad': 'Afiliacion a mutualidad',
            'curriculum': 'Curriculum',
            'certificado_antecedentes': 'Certificado de antecedentes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nombre'].error_messages['required'] = 'Ingresa el nombre del trabajador.'
        self.fields['cargo'].error_messages['required'] = 'Ingresa el cargo o especialidad principal.'
        self.fields['email'].error_messages['invalid'] = 'Ingresa un correo valido, por ejemplo persona@empresa.cl.'
        self.fields['nombre'].widget.attrs.update({'autocomplete': 'name'})
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        self.fields['telefono'].widget.attrs.update({'type': 'tel', 'inputmode': 'tel', 'autocomplete': 'tel'})
        self.fields['nombre'].help_text = 'Nombre completo del trabajador o trabajadora.'
        self.fields['cargo'].help_text = 'Cargo o especialidad principal dentro de la empresa.'
        self.fields['area'].help_text = 'Area interna, por ejemplo Operaciones, Terreno o Administracion.'
        self.fields['activo'].help_text = 'Puedes dejar el trabajador activo o inactivo sin afectar su documentacion.'
        self.fields['email'].help_text = 'Opcional, pero ayuda para coordinacion y comunicacion interna.'
        self.fields['telefono'].help_text = 'Usa telefono o celular de contacto directo.'
        self.fields['fecha_ingreso'].help_text = 'Fecha de ingreso a la empresa o al registro interno.'
        self.fields['certificado_fonasa'].help_text = 'PDF o imagen legible. Maximo 10 MB.'
        self.fields['certificado_pago_afp'].help_text = 'PDF o imagen legible. Maximo 10 MB.'
        self.fields['examen_altura_espacio_confinado'].help_text = 'Opcional segun faena. Acepta PDF o imagen hasta 10 MB.'
        self.fields['afiliacion_mutualidad'].help_text = 'PDF o imagen legible. Maximo 10 MB.'
        self.fields['curriculum'].help_text = 'Acepta PDF, DOC o DOCX. Maximo 10 MB.'
        self.fields['certificado_antecedentes'].help_text = 'PDF o imagen vigente. Maximo 10 MB.'

    def clean_nombre(self):
        nombre = clean_optional_text(self.cleaned_data.get('nombre'))
        if not nombre:
            raise forms.ValidationError('Ingresa el nombre del trabajador.')
        return nombre

    def clean_cargo(self):
        cargo = clean_optional_text(self.cleaned_data.get('cargo'))
        if not cargo:
            raise forms.ValidationError('Ingresa el cargo o especialidad principal.')
        return cargo

    def clean_area(self):
        return clean_optional_text(self.cleaned_data.get('area'))

    def clean_telefono(self):
        return clean_optional_text(self.cleaned_data.get('telefono'))

    def _clean_personal_respaldo(self, field_name, *, label, allowed_extensions, allowed_content_types):
        archivo = self.cleaned_data.get(field_name)
        if not archivo or not self.files.get(field_name):
            return archivo

        return validate_uploaded_file(
            archivo,
            allowed_extensions=allowed_extensions,
            allowed_content_types=allowed_content_types,
            max_size=MAX_PERSONAL_UPLOAD_SIZE,
            label=label,
        )

    def clean_certificado_fonasa(self):
        return self._clean_personal_respaldo(
            'certificado_fonasa',
            label='certificado Fonasa',
            allowed_extensions=ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS,
            allowed_content_types=ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES,
        )

    def clean_certificado_pago_afp(self):
        return self._clean_personal_respaldo(
            'certificado_pago_afp',
            label='certificado AFP',
            allowed_extensions=ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS,
            allowed_content_types=ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES,
        )

    def clean_examen_altura_espacio_confinado(self):
        return self._clean_personal_respaldo(
            'examen_altura_espacio_confinado',
            label='examen de altura y espacio confinado',
            allowed_extensions=ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS,
            allowed_content_types=ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES,
        )

    def clean_afiliacion_mutualidad(self):
        return self._clean_personal_respaldo(
            'afiliacion_mutualidad',
            label='afiliacion a mutualidad',
            allowed_extensions=ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS,
            allowed_content_types=ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES,
        )

    def clean_curriculum(self):
        return self._clean_personal_respaldo(
            'curriculum',
            label='curriculum',
            allowed_extensions=ALLOWED_CURRICULUM_EXTENSIONS,
            allowed_content_types=ALLOWED_CURRICULUM_CONTENT_TYPES,
        )

    def clean_certificado_antecedentes(self):
        return self._clean_personal_respaldo(
            'certificado_antecedentes',
            label='certificado de antecedentes',
            allowed_extensions=ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS,
            allowed_content_types=ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES,
        )


class AsignacionTrabajoForm(forms.ModelForm):
    class Meta:
        model = AsignacionTrabajo
        fields = [
            'trabajador',
            'rol',
            'estado',
            'fecha_inicio',
            'fecha_fin',
            'horas_estimadas',
            'horas_reales',
            'observaciones',
        ]
        widgets = {
            'trabajador': forms.Select(attrs={'class': 'form-select'}),
            'rol': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Supervisor, Tecnico, Apoyo en terreno'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'horas_estimadas': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 24'}),
            'horas_reales': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 18.5'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas sobre el trabajo asignado'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trabajador'].queryset = PersonalTrabajo.objects.filter(activo=True).order_by('nombre')
        self.fields['trabajador'].help_text = 'Solo se muestran trabajadores activos.'
        self.fields['rol'].help_text = 'Describe como participa la persona en este trabajo.'
        self.fields['estado'].help_text = 'Activo: trabajando hoy. Pausado o finalizado si ya no participa.'
        self.fields['fecha_inicio'].help_text = 'Opcional. Sirve para ordenar la participacion real.'
        self.fields['fecha_fin'].help_text = 'Completa este campo cuando la participacion termine.'
        self.fields['horas_estimadas'].help_text = 'Opcional. Horas planificadas para esta persona.'
        self.fields['horas_reales'].help_text = 'Opcional. Horas efectivamente trabajadas.'
        self.fields['observaciones'].help_text = 'Cualquier detalle util para coordinacion o trazabilidad.'
