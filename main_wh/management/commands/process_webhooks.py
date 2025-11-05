from django.core.management.base import BaseCommand
from main_wh.models import WebhookRequest

from main_wh.tasks import retry_failed_notifications


class Command(BaseCommand):
    help = 'Административные команды для управления webhook обработкой'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['retry_failed', 'stats'],
            help='Действие: retry_failed - повторить ошибки, stats - статистика',
        )

    def handle(self, *args, **options):
        action = options.get('action')

        if action == 'retry_failed':
            self.stdout.write('Запуск повторной обработки ошибочных уведомлений...')
            result = retry_failed_notifications.delay()
            self.stdout.write(
                self.style.SUCCESS(f'Задача запущена (ID: {result.id})')
            )
        elif action == 'stats':
            stats = {
                'новый': WebhookRequest.objects.filter(status='new').count(),
                'ошибка': WebhookRequest.objects.filter(status='error').count(),
                'завершено': WebhookRequest.objects.filter(status='complete').count(),
                'всего': WebhookRequest.objects.count(),
            }
            self.stdout.write(f"Статистика уведомлений: {stats}")
        else:
            self.stdout.write('Используйте --action [retry_failed|stats]')