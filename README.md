# Gestion Documental

## Documentación útil

- [DEPLOY.md](DEPLOY.md): flujo recomendado de despliegue y operación para este entorno.
- [SECURITY.md](SECURITY.md): checklist operativa de seguridad basada en OWASP para este proyecto.

## Correos de cobranza

El proyecto queda preparado para usar SMTP real y enviar alertas de cobranza sobre facturas pendientes de pago.

Variables base:

```bash
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_EMAIL_HOST=smtp.tu-operador.cl
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_HOST_USER=cobranzas@tuempresa.cl
DJANGO_EMAIL_HOST_PASSWORD=tu-clave
DJANGO_EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL="Gestion Documental <cobranzas@tuempresa.cl>"
DJANGO_COBRANZA_OPERATOR_EMAILS=cobranzas@tuempresa.cl,administracion@tuempresa.cl
DJANGO_COBRANZA_REPLY_TO=cobranzas@tuempresa.cl
DJANGO_COBRANZA_APP_URL=https://app.sysnergia.com/gestion/presupuestos/?estado=por_cobrar
```

Comando disponible:

```bash
python manage.py enviar_alertas_cobro --dry-run
python manage.py enviar_alertas_cobro
python manage.py enviar_alertas_cobro --enviar-clientes
```

Uso sugerido:

- `--dry-run`: revisar el resumen sin enviar correos.
- sin flags extra: enviar resumen interno al operador de cobranzas.
- `--enviar-clientes`: ademas enviar recordatorios a clientes con email cargado.

## Logs en producción

El proyecto soporta salida de logs a archivo rotado para operación real.

Variables recomendadas:

```bash
DJANGO_LOG_TO_FILE=True
DJANGO_LOG_TO_CONSOLE=False
DJANGO_LOG_DIR=/opt/gestion_documental/logs
DJANGO_APP_LOG_FILE=app.log
DJANGO_SECURITY_LOG_FILE=security.log
DJANGO_LOG_MAX_BYTES=10485760
DJANGO_LOG_BACKUP_COUNT=5
```

Archivos esperados:

- `app.log`: eventos generales de Django y la aplicación
- `security.log`: autenticación, permisos denegados, CSRF y rechazos de archivos

Para recalentar la caché de indicadores sin depender del primer request del dashboard:

```bash
python manage.py refresh_indicadores
```

## Docker

El proyecto queda preparado para construir imagen y ejecutarse con `docker compose`.

Preparación mínima:

```bash
cp .env.example .env
```

Ajusta en `.env` al menos:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_DB_NAME`
- `DJANGO_DB_USER`
- `DJANGO_DB_PASSWORD`

Primer arranque recomendado:

```bash
DJANGO_RUN_MIGRATIONS=1 docker compose up --build
```

Luego, para operación normal:

```bash
docker compose up -d
```

Notas:

- La imagen excluye `.env`, `.git`, logs y archivos locales del contexto de build mediante `.dockerignore`.
- Los estáticos se recopilan en el arranque del contenedor.
- `docker-compose.yml` incluye PostgreSQL para facilitar despliegues autocontenidos.

## Convenciones de desarrollo

### Migraciones de Django

- No renombrar migraciones ya creadas y compartidas.
- No editar el nombre de una migración que ya pudo haberse aplicado en otra base de datos.
- Crear nuevas migraciones con nombre explícito y corto.

Motivo:

Django registra el nombre de cada migración en la tabla `django_migrations`. Si se renombra un archivo ya compartido, los entornos pueden quedar desalineados y romper la cadena de dependencias.

Buenas prácticas para este proyecto:

- Usar nombres cortos y orientados al cambio principal.
- Preferir una sola responsabilidad por migración cuando sea razonable.
- Evitar nombres automáticos demasiado largos cuando el cambio ya es claro.

Ejemplos recomendados:

```bash
python manage.py makemigrations core --name presupuestos_base
python manage.py makemigrations core --name estado_manual_labels
python manage.py makemigrations core --name add_documento_indices
```

Atajo recomendado en este proyecto:

```bash
./scripts/makemigration.sh presupuestos_base
./scripts/makemigration.sh estado_manual_labels
./scripts/makemigration.sh add_documento_indices core
```

Ejemplos a evitar:

```bash
python manage.py makemigrations
```

Ese comando funciona, pero suele generar nombres extensos como `0002_modelo_a_modelo_b_and_more.py`.

### Regla práctica

Si una migración ya está en GitHub, en otra máquina o aplicada en una base real:

- se conserva tal como está
- los ajustes se hacen en una migración nueva

Si una migración todavía no salió de tu máquina:

- se puede regenerar con un nombre mejor antes de compartirla
