# orders/migrations/0004_populate_order_id.py
from django.db import migrations
import uuid

def generate_order_id():
    # Generate a 10-character uppercase alphanumeric ID
    return str(uuid.uuid4()).replace('-', '').upper()[:10]

def populate_order_id(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for order in Order.objects.filter(order_id__isnull=True):
        while True:
            new_id = generate_order_id()
            if not Order.objects.filter(order_id=new_id).exists():
                order.order_id = new_id
                order.save()
                break

def reverse_populate_order_id(apps, schema_editor):
    # Optional: Reverse migration (set order_id to NULL if needed)
    Order = apps.get_model('orders', 'Order')
    Order.objects.filter(order_id__isnull=False).update(order_id=None)

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0002_order_is_returned_order_order_id_alter_order_status_and_more'),  # Adjust to the migration before 0003
    ]

    operations = [
        migrations.RunPython(populate_order_id, reverse_populate_order_id),
    ]