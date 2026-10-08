from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('card_relations', '0008_alter_cardrelation_relation_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='cardrelation',
            name='is_resolved',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
