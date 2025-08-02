from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.conf import settings
from django.utils.safestring import mark_safe
from django.contrib.auth.models import Permission

from core.forms import UserCreationForm, UserChangeForm
from core.models import User, Profile, ActivityLog, Menu

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class UserAdmin(UserAdmin):
    def edit(self, obj):
        return format_html('<a class="btn btn-outline-primary" href="/admin/core/user/{}/change/"><i class="fas fa-pen"></i> Change</a>', obj.id)

    def delete(self, obj):
        return format_html('<a class="btn btn-outline-danger" href="/admin/core/user/{}/delete/"><i class="fas fa-trash"></i> Delete</a>', obj.id)

    add_form = UserCreationForm
    form = UserChangeForm
    model = User
    inlines = (ProfileInline, )
    list_display_links = None
    list_display = ('email', 'get_name', 'image', 'is_superuser', 'is_staff', 'is_active', 'last_login', 'edit', 'delete')
    list_filter = ("first_name", "last_name", "profile__department", "profile__designation", "is_staff", "is_active",)
    list_select_related = ('profile', )
    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "password")}),
        ("Permissions", {"fields": ("is_superuser", "is_staff", "is_active", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "password1", "password2", "is_staff",
                "is_active", "groups", "user_permissions"
            )}
        ),
    )
    search_fields = ("email",)
    ordering = ("email",)

    def get_name(self, instance):
        return instance.get_full_name()
    get_name.short_description = 'Full Name'
    
    def image(self, instance):
        if instance.profile.user_img != '':
            return mark_safe('<img src="%s%s" width="100" />' % (f'{settings.MEDIA_URL}', instance.profile.user_img))
    image.short_description = 'Image'

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(UserAdmin, self).get_inline_instances(request, obj)


admin.site.register(User, UserAdmin)


class PermissionAdmin(admin.ModelAdmin):
    def edit(self, obj):
        return format_html('<a class="btn btn-outline-primary" href="/admin/auth/permission/{}/change/"><i class="fas fa-pen"></i> Change</a>', obj.id)

    def delete(self, obj):
        return format_html('<a class="btn btn-outline-danger" href="/admin/auth/permission/{}/delete/"><i class="fas fa-trash"></i> Delete</a>', obj.id)

    search_fields=['name']
    list_display_links = None
    list_display = ('name','content_type', 'codename', 'edit', 'delete')
    list_per_page = 20 # No of records per page 
    list_filter = ('name', 'content_type')
    #fields=['name', 'content_type', 'codename']
    #actions = None
    #search = None

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Permission'} # Here
        return super().changelist_view(request, extra_context=extra_context)

admin.site.register(Permission, PermissionAdmin)

class ActivityLogAdmin(admin.ModelAdmin):
    def edit(self, obj):
        return format_html('<a class="btn btn-outline-primary" href="/admin/core/activitylog/{}/change/"><i class="fas fa-pen"></i> Change</a>', obj.id)

    def delete(self, obj):
        return format_html('<a class="btn btn-outline-danger" href="/admin/core/activitylog/{}/delete/"><i class="fas fa-trash"></i> Delete</a>', obj.id)

    search_fields=['name']
    list_display_links = None
    list_display = ('actor', 'action_type', 'action_time', 'status', 'content_type')
    list_per_page = 20 # No of records per page 
    list_filter = ('action_type', 'status')
    #fields=['name', 'content_type', 'codename']
    #actions = None
    #search = None

    def changelist_view(self, request, extra_context=None):
        extra_context = {'title': 'Activity Log'} # Here
        return super().changelist_view(request, extra_context=extra_context)

admin.site.register(ActivityLog, ActivityLogAdmin)

class MenuAdmin(admin.ModelAdmin):
    def edit(self, obj):
        return format_html('<a class="btn btn-outline-primary" href="/admin/core/menu/{}/change/"><i class="fas fa-pen"></i> Change</a>', obj.id)

    def delete(self, obj):
        return format_html('<a class="btn btn-outline-danger" href="/admin/core/menu/{}/delete/"><i class="fas fa-trash"></i> Delete</a>', obj.id)
    
    list_display = ('name', 'parent', 'url', 'order', 'permission', 'edit', 'delete')
    list_per_page = 20 # No of records per page 
    list_filter = ('parent',)
    search_fields = ('name', 'url')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'permission':
            kwargs['queryset'] = Permission.objects.filter(codename__startswith='view_')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
admin.site.register(Menu, MenuAdmin)