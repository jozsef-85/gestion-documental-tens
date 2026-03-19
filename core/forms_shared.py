import logging

from django import forms


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
    normalized_text = str(value or '').strip()
    if not normalized_text:
        return None if empty_to_none else ''
    return normalized_text


def _calcular_digito_verificador(numero):
    reversed_digits = map(int, reversed(numero))
    factores = (2, 3, 4, 5, 6, 7)
    acumulado = sum(digito * factor for digito, factor in zip(reversed_digits, factores * 10))
    resto = 11 - (acumulado % 11)
    if resto == 11:
        return '0'
    if resto == 10:
        return 'K'
    return str(resto)


def format_chilean_document_number(numero, digito_verificador):
    cuerpo = f'{int(numero):,}'.replace(',', '.')
    return f'{cuerpo}-{digito_verificador}'


def validate_chilean_document_number(value, *, label):
    normalized_value = clean_optional_text(value, empty_to_none=True)
    if normalized_value is None:
        return None

    compact_value = ''.join(caracter for caracter in normalized_value.upper() if caracter.isalnum())
    if len(compact_value) < 2:
        raise forms.ValidationError(f'Ingresa un {label} válido.')

    numero, digito_verificador = compact_value[:-1], compact_value[-1]
    if not numero.isdigit() or digito_verificador not in '0123456789K':
        raise forms.ValidationError(f'Ingresa un {label} válido, por ejemplo 12.345.678-5.')

    if _calcular_digito_verificador(numero) != digito_verificador:
        raise forms.ValidationError(f'El {label} no es válido. Revisa el dígito verificador.')

    return format_chilean_document_number(numero, digito_verificador)


def validate_uploaded_file(uploaded_file, *, allowed_extensions, allowed_content_types, max_size, label):
    filename = uploaded_file.name.lower()

    if not any(filename.endswith(extension) for extension in allowed_extensions):
        extensiones = ', '.join(sorted(allowed_extensions))
        security_logger.warning(
            'Archivo rechazado por extensión: label=%s filename=%s content_type=%s',
            label,
            uploaded_file.name,
            getattr(uploaded_file, 'content_type', ''),
        )
        raise forms.ValidationError(
            f'El {label} debe tener uno de estos formatos permitidos: {extensiones}.'
        )

    if uploaded_file.size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        security_logger.warning(
            'Archivo rechazado por tamaño: label=%s filename=%s size=%s max_size=%s',
            label,
            uploaded_file.name,
            uploaded_file.size,
            max_size,
        )
        raise forms.ValidationError(
            f'El {label} supera el tamaño máximo permitido de {max_size_mb} MB.'
        )

    content_type = getattr(uploaded_file, 'content_type', '') or ''
    if content_type and content_type not in allowed_content_types:
        security_logger.warning(
            'Archivo rechazado por content_type: label=%s filename=%s content_type=%s',
            label,
            uploaded_file.name,
            content_type,
        )
        raise forms.ValidationError(
            f'El tipo de archivo informado para el {label} no está permitido.'
        )

    return uploaded_file
