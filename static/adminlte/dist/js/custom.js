// Set Active Links Function
function setActiveLinks() {
    /*
     Set the currently active menu item based on the current url, or failing that, find the parent
     item from the back link
     */
    const url = window.location.pathname;
    const $back_link = $('.back-link').last();
    const $link = $('a[href="' + url + '"]');
    const $parent_link = $('.menu a[href="' + $back_link.attr('href') + '"]');

    if ($link.length) {
        $link.addClass('active');
    } 
    if ($parent_link.length) {
        $parent_link.addClass('active');
    };

    const $a_active = $('a.nav-link.active');
    const $main_li_parent = $a_active.closest('li.nav-item.has-treeview');
    const $ul_child = $main_li_parent.children('ul');

    $ul_child.show();
    $main_li_parent.addClass('menu-is-opening menu-open');
};

// Dark Mode Toggle Functionality
function setupThemeSwitcher() {
    var toggleSwitch = document.querySelector('.theme-switch input[type="checkbox"]');
    var currentTheme = localStorage.getItem('theme');
    var mainHeader = document.querySelector('.main-header');

    if (currentTheme) {
        if (currentTheme === 'dark') {
            document.body.classList.add('dark-mode');
            mainHeader.classList.add('navbar-dark');
            mainHeader.classList.remove('navbar-light');
            toggleSwitch.checked = true;
        }
    }

    function switchTheme(e) {
        if (e.target.checked) {
            document.body.classList.add('dark-mode');
            mainHeader.classList.add('navbar-dark');
            mainHeader.classList.remove('navbar-light');
            localStorage.setItem('theme', 'dark');
        } else {
            document.body.classList.remove('dark-mode');
            mainHeader.classList.add('navbar-light');
            mainHeader.classList.remove('navbar-dark');
            localStorage.setItem('theme', 'light');
        }
    }

    toggleSwitch.addEventListener('change', switchTheme, false);
}

// Color Arrays
var navbar_dark_skins = [
    'navbar-primary',
    'navbar-secondary',
    'navbar-info',
    'navbar-success',
    'navbar-danger',
    'navbar-indigo',
    'navbar-purple',
    'navbar-pink',
    'navbar-navy',
    'navbar-lightblue',
    'navbar-teal',
    'navbar-cyan',
    'navbar-dark',
    'navbar-gray-dark',
    'navbar-gray'
];

function setupThemeSettings() {
    var settings = JSON.parse(document.getElementById('adminlte-settings').innerHTML);

    // Apply settings based on the context variables
    if (settings.dark_mode) {
        $('body').addClass('dark-mode');
        $('.main-header').addClass('navbar-dark');
        $('.main-header').removeClass('navbar-light');
    }
    if (settings.header_fixed) {
        $('body').addClass('layout-navbar-fixed');
    }
    if (settings.dropdown_legacy_offset) {
        $('.main-header').addClass('dropdown-legacy');
    }
    if (settings.no_border) {
        $('.main-header').addClass('border-bottom-0');
    }
    if (settings.sidebar_collapsed) {
        $('body').addClass('sidebar-collapse');
        $(window).trigger('resize');
    }
    if (settings.sidebar_fixed) {
        $('body').addClass('layout-fixed');
        $(window).trigger('resize');
    }
    if (settings.sidebar_mini) {
        $('body').addClass('sidebar-mini');
    }
    if (settings.sidebar_mini_md) {
        $('body').addClass('sidebar-mini-md');
    }
    if (settings.sidebar_mini_xs) {
        $('body').addClass('sidebar-mini-xs');
    }
    if (settings.nav_flat_style) {
        $('.nav-sidebar').addClass('nav-flat');
    }
    if (settings.nav_legacy_style) {
        $('.nav-sidebar').addClass('nav-legacy');
    }
    if (settings.nav_compact) {
        $('.nav-sidebar').addClass('nav-compact');
    }
    if (settings.nav_child_indent) {
        $('.nav-sidebar').addClass('nav-child-indent');
    }
    if (settings.nav_child_hide_on_collapse) {
        $('.nav-sidebar').addClass('nav-collapse-hide-child');
    }
    if (settings.disable_hover_expand) {
        $('.main-sidebar').addClass('sidebar-no-expand');
    }
    if (settings.footer_fixed) {
        $('body').addClass('layout-footer-fixed');
    }
    if (settings.small_text_body) {
        $('body').addClass('text-sm');
    }
    if (settings.small_text_navbar) {
        $('.main-header').addClass('text-sm');
    }
    if (settings.small_text_brand) {
        $('.brand-link').addClass('text-sm');
    }
    if (settings.small_text_sidebar) {
        $('.nav-sidebar').addClass('text-sm');
    }
    if (settings.small_text_footer) {
        $('.main-footer').addClass('text-sm');
    }
    
    if (settings.navbar_variant) {
        $('.main-header').removeClass('navbar-dark').removeClass('navbar-light');
        if (navbar_dark_skins.indexOf(settings.navbar_variant) > -1) {
            $('.main-header').addClass('navbar-dark');
            $('.main-header').addClass(settings.navbar_variant).addClass('text-light');
        } else {
            if (settings.dark_mode) {
                $('.main-header').addClass('navbar-dark');
            } else {
                $('.main-header').addClass('navbar-light');
            }            
            $('.main-header').addClass(settings.navbar_variant);
        }
    }
    if (settings.accent_color) {
        $('body').addClass(settings.accent_color);
    }
    if (settings.sidebar_dark_variant) {
        $('.main-sidebar').addClass(settings.sidebar_dark_variant);
    }
    if (settings.sidebar_light_variant) {
        $('.main-sidebar').addClass(settings.sidebar_light_variant);
    }
    if (settings.brand_logo_variant) {
        $('.brand-link').addClass(settings.brand_logo_variant);
    }
}
// Run the functions when the document is ready
$(document).ready(function() {
    setActiveLinks();
    setupThemeSettings();
    setupThemeSwitcher();
});
