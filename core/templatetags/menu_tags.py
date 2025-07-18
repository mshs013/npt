# core/templatetags/menu_tags.py
import os
from django import template
from django.utils.safestring import mark_safe
from django.core.cache import cache
from django.conf import settings
from core.models import Menu

register = template.Library()

# Directory to store cached menus
MENU_CACHE_DIR = os.path.join(settings.BASE_DIR, 'menu_cache')
if not os.path.exists(MENU_CACHE_DIR):
    os.makedirs(MENU_CACHE_DIR)

@register.simple_tag(takes_context=True)
def render_menu(context):
    user = context['request'].user
    # Cache menu in a file for this user to avoid querying frequently
    menu_file_path = os.path.join(MENU_CACHE_DIR, f"menu_for_user_{user.id}.html")
    
    # Check if the cached file exists
    if os.path.exists(menu_file_path):
        with open(menu_file_path, 'r') as file:
            return mark_safe(file.read())

    # If not cached, generate the menu and save it to a file
    menu_html = generate_menu_html(user)
    with open(menu_file_path, 'w') as file:
        file.write(menu_html)

    return mark_safe(menu_html)

def generate_menu_html(user):
    # Prefetch children and permissions in one query
    top_level_menus = Menu.objects.filter(parent__isnull=True).select_related('permission').prefetch_related(
        'children__permission').order_by('order')

    menu_html = '<ul class="menu nav nav-pills nav-sidebar flex-column" data-widget="treeview" role="menu">'

    for menu in top_level_menus:
        if user_has_permission(user, menu):
            menu_html += render_menu_item(menu, user)

    menu_html += "</ul>"
    return menu_html

def render_menu_item(menu, user):
    sub_menu_html = ""
    angle_icon_html = ""
    tree_class = ""

    if menu.children.exists():  # Avoid querying in a loop
        sub_menu_html = "<ul class='nav nav-treeview'>"
        for sub_menu in menu.children.all().order_by('order'):
            if user_has_permission(user, sub_menu):
                sub_menu_html += render_menu_item(sub_menu, user)
        sub_menu_html += "</ul>"
        angle_icon_html = '<i class="right fas fa-angle-left"></i>'
        tree_class = 'has-treeview'

    return f"""
        <li class='nav-item {tree_class}'>
            <a href="{menu.get_absolute_url()}" class="nav-link">
                <i class="nav-icon fas fa-{menu.icon}"></i> 
                <p>
                    {menu.name}
                    {angle_icon_html}
                </p>
            </a>
            {sub_menu_html}
        </li>
    """

def user_has_permission(user, menu):
    if menu.permission:
        permission_code = f"{menu.permission.content_type.app_label}.{menu.permission.codename}"
        # Use a cached permissions check to avoid querying in loops
        return user.has_perm(permission_code)
    return True  # If no permission is set, allow access
