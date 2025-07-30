from django import forms
from shop.models import Product, ProductVariant
import re

# Form for Product (no price/stock here)
class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'description', 'is_listed','price']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise forms.ValidationError("Product name is required.")
        if len(name) < 3:
            raise forms.ValidationError("Product name must be at least 3 characters long.")
        if not re.match(r'^[a-zA-Z0-9_]+$', name):
            raise forms.ValidationError("Product name can only contain letters, numbers, and underscores (no spaces or special characters).")
        return name

    def clean(self):
        cleaned_data = super().clean()
        existing_images = self.instance.images.count() if self.instance.pk else 0
        removed_image_ids = [key.split('_')[2] for key in self.data.keys() if key.startswith('remove_image_') and self.data[key] == 'true']
        replaced_image_ids = [key.split('_')[1] for key in self.files.keys() if key.startswith('image_')]
        total_images = existing_images - len(removed_image_ids) - len(replaced_image_ids)

        if total_images < 1:
            self.add_error(None, "At least one image is required.")

        for key, img in self.files.items():
            if key.startswith('image_'):
                if img.content_type not in ['image/png', 'image/gif', 'image/jpeg', 'image/webp']:
                    self.add_error(None, f"{key}: Only PNG, GIF, WebP, or JPEG files are allowed.")

        return cleaned_data
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is None:
            raise forms.ValidationError("Price is required.")
        if price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

# ✅ Form for Product Variant (add price/stock validation here)
class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [ 'size', 'stock']

    def clean(self):
        cleaned_data = super().clean()
        size = cleaned_data.get('size')
     

        if not size :
            raise forms.ValidationError("size")

        return cleaned_data

   

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is None:
            raise forms.ValidationError("Stock is required.")
        if stock < 0:
            raise forms.ValidationError("Stock cannot be negative.")
        return stock

from django.forms import modelformset_factory

ProductVariantFormSet = modelformset_factory(
    ProductVariant,
    form=ProductVariantForm,
    extra=1,  # Number of empty forms shown for adding new variants
    can_delete=True  # Allow removing variants
)
