from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="payment",
            name="stripe_payment_intent_id",
            field=models.CharField(blank=True, max_length=200, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="refunded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
