from django.urls import path
from . import views

app_name = 'shop'  

urlpatterns = [

    #  Shop Pages
    path('', views.shop_view, name='shop'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('my-orders/', views.my_orders_view, name='my_orders'),
    path("product/<int:product_id>/review/", views.submit_review, name="submit_review"),


    #  Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('ajax/add-to-wishlist/', views.ajax_add_to_wishlist,
         name='ajax_add_to_wishlist'),
    path('ajax/remove-from-wishlist/', views.ajax_remove_from_wishlist,
         name='ajax_remove_from_wishlist'),

    #  Cart
    path('cart/', views.cart_view, name='cart'),
    path('ajax/add-to-cart/', views.ajax_add_to_cart, name='ajax_add_to_cart'),
    path('remove-from-cart-ajax/', views.ajax_remove_from_cart,
         name='ajax_remove_from_cart'),
    path('cart/update/<int:product_id>/', views.update_cart_quantity, name='ajax_update_cart_quantity'),


]
