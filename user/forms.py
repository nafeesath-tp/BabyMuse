from django import forms
from .models import CustomUser, Address
import re
from .widgets import CustomImageInput


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone', 'email', 'profile_image']
        widgets = {
            'profile_image': CustomImageInput(attrs={
                'class': 'w-full border px-4 py-2 rounded',
                'accept': 'image/*',
            })
        }

    def clean_first_name(self):
        value = self.cleaned_data['first_name'].strip()
        if len(value) < 3 or not value.isalpha():
            raise forms.ValidationError("Enter a valid first name.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data['last_name'].strip()
        if len(value) < 1 or not value.isalpha():
            raise forms.ValidationError("Enter a valid last name.")
        return value

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        # Skip email uniqueness check for the current user
        if self.instance and self.instance.email != email:
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError("This email is already in use.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise forms.ValidationError("Enter a valid 10-digit phone number.")
        return phone

    def clean_profile_image(self):
        image = self.cleaned_data.get('profile_image')
        if image:
            valid_types = ['image/jpeg', 'image/png', 'image/jpg']
            if hasattr(image, 'content_type') and image.content_type not in valid_types:
                raise forms.ValidationError("Only JPG, JPEG, or PNG images are allowed.")
        return image
    




    

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['name', 'phone', 'address_line', 'city', 'state', 'postal_code', 'is_default']

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 3 or not re.match(r'^[A-Za-z ]+$', name):
            raise forms.ValidationError("Enter a valid name (at least 3 letters, only letters and spaces).")
        return name

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        if not re.match(r'^[6-9]\d{9}$', phone):
            raise forms.ValidationError("Enter a valid 10-digit phone number starting with 6-9.")
        return phone
  

    def clean_address_line(self):
        address = self.cleaned_data['address_line'].strip()
        if len(address) < 5:
            raise forms.ValidationError("Address must be at least 5 characters long.")
        return address
    def clean_city(self):
        city = self.cleaned_data['city'].strip()
        if not re.match(r'^[A-Za-z ]+$', city):
            raise forms.ValidationError("Enter a valid city name (letters and spaces only).")
        return city

    # 5. Validate State
    def clean_state(self):
        state = self.cleaned_data['state'].strip()
        if not re.match(r'^[A-Za-z ]+$', state):
            raise forms.ValidationError("Enter a valid state name (letters and spaces only).")
        return state
    def clean_postal_code(self):
        
        postal_code = self.cleaned_data['postal_code'].strip()

    # Must be 6 digits
        if not re.match(r'^\d{6}$', postal_code):
            
            raise forms.ValidationError("Enter a valid 6-digit postal code.")

    # Reject common dummy or fake codes
        if postal_code in ['000000', '111111', '123456', '999999']:
            
            raise forms.ValidationError("This postal code is not valid.")

    # Optional: Check if starts with 0
        if postal_code.startswith('0'):
            
            raise forms.ValidationError("Postal code cannot start with 0.")

        return postal_code
