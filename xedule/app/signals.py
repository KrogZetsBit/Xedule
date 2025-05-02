# tweets/signals.py
from django_celery_beat.models import IntervalSchedule
from django_celery_beat.models import PeriodicTask


def create_periodic_tasks(sender, **kwargs):
    """
    Configura tareas periódicas de Celery después de la migración
    """
    # Crear o obtener un intervalo cada 5 minutos
    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.MINUTES,
    )

    # Crear tarea periódica para publicar tweets
    PeriodicTask.objects.update_or_create(
        name="Publish scheduled tweets",
        defaults={
            "task": "xedule.app.tasks.schedule_pending_tweets",
            "interval": schedule,
            "enabled": True,
        },
    )
