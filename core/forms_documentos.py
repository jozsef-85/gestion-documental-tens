from django import forms

from .forms_shared import (
    ALLOWED_DOCUMENT_CONTENT_TYPES,
    ALLOWED_DOCUMENT_EXTENSIONS,
    MAX_DOCUMENT_UPLOAD_SIZE,
    validate_uploaded_file,
)
from .models import Documento, RegistroPresupuesto


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
