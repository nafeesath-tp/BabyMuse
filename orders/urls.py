
# orders/urls.py

from django.urls import path
from . import views
from .views import return_item_view


app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout_view, name="checkout"),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    path("success/<int:order_id>/", views.order_success_view, name="order_success"),
    
    
    path("my-orders/", views.my_orders_view, name="my_orders"),
    path("failure/<int:order_id>/", views.payment_failure_view, name="payment_failure"),


    path("order/<int:order_id>/", views.order_detail_view, name="order_detail"),
    
    path("order/item/cancel/<int:item_id>/", views.cancel_order_item_view, name="cancel_order_item"),

    path("order/<int:order_id>/return/", views.return_order_view, name="return_order"),
    path('order/item/<int:item_id>/return/', return_item_view, name='return_item'),
    path("order/<int:order_id>/invoice/", views.download_invoice_view, name="download_invoice"),
    path('razorpay/success/', views.razorpay_success, name='razorpay_success'),

]

