from django.contrib import admin
from library.models import NptReason
from django.utils.html import format_html

# Register your models here.

class NptReasonAdmin(admin.ModelAdmin):
    def edit(self, obj):
        return format_html('<a class="btn btn-outline-primary" href="/admin/library/nptreason/{}/change/"><i class="fas fa-pen"></i> Change</a>', obj.id)

    def delete(self, obj):
        return format_html('<a class="btn btn-outline-danger" href="/admin/library/nptreason/{}/delete/"><i class="fas fa-trash"></i> Delete</a>', obj.id)
    
    list_display = ('name', 'min_time', 'edit', 'delete')
    list_per_page = 20 # No of records per page 
    list_filter = ('name',)
    search_fields = ('name', 'min_time')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'permission':
            kwargs['queryset'] = Permission.objects.filter(codename__startswith='view_')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
admin.site.register(NptReason, NptReasonAdmin)
