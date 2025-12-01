# Handmade on 2025-11-22 15:00

from django.db import migrations, models
import django.db.models.deletion


def populate_categories_and_assign(apps, schema_editor):
    CategoryWebhook = apps.get_model('main_wh', 'CategoryWebhook')
    WebhookRequest = apps.get_model('main_wh', 'WebhookRequest')

    # Создаем категории
    categories_data = [
        {
            'id_ext': 'phajA9JMvruP8bhJJQOYzs8vwKlFiX6f',
            'name': 'Основная категория 1',
            'description': 'Автоматически создана из исторических данных'
        },
        {
            'id_ext': 'Zr6mmitc9NdqtbdQJ5cBbgszyxvr0lg6',
            'name': 'Teletype категория',
            'description': 'Автоматически создана из исторических данных'
        }
    ]

    categories = {}
    for data in categories_data:
        category, created = CategoryWebhook.objects.get_or_create(
            id_ext=data['id_ext'],
            defaults=data
        )
        categories[data['id_ext']] = category

    # Создаем категорию по умолчанию для неизвестных путей
    default_category, _ = CategoryWebhook.objects.get_or_create(
        id_ext='legacy_unknown',
        defaults={
            'name': 'Исторические записи',
            'description': 'Автоматически создана для записей без категории',
            'is_active': False
        }
    )

    # Связываем WebhookRequest с категориями
    for webhook in WebhookRequest.objects.all():
        # Извлекаем external_id из path
        path_parts = webhook.path.split('/')
        id_ext = path_parts[-1] if path_parts else None

        if id_ext in categories:
            webhook.category = categories[id_ext]
        else:
            webhook.category = default_category

        webhook.save()


class Migration(migrations.Migration):
    dependencies = [
        ('main_wh', '0006_alter_webhookrequest_data_and_more'),
    ]

    operations = [
        # 1. Добавляем поле как nullable
        migrations.AddField(
            model_name='webhookrequest',
            name='category',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='main_wh.CategoryWebhook',
                related_name='webhook_requests',
                verbose_name='Категория'
            ),
        ),

        # 2. Заполняем данные
        migrations.RunPython(populate_categories_and_assign),

        # 3. Делаем поле обязательным
        migrations.AlterField(
            model_name='webhookrequest',
            name='category',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to='main_wh.CategoryWebhook',
                related_name='webhook_requests',
                verbose_name='Категория',
                null=False,
                blank=False
            ),
        ),
    ]