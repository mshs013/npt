# core/templatetags/menu_tags.py
import os
from django import template
from django.utils.safestring import mark_safe
from django.urls import resolve, Resolver404
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
    top_level_menus = Menu.objects.filter(parent__isnull=True).select_related('permission').prefetch_related(
        'children__permission').order_by('order')

    menu_html = '<ul class="menu nav nav-pills nav-sidebar flex-column" data-widget="treeview" role="menu">'

    for menu in top_level_menus:
        menu_item_html = render_menu_item(menu, user)
        if menu_item_html:  # only add if it has visible children or permission
            menu_html += menu_item_html

    menu_html += "</ul>"
    return menu_html

def render_menu_item(menu, user):
    # Recursively render children
    visible_children_html = ""
    for sub_menu in menu.children.all().order_by("order"):
        child_html = render_menu_item(sub_menu, user)
        if child_html:
            visible_children_html += child_html

    # Wrap children in <ul> if any
    if visible_children_html:
        visible_children_html = f"<ul class='nav nav-treeview'>{visible_children_html}</ul>"

    # Determine if the menu is accessible
    if user.is_superuser:
        has_permission = True
    else:
        if menu.permission:
            has_permission = user_has_permission(user, menu)
        else:
            url = menu.get_absolute_url()
            try:
                match = resolve(url)
                view_func = match.func
                # Unwrap decorators
                while hasattr(view_func, "__wrapped__"):
                    view_func = view_func.__wrapped__
                has_permission = getattr(view_func, "_skip_permission", False)
            except Resolver404:
                has_permission = False

    # Hide menu if no children AND no permission (for non-superuser)
    if not visible_children_html and not has_permission:
        return ""

    angle_icon_html = '<i class="right fas fa-angle-left"></i>' if visible_children_html else ""
    tree_class = "has-treeview" if visible_children_html else ""
    url = menu.get_absolute_url() if has_permission else "#"

    return f"""
        <li class='nav-item {tree_class}'>
            <a href="{url}" class="nav-link">
                <i class="nav-icon fas fa-{menu.icon}"></i> 
                <p>
                    {menu.name}
                    {angle_icon_html}
                </p>
            </a>
            {visible_children_html}
        </li>
    """

def user_has_permission(user, menu):
    if not hasattr(user, "_cached_perms"):
        user._cached_perms = user.get_all_permissions()

    if menu.permission:
        permission_code = f"{menu.permission.content_type.app_label}.{menu.permission.codename}"
        return permission_code in user._cached_perms
    return True
