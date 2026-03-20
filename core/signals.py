from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .services.roles import sync_role_groups_permissions


@receiver(post_migrate)
def sync_core_role_groups(sender, **kwargs):
    if getattr(sender, 'name', '') != 'core':
        return
    sync_role_groups_permissions()
