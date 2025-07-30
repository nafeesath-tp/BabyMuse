from django.contrib import admin
from .models import Order, OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'status', 'total_price', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_id', 'user__email']


@admin.action(description="Mark selected items as returned")
def mark_items_as_returned(modeladmin, request, queryset):
    for item in queryset:
        if not item.is_returned:
            item.is_returned = True
            item.return_requested_at = timezone.now()
            item.save()

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price', 'is_returned']
    list_filter = ['is_returned']
    actions = [mark_items_as_returned]



