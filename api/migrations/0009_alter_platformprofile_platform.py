# Generated by Django 5.1.7 on 2025-04-22 18:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_assessmentsubmission_plagiarism_score_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='platformprofile',
            name='platform',
            field=models.CharField(choices=[('codeforces', 'Codeforces'), ('leetcode', 'LeetCode'), ('codechef', 'CodeChef')], default='codeforces', max_length=20),
        ),
    ]
