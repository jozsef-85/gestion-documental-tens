from django import forms

from .forms_shared import (
    ALLOWED_CURRICULUM_CONTENT_TYPES,
    ALLOWED_CURRICULUM_EXTENSIONS,
    ALLOWED_PERSONAL_CERTIFICATE_CONTENT_TYPES,
    ALLOWED_PERSONAL_CERTIFICATE_EXTENSIONS,
    MAX_PERSONAL_UPLOAD_SIZE,
    clean_optional_text,
    validate_uploaded_file,
)
from .models import Cliente, PersonalTrabajo


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
