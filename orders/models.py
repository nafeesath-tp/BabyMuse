# orders/models.py
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings   # For AUTH_USER_MODEL
from shop.models import ProductVariant
from user.models import CustomUser
from django.utils import timezone
# ──────────────── choices ──────────────────────────────────────────────
ORDER_STATUS = [
    ('Pending',    'Pending'),
    ('Processing', 'Processing'),
    ('Shipped',    'Shipped'),
    ('Delivered',  'Delivered'),
    ('Cancelled',  'Cancelled'),
    ('Returned',   'Returned'),      
]


class Order(models.Model):
   
    order_id = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    address = models.ForeignKey(
        'user.Address',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    applied_coupon = models.ForeignKey(
    'Coupon',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='orders'
)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='Pending')
    payment_method = models.CharField(max_length=30, default='COD')
    is_returned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)

    def update_total_price(self):
        self.total_price = sum(item.subtotal() for item in self.items.all())
        self.save()


    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_id:
            while True:
                order_id = uuid.uuid4().hex[:10].upper()
                if not Order.objects.filter(order_id=order_id).exists():
                    self.order_id = order_id
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_id} – {self.user.username}"


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ("COD", "Cash on Delivery"),
        ("Razorpay", "Razorpay"),
        ("Wallet", "Wallet"),  
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, default="pending") 
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.method} - {self.status}"




class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('shop.Product', on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    is_returned = models.BooleanField(default=False)
    return_reason = models.TextField(blank=True, null=True)
    is_return_requested = models.BooleanField(default=False) 

    def subtotal(self):
        return self.quantity * self.price


    def __str__(self):
        return f"{self.quantity} × {self.product} ({self.order.order_id})"
class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(
        max_length=10,
        choices=(('percent', 'Percent'), ('amount', 'Amount')),
        default='percent'
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=0)  # 0 = unlimited
    used_count = models.PositiveIntegerField(default=0)

    def is_valid(self):
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date and\
               (self.usage_limit == 0 or self.used_count < self.usage_limit)

    def __str__(self):
        return self.code
