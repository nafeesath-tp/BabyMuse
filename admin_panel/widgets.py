from django.forms.widgets import ClearableFileInput


class MultiFileInput(ClearableFileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        attrs = {'multiple': True, **(attrs or {})}
        super().__init__(attrs)

    def value_from_datadict(self, data, files, name):
        return files.getlist(name)
