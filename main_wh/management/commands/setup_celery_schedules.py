from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule


class Command(BaseCommand):
    help = 'Настройка начального расписания Celery Beat'

    def handle(self, *args, **options):
        self.stdout.write('Настройка расписания Celery Beat...')

        # Создаем интервалы
        interval_5min, _ = IntervalSchedule.objects.get_or_create(
            every=300,
            period=IntervalSchedule.SECONDS,
        )

        # Создаем cron расписания
        crontab_2am, _ = CrontabSchedule.objects.get_or_create(
            hour=2, minute=0, timezone="Asia/Yekaterinburg"
        )

        crontab_4am, _ = CrontabSchedule.objects.get_or_create(
            hour=4, minute=0, timezone="Asia/Yekaterinburg"
        )

        # Задачи
        tasks = [
            ("process-pending-notifications", "main_wh.tasks.process_pending_notifications", interval_5min),
            ("retry-failed-notifications", "main_wh.tasks.retry_failed_notifications", crontab_2am),
            ("cleanup-old-notifications", "main_wh.tasks.cleanup_old_notifications", crontab_4am),
        ]

        for name, task, schedule in tasks:
            obj, created = PeriodicTask.objects.get_or_create(
                name=name,
                task=task,
                schedule=schedule,
                defaults={"enabled": True}
            )
            if created:
                self.stdout.write(f'Создана задача: {name}')
            else:
                self.stdout.write(f'Задача уже создана: {name}')

        self.stdout.write('Celery Beat настройка расписания завершена!')
