from PIL.Image import Resampling  # Import the Resampling enum
from django.utils.text import slugify
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from PIL import Image
import os
from django.core.files.base import ContentFile
from io import BytesIO
from decimal import Decimal
from django.utils import timezone
from PIL import Image, UnidentifiedImageError


User = get_user_model()





class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    slug = models.SlugField(max_length=255, unique=True, null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, default=0)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    is_active = models.BooleanField(default=True)
    is_listed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.parent:
            return f"{self.parent} → {self.name}"
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    description = models.TextField(default='No description provided')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    is_listed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    
    def __str__(self):
        return self.name

    @property
    def primary_image(self):
        first_image = self.images.first()
        return first_image.image.url if first_image else '/static/images/default-img.jpg'

    @property
    def discounted_price(self):
        base_price = self.price or 0

        # ✅ Get product discount from ProductOffer table (if exists and active)
        product_offer = self.productoffer_set.filter(is_active=True).first()
        product_discount = product_offer.discount_percent if product_offer else 0

        # ✅ Get category discount
        category_discount = self.category.discount_percent if self.category and self.category.discount_percent else 0

        # ✅ Take the best discount
        best_discount = min(max(product_discount, category_discount), 30)

        # ✅ Calculate final price
        if best_discount > 0:
            return round(base_price - (base_price * best_discount / 100), 2)

        return base_price

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    size = models.CharField(max_length=50, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    is_listed = models.BooleanField(default=True)
    
    def __str__(self):
        attrs = []
        if self.size:
            attrs.append(self.size)
        return f"{self.product.name} - {' / '.join(attrs)}"

    @property
    def primary_image(self):
        first_image = self.product.images.first()
        return first_image.image.url if first_image else '/static/images/default-img.jpg'

from datetime import date

class ProductOffer(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    discount_percent = models.PositiveIntegerField()
    valid_from = models.DateField()
    valid_to = models.DateField()
    is_active = models.BooleanField(default=True)

    def is_valid(self):
        today = date.today()
        return self.is_active and self.valid_from <= today <= self.valid_to

    def __str__(self):
        return f"{self.product.name} - {self.discount_percent}% off"
 



class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/')

    def save(self, *args, **kwargs):
        # ✅ Save the original first
        super().save(*args, **kwargs)

        img_path = self.image.path

        try:
            img = Image.open(img_path)
            img = img.convert("RGB")  # ✅ Ensure JPEG compatible

            # ✅ Crop and resize
            img = self.crop_center(img)
            img = img.resize((600, 600), Resampling.LANCZOS)

            # ✅ Save as JPEG
            img.save(img_path, format="JPEG", quality=90)

        except UnidentifiedImageError:
            # ✅ Delete invalid image file
            if os.path.exists(img_path):
                os.remove(img_path)
            raise ValueError("Invalid image file uploaded.")

    def crop_center(self, img):
        width, height = img.size
        new_edge = min(width, height)
        left = (width - new_edge) // 2
        top = (height - new_edge) // 2
        right = (width + new_edge) // 2
        bottom = (height + new_edge) // 2
        return img.crop((left, top, right, bottom))





class Wishlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    added_at = models.DateTimeField(auto_now_add=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('user', 'product','variant')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.email} - {self.product.name}"


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)  # 👈 Add this
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    
            


    def subtotal(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.quantity} x {self.product.name} ({self.user.email})"

    class Meta:
        unique_together = ('user', 'product', 'variant')  # 👈 ensure uniqueness per variant
        ordering = ['-added_at']

class ProductReview(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()  # e.g., 1 to 5
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # newest first

    def __str__(self):
        return f"{self.user} - {self.product} ({self.rating})"