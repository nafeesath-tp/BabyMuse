from django.contrib import admin


from .models import Category,ProductImage

# Register your models here.
admin.site.register(Category)
# admin.site.register(Product)
admin.site.register(ProductImage)

from .models import ProductOffer

@admin.register(ProductOffer)
class ProductOfferAdmin(admin.ModelAdmin):
    list_display = ('product', 'discount_percent', 'valid_from', 'valid_to', 'is_active')

