from django.contrib import admin
from shop.models import Product, ProductVariant  # import from the 'shop' app

class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1  # how many empty variant rows to show by default

class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_listed']
    inlines = [ProductVariantInline]  # show variants inline in Product admin

admin.site.register(Product, ProductAdmin)
admin.site.register(ProductVariant)  # optional: only if you want it listed separately
