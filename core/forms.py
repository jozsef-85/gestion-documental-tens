from django import forms
import logging

from .models import Cliente, Documento, PersonalTrabajo, RegistroPresupuesto
from .presupuestos import parsear_fecha_texto


security_logger = logging.getLogger('security')


MAX_DOCUMENT_UPLOAD_SIZE = 15 * 1024 * 1024
MAX_SPREADSHEET_UPLOAD_SIZE = 10 * 1024 * 1024

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

    def clean_archivo_actual(self):
        archivo = self.cleaned_data['archivo_actual']
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
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'departamento': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'nivel_confidencialidad': forms.Select(attrs={'class': 'form-select'}),
        }


class VersionDocumentoForm(forms.Form):
    numero_version = forms.CharField(label='Nueva versión', max_length=20)
    archivo = forms.FileField(label='Archivo actualizado')
    comentario = forms.CharField(label='Comentario', required=False, widget=forms.Textarea)

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
        })
        self.fields['archivo'].widget.attrs.update({
            'class': 'form-control',
            'accept': '.xls,.xlsx',
        })

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
    documentos_relacionados = forms.ModelMultipleChoiceField(
        label='Documentos de respaldo',
        queryset=Documento.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['documentos_relacionados'].queryset = Documento.objects.order_by('titulo')
        if self.instance.pk:
            self.fields['documentos_relacionados'].initial = self.instance.documentos.all()

    class Meta:
        model = RegistroPresupuesto
        fields = [
            'presupuesto',
            'descripcion',
            'solicitante',
            'valor',
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
            'presupuesto': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control'}),
            'solicitante': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'fecha_texto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 17/01/2025'}),
            'nota_pedido': forms.TextInput(attrs={'class': 'form-control'}),
            'estado_oc': forms.TextInput(attrs={'class': 'form-control'}),
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


class PersonalTrabajoForm(forms.ModelForm):
    class Meta:
        model = PersonalTrabajo
        fields = ['nombre', 'cargo', 'area', 'email', 'telefono', 'fecha_ingreso', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_ingreso': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'activo': forms.Select(choices=[(True, 'Activo'), (False, 'Inactivo')], attrs={'class': 'form-select'}),
        }
