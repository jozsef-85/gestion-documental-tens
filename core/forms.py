from django import forms
from .models import Documento

class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ['titulo', 'descripcion', 'tipo_documento', 'departamento', 'archivo_actual', 'nivel_confidencialidad']
        
class VersionDocumentoForm(forms.Form):
    numero_version = forms.CharField(label="Nueva versión", max_length=20)
    archivo = forms.FileField(label="Archivo actualizado")
    comentario = forms.CharField(label="Comentario", required=False, widget=forms.Textarea)
