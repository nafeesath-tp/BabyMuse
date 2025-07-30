from django.urls import path
from . import views
from .views import toggle_user_status


app_name = 'admin_panel'

urlpatterns = [
    # Auth
     path('login/', views.custom_admin_login, name='custom_admin_login'),
     path('logout/', views.custom_admin_logout,
         name='custom_admin_logout'),
     path('forgot-password/', views.admin_forgot_password,
         name='admin_forgot_password'),

    # Dashboard & Profile
     path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
     path('profile/', views.admin_profile, name='admin_profile'),
     path('change-password/', views.change_admin_password,
         name='admin_change_password'),

    # Orders
     path('orders/', views.admin_orders, name='admin_orders'),
     path('orders/<int:order_id>/', views.admin_order_detail,
         name='admin_order_detail'),
     path('orders/item/accept-return/<int:item_id>/', views.admin_accept_return_item, name='admin_accept_return_item'),
     path('orders/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),


    # Products
     path('products/', views.admin_products, name='admin_products'),
     path('products/new/', views.admin_add_product, name='admin_add_product'),
     path('products/<int:product_id>/edit/',
         views.admin_edit_product, name='admin_edit_product'),
    
     path('products/<int:product_id>/toggle-list/', 
         views.toggle_product_list_status, name='toggle_product_list_status'),
     path('product/<int:product_id>/variants/', views.variant_list, name='variant_list'),
     path('product/<int:product_id>/variants/add/', views.add_variant, name='add_variant'),
     path('variant/<int:variant_id>/edit/', views.edit_variant, name='edit_variant'),
     path('variant/<int:variant_id>/toggle-list/', views.toggle_variant_list, name='toggle_variant_list'),



    # Categories
    path('categories/', views.category_list, name='admin_category_list'),
    path('categories/add/', views.add_category, name='admin_add_category'),
    path('categories/edit/<int:category_id>/',
         views.edit_category, name='admin_edit_category'),
    # urls.py
    path('categories/<int:category_id>/toggle/', 
         views.toggle_category_status, name='toggle_category_status'),


    # Customers
    path('customers/', views.admin_customer_list, name='admin_customer_list'),
    path('customers/<int:customer_id>/',
         views.admin_view_customer, name='admin_view_customer'),
    path('users/<int:user_id>/toggle/',
         toggle_user_status, name='toggle_user_status'),

     path('coupons/', views.coupon_list, name='coupon_list'),
     path('coupons/add/', views.add_coupon, name='add_coupon'),
     path('coupons/edit/<int:coupon_id>/', views.edit_coupon, name='edit_coupon'),
     path('coupons/delete/<int:coupon_id>/', views.delete_coupon, name='delete_coupon'),

     path('sales-report/', views.sales_report_view, name='sales_report'),
     path('sales-report/download/pdf/', views.download_sales_report_pdf, name='download_sales_report_pdf'),
     path('sales-report/download/excel/', views.download_sales_report_excel, name='download_sales_report_excel'),
     
   
]
