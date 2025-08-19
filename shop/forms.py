
from django import forms
from shop.models import Category
from django.core.exceptions import ValidationError
from .models import ProductReview

class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'comment': forms.Textarea(attrs={'rows': 3}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name','description','discount_percent']
        widgets = {
            'discount_percent': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Enter Discount %'}),
        }
    def clean_discount_percent(self):
        discount = self.cleaned_data.get('discount_percent')

        if discount is not None and discount > 30:
            raise ValidationError("Category discount cannot exceed 30%.")

        return discount
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Category.objects.filter(name__iexact=name).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("This category already exists!")
        return name