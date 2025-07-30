from django.forms.widgets import FileInput

class MultiFileInput(FileInput):
    """A custom widget to handle multiple file uploads."""
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        super().__init__(attrs={'multiple': True, **(attrs or {})})

    def value_from_datadict(self, data, files, name):
        """Handle multiple files in the form data."""
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return files.get(name)