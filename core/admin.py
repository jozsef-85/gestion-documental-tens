from django.contrib import admin

from .models import Departamento, TipoDocumento, Documento, VersionDocumento, Auditoria


admin.site.register(Departamento)
admin.site.register(TipoDocumento)
admin.site.register(Documento)
admin.site.register(VersionDocumento)
admin.site.register(Auditoria)
