from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.apps import apps
from django import forms
from django.forms import modelform_factory, inlineformset_factory
from crispy_forms.helper import FormHelper
from core.models import User
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
            # Remove hidden fields from cleaned_data
            for field in hide_fields:
                if field in cleaned_data and cleaned_data[field] == '':
                    # Ensure the field is not saved if it has an empty value
                    cleaned_data.pop(field, None)
            return cleaned_data

    head_form = DynamicHeadForm(instance=instance)

    formsets = []
    for config in model_configs['body_models']:
        BodyModel = apps.get_model(app_label=app_label, model_name=config['model_name'])
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

        formset = DynamicBodyFormset(instance=instance)
        formsets.append({'formset': formset, 'prefix':config['model_name'].lower(), 'fk_field': fk_field})

    return head_form, formsets



