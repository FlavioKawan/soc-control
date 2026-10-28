from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable")


def drop_cache_table(apps, schema_editor):
    schema_editor.execute('DROP TABLE IF EXISTS "django_cache"')


class Migration(migrations.Migration):
    """
    Creates the DB-backed cache table (settings.CACHES) used by the login
    throttle - as a real migration instead of a manual `createcachetable`
    step, so it also exists in the test database and anywhere else
    `migrate` runs, with no separate setup step to remember.
    """

    initial = True

    dependencies = []

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
