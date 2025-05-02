from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "xedule.app"

    def ready(self):
        # Importar la función para crear tareas periódicas
        from .signals import create_periodic_tasks

        # Conectar la señal post_migrate
        post_migrate.connect(create_periodic_tasks, sender=self)
