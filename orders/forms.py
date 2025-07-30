from django import forms

class ItemReturnForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'w-full border rounded p-2',
            'placeholder': 'Why are you returning this order?'
        }),
        required=True,
        label="Return Reason"
    )
