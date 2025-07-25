# Generated by Django 5.2.4 on 2025-07-17 17:35

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='First Name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='Last Name')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='Email Address')),
                ('is_staff', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'User',
                'verbose_name_plural': 'Users',
                'permissions': [('detail_User', 'Can view custom user detail')],
            },
        ),
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('CREATE', 'Create'), ('UPDATE', 'Update'), ('DELETE', 'Delete'), ('RESTORE', 'Restore'), ('LOGIN', 'Login'), ('LOGIN_FAILED', 'Login Failed')], max_length=15)),
                ('action_time', models.DateTimeField(auto_now_add=True)),
                ('remarks', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('SUCCESS', 'Success'), ('FAILURE', 'Failure')], default='SUCCESS', max_length=7)),
                ('data', models.JSONField(default=dict)),
                ('object_id', models.CharField(blank=True, max_length=36, null=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name': 'Activity Log',
                'verbose_name_plural': 'Activity Logs',
                'permissions': [('detail_activitylog', 'Can view activity log detail')],
            },
        ),
        migrations.CreateModel(
            name='Menu',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('url', models.CharField(blank=True, max_length=100, null=True)),
                ('icon', models.CharField(blank=True, max_length=100, null=True)),
                ('order', models.PositiveIntegerField(default=1)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='core.menu')),
                ('permission', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='auth.permission')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('official_id', models.CharField(blank=True, max_length=10, null=True)),
                ('contact_no', models.CharField(blank=True, max_length=15, null=True)),
                ('user_img', models.ImageField(blank=True, null=True, upload_to='user/img/')),
                ('user_sign', models.ImageField(blank=True, null=True, upload_to='user/sign/')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Profile',
                'verbose_name_plural': 'Profiles',
            },
        ),
    ]
