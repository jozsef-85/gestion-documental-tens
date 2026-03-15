# Seguridad

Este documento resume criterios de seguridad operativos para este proyecto.

No reemplaza una auditoría formal ni una evaluación completa de OWASP ASVS. Su objetivo es dejar una base práctica para revisar, priorizar y dar seguimiento a controles de seguridad reales del código.

## Estado actual

Escala usada:

- `Cumple`
- `Parcial`
- `No cumple`

### Checklist OWASP aterrizada al proyecto

| Control | Estado | Evidencia principal | Acción recomendada |
| --- | --- | --- | --- |
| Configuración segura de Django | Parcial | `config/settings_base.py`, `config/settings_prod.py` | Confirmar `DEBUG=False` y `DJANGO_SECRET_KEY` fuerte en producción. Ejecutar `manage.py check --deploy` en cada despliegue. |
| Gestión de secretos | Parcial | Variables de entorno en settings | Evitar defaults inseguros en producción y documentar rotación de secretos. |
| Control de acceso | Parcial | Decoradores `login_required` y `permission_required` en `core/views_*.py` | Revisar si todas las vistas con solo login deben tener permisos más finos. |
| CSRF y protección XSS por defecto | Cumple | Middleware estándar de Django y plantillas con autoescape | Mantener sin `csrf_exempt` salvo necesidad documentada. |
| Inyección SQL | Cumple | Uso de ORM de Django | Evitar consultas SQL raw sin parametrización. |
| Autenticación resistente a abuso | Parcial | Login con rate limiting por IP/usuario en la vista de acceso | Evaluar bloqueo más avanzado, observabilidad y posible MFA según criticidad. |
| Subida segura de archivos | Parcial | `core/forms.py` valida extensión, tamaño y tipo informado para documentos y planillas | Falta validación más profunda de contenido y política final de formatos permitidos por negocio. |
| Logging y auditoría | Parcial | `core/services/audit.py`, logging básico en `core/services/indicators.py` | Centralizar logs de seguridad y manejo de errores operativos. |
| Encabezados HTTP de seguridad | Parcial | `settings_prod.py` cubre HSTS, cookies seguras, `X-Frame-Options`, `Referrer-Policy` | Evaluar CSP y revisar configuración efectiva en producción. |
| Dependencias y despliegue | Parcial | `Dockerfile` usa usuario no root | Incorporar revisión de dependencias y checklist de despliegue seguro. |

## Flujo mínimo recomendado antes de publicar

```bash
python manage.py check
DJANGO_ENV=production python manage.py check --deploy
python manage.py test
```

## Prioridades inmediatas

1. Asegurar `DEBUG=False` real en producción.
2. Reemplazar cualquier `SECRET_KEY` débil por una larga y aleatoria.
3. Revisar permisos finos en vistas solo protegidas por autenticación.
4. Evaluar validación más profunda de archivos según formato y contenido real.
5. Mejorar observabilidad y respuesta ante abuso de autenticación.

## Criterio del proyecto

- No marcar un control como `Cumple` sin evidencia concreta en código o configuración.
- Si un hallazgo afecta producción, corregir en una nueva migración o cambio controlado; no reescribir historia ya aplicada.
- Mantener esta lista corta, accionable y vinculada a archivos reales del proyecto.
