# Generated by Django 4.2.20 on 2025-04-25 20:27

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('app', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tweet',
            name='nostr_id',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='Nostr Event ID'),
        ),
        migrations.AddField(
            model_name='tweet',
            name='publish_to_nostr',
            field=models.BooleanField(default=False, verbose_name='Publish to Nostr'),
        ),
        migrations.CreateModel(
            name='NostrCredentials',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('private_key', models.CharField(max_length=64, verbose_name='Private Key')),
                ('public_key', models.CharField(max_length=64, verbose_name='Public Key')),
                ('relay_urls', models.TextField(help_text='Enter one relay URL per line', verbose_name='Relay URLs')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='nostr_credentials', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Nostr Credentials',
                'verbose_name_plural': 'Nostr Credentials',
            },
        ),
    ]
