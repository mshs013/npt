from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.apps import apps
from django import forms
from django.forms import modelform_factory, inlineformset_factory
from django.contrib.auth.models import Group, Permission
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Button
from core.models import User, Profile, UserBlockPermission, UserMachinePermission, Block, Machine, Department, Designation, Company
from core.middleware import get_current_user


class UserCreationForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name",)


class UserChangeForm(UserChangeForm):

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "is_staff", "is_active", "is_superuser", "groups", "user_permissions", )

class PasswordInput(forms.PasswordInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.render_value = False  # Ensure that the value is not rendered in the HTML


def generate_dynamic_formset(app_label, head_model_name, model_configs, instance=None, hide_fields=None, readonly_fields=None, widget_overrides=None, is_form_row=True, extra_form=1):
    """
    Generate dynamic forms and formsets based on the provided model configurations.
    """

    hide_fields = hide_fields or []
    readonly_fields = readonly_fields or []
    # Get the current user from the request object
    current_user = get_current_user()
    
    HeadModel = apps.get_model(app_label=app_label, model_name=head_model_name)

    # Dynamically create a form class for the head model with specified fields and Crispy Forms integration
    class DynamicHeadForm(modelform_factory(HeadModel, fields=model_configs['head_fields'])):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.helper = FormHelper()
            self.helper.form_method = 'post'
            self.helper.form_tag = False  # Let the template handle the form tag

            if 'password' in self.fields:
                self.fields['password'].widget = PasswordInput()

            # Conditionally load permissions based on whether the user is a superuser or not
            if 'user_permissions' in self.fields and current_user:
                if not current_user.is_superuser:
                    # Load only the current user's permissions for non-superusers
                    self.fields['user_permissions'].queryset = current_user.user_permissions.all()

            # Apply read-only fields if in edit mode
            if instance:
                for field in readonly_fields:
                    if field in self.fields:
                        self.fields[field].widget.attrs['readonly'] = True

                # Hide or clear fields as specified
                for field in hide_fields:
                    if field in self.fields:
                        self.fields[field].initial = None
                        self.fields[field].required = False  # Make the field optional

            # Apply widget overrides
            if widget_overrides:
                for field_name, widget in widget_overrides.items():
                    if field_name in self.fields:
                        field = self.fields[field_name]
                        
                        # For fields that have choices (MultipleChoiceField, ModelMultipleChoiceField)
                        if isinstance(field, (forms.ModelMultipleChoiceField, forms.MultipleChoiceField)):
                            self.fields[field_name].widget = widget
                            self.fields[field_name].widget.choices = field.choices  # Re-assign the choices to the widget
                        else:
                            self.fields[field_name].widget = widget  # For other field types, directly assign the widget
            
                    
        def clean(self):
            cleaned_data = super().clean()

            # Only apply if body_formsets exist
            if hasattr(self, 'body_formsets') and self.body_formsets:
                blocks_selected = 0
                machines_selected = 0
                
                for formset_dict in self.body_formsets:
                    formset = formset_dict['formset']
                    prefix = formset_dict['prefix']
                    
                    for form in formset.forms:
                        if form.cleaned_data.get('DELETE'):
                            continue
                        if prefix == 'userblockpermission' and form.cleaned_data.get('block'):
                            blocks_selected += 1
                        if prefix == 'usermachinepermission' and form.cleaned_data.get('machine'):
                            machines_selected += 1
                
                if blocks_selected > 0 and machines_selected > 0:
                    raise forms.ValidationError("You can assign either blocks or machines, not both.")
        
            # Remove hidden fields from cleaned_data
            for field in hide_fields:
                if field in cleaned_data and cleaned_data[field] == '':
                    # Ensure the field is not saved if it has an empty value
                    cleaned_data.pop(field, None)
            return cleaned_data

    head_form = DynamicHeadForm(instance=instance)

    formsets = []
    for config in model_configs['body_models']:
        if '.' in config['model_name']:
            # Format: 'app_label.ModelName'
            app_label, model_name = config['model_name'].split('.', 1)
        else:
            model_name = config['model_name']
        BodyModel = apps.get_model(app_label=app_label, model_name=model_name)
        fk_field = config['fk_field']

        DynamicFormset = inlineformset_factory(
            HeadModel, 
            BodyModel, 
            fields=config['fields'], 
            extra=extra_form,
            fk_name=fk_field,
            can_delete=True,
            can_delete_extra=True,
        )
        
        # Dynamically create a formset with Crispy Forms integration
        class DynamicBodyFormset(DynamicFormset):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
  
                for index, form in enumerate(self.forms):
                    form.helper = FormHelper()
                    form.helper.form_method = 'post'
                    form.helper.form_tag = False  # Let the template handle the form tag

                    # Apply label visibility logic based on the form index
                    #form.helper.form_show_labels = (index == 0) and is_form_row

                    if extra_form > 1:
                        # Assign placeholders to widgets of fields
                        for field_name, field in form.fields.items():
                            form.fields[field_name].widget.attrs['placeholder'] = f"Enter {field.label}"

                    # Apply read-only fields to body model forms
                    if instance:
                        for field in readonly_fields:
                            if field in form.fields:
                                form.fields[field].widget.attrs['readonly'] = True

                        # Hide or clear fields as specified for body model forms
                        for field in hide_fields:
                            if field in form.fields:
                                form.fields[field].initial = None  # Clear the field value
                                form.fields[field].required = False  # Make the field optional

                    # Apply widget overrides
                    if widget_overrides:
                        for field_name, widget in widget_overrides.items():
                            if field_name in form.fields:
                                field = form.fields[field_name]
                                
                                # For fields that have choices (MultipleChoiceField, ModelMultipleChoiceField)
                                if isinstance(field, (forms.ModelMultipleChoiceField, forms.MultipleChoiceField)):
                                    form.fields[field_name].widget = widget
                                    form.fields[field_name].widget.choices = field.choices  # Re-assign the choices to the widget
                                else:
                                    form.fields[field_name].widget = widget  # For other field types, directly assign the widget

                    # Add a custom class to the delete checkbox
                    if 'DELETE' in form.fields:
                        form.fields['DELETE'].widget.attrs.update({
                            'class': 'custom-delete-checkbox',  # Your custom class here
                        })


            def clean(self):
                cleaned_data = super().clean()
                for form in self.forms:
                    form_cleaned_data = form.clean()
                    # Remove hidden fields from cleaned_data
                    for field in hide_fields:
                        if field in form_cleaned_data and form_cleaned_data[field] == '':
                            # Ensure the field is not saved if it has an empty value
                            cleaned_data.pop(field, None)
                return cleaned_data                    

        # Inside your loop over body_models
        existing_qs = BodyModel.objects.filter(**{fk_field: instance}) if instance else BodyModel.objects.none()
        formset = DynamicBodyFormset(instance=instance, queryset=existing_qs)
        formsets.append({'formset': formset, 'prefix':model_name.lower(), 'fk_field': fk_field})

    return head_form, formsets


class DynamicUserProfileForm(forms.ModelForm):
    # Password (optional)
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False)
    )

    # Block & Machine permissions
    blocks = forms.ModelMultipleChoiceField(
        queryset=Block.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    machines = forms.ModelMultipleChoiceField(
        queryset=Machine.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    # Profile fields
    official_id = forms.CharField(required=False)
    contact_no = forms.CharField(required=False)
    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        required=False,
        empty_label="Select Department"
    )
    designation = forms.ModelChoiceField(
        queryset=Designation.objects.all(),
        required=False,
        empty_label="Select Designation"
    )
    user_img = forms.ImageField(required=False)
    user_sign = forms.ImageField(required=False)
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    default_company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        required=False,
        empty_label="Select Default Company"
    )

    # Group and permissions
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]  # do not include password here

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False

        # Make email readonly in edit mode
        if self.instance and self.instance.pk:
            self.fields["email"].widget.attrs["readonly"] = True

        # Populate profile data
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.profile
                self.fields['official_id'].initial = profile.official_id
                self.fields['contact_no'].initial = profile.contact_no
                self.fields['department'].initial = profile.department
                self.fields['designation'].initial = profile.designation
                self.fields['user_img'].initial = profile.user_img
                self.fields['user_sign'].initial = profile.user_sign
                self.fields['companies'].initial = profile.company.all()  # updated
                self.fields['default_company'].initial = profile.default_company
            except Profile.DoesNotExist:
                pass

            # Populate block/machine permissions
            try:
                self.fields['blocks'].initial = self.instance.userblockpermission.blocks.all()
            except UserBlockPermission.DoesNotExist:
                pass
            try:
                self.fields['machines'].initial = self.instance.usermachinepermission.machines.all()
            except UserMachinePermission.DoesNotExist:
                pass

            # Groups and permissions
            self.fields['groups'].initial = self.instance.groups.all()
            self.fields['user_permissions'].initial = self.instance.user_permissions.all()

    def clean(self):
        cleaned_data = super().clean()
        blocks = cleaned_data.get('blocks')
        machines = cleaned_data.get('machines')
        if blocks and machines:
            raise forms.ValidationError("You can assign either blocks or machines, not both.")
        return cleaned_data

    def save(self, commit=True):
        # Save user fields first, but skip password here
        user = super().save(commit=False)

        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)  # only update if password is provided

        if commit:
            user.save()

        # Save Profile
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.official_id = self.cleaned_data.get('official_id')
        profile.contact_no = self.cleaned_data.get('contact_no')
        profile.department = self.cleaned_data.get('department')
        profile.designation = self.cleaned_data.get('designation')
        if self.cleaned_data.get('user_img'):
            profile.user_img = self.cleaned_data.get('user_img')
        if self.cleaned_data.get('user_sign'):
            profile.user_sign = self.cleaned_data.get('user_sign')
        profile.company.set(self.cleaned_data.get('companies'))  # updated
        profile.default_company = self.cleaned_data.get('default_company')
        profile.save()

         # Save permissions (blocks/machines)
        if commit:
            ubp, _ = UserBlockPermission.objects.get_or_create(user=user)
            ump, _ = UserMachinePermission.objects.get_or_create(user=user)

            blocks = self.cleaned_data.get('blocks')
            machines = self.cleaned_data.get('machines')

            if blocks:
                ubp.blocks.set(blocks)
                ubp.save()
                ump.machines.clear()
            if machines:
                ump.machines.set(machines)
                ump.save()
                ubp.blocks.clear()

            # Save groups and user permissions
            user.groups.set(self.cleaned_data.get("groups"))
            user.user_permissions.set(self.cleaned_data.get("user_permissions"))

        return user