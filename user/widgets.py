from django.forms.widgets import ClearableFileInput

class CustomImageInput(ClearableFileInput):
    template_name = 'widgets/custom_clearable_file_input.html'
