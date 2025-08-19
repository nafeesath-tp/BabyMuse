from django.urls import path
from . import views
app_name = 'user'

urlpatterns = [
   
   path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('otp-signup/', views.otp_signup_request, name='signup_request'),
    path('verify-otp/', views.otp_verify, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('set-password/', views.set_password, name='set_password'),
    path('change-password/', views.change_password, name='change_password'),
    path('forgot/', views.forgot_password_request, name='forgot_password'),
    path('register/', views.register_email, name='register_email'),
    path('verify-signup-otp/', views.register_otp_verify, name='verify_signup_otp'),
    path('create-account/', views.create_account, name='create_account'),
    path('account-success/', views.account_success, name='account_success'),
    path("wallet/", views.wallet_view, name="wallet"),

    # 🆕 Edit profile (separate page from viewing)
    path('profile/', views.profile_view, name='profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('verify-email-change/', views.verify_email_change, name='verify_email_change'),
  



    # 🆕 Address Management
    path('address/', views.address_list, name='address_list'),
    path('address/add/', views.add_address, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('address/delete/<int:address_id>/', views.delete_address, name='delete_address'),





]
