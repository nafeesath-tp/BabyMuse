from django.contrib.auth import login
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib import messages
from .models import CustomUser 
import re
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from .models import EmailOTP
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth import update_session_auth_hash
from .models import Address
from .forms import ProfileForm
from .forms import AddressForm
from django.utils.http import urlencode
from django.http import HttpResponseRedirect
from django.views.decorators.cache import never_cache
from .models import Profile
from .utils import generate_and_send_otp
from django.core.files.uploadedfile import InMemoryUploadedFile
import io
from .models import Wallet



User = get_user_model()


def user_login(request):
    next_url = request.GET.get('next', '')  
    # Show toast before login form if redirected
    if next_url:
        if 'wishlist' in next_url:
            messages.warning(
                request, "🔒 Please log in to access your wishlist.")
        elif 'cart' in next_url:
            messages.warning(request, "🛒 Please log in to access your cart.")

    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Both username and password are required.")
            return redirect('user:user_login')

        auth_user = authenticate(username=username, password=password)
        if auth_user:
            login(request, auth_user)

            # Safe redirect (prevents open redirect attacks)
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            else:
                return redirect('home')
        else:
            messages.error(request, "Invalid credentials")

    return render(request, 'user/login.html', {'next': next_url})


def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[@$!%*?&]", password):
        return False
    return True


def register_email(request):
    """Step 1: ask for e‑mail and send OTP"""
    if request.method == 'POST':
        email = request.POST.get('email').strip()

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Please log in.")
            return redirect('user:user_login')

        send_otp(email)
        request.session['email'] = email
        request.session['flow']  = 'signup'
        # 🔑  redirect to the *real* URL name for OTP page
        return redirect('user:verify_signup_otp')

    return render(request, 'user/register_email.html')


def register_otp_verify(request):
    email = request.session.get('email')
    if not email:
        messages.error(request, "Session expired. Start again.")
        return redirect('user:register_email')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        try:
            otp_record = EmailOTP.objects.get(email=email)

            # Check if OTP is expired
            if timezone.now() - otp_record.created_at > timedelta(seconds=60):
                messages.error(request, "OTP expired. Please resend OTP.")
                  # ✅ Stay on OTP screen

            if otp_record.otp == entered_otp:
                request.session['is_verified'] = True
                return redirect('user:create_account')

            messages.error(request, "Invalid OTP. Please enter the correct OTP.")

        except EmailOTP.DoesNotExist:
            messages.error(request, "OTP not sent. Start again.")
            return redirect('user:register_email')

    return render(request, 'user/verify_signupotp.html')


import re
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth import login
from django.contrib.auth.models import User

def create_account(request):
    email = request.session.get('email')
    is_verified = request.session.get('is_verified')

    if not email or not is_verified:
        messages.error(request, "Unauthorized access.")
        return redirect('user:register_email')

    if request.method == 'POST':
        username = request.POST.get('username').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Basic required field validation
        if not username or not password or not confirm_password:
            messages.error(request, "All fields are required.")
            return redirect('user:create_account')

        # Username validations
        if len(username) < 4 or len(username) > 20:
            messages.error(request, "Username must be 4-20 characters long.")
            return redirect('user:create_account')
        if not re.match(r'^[A-Za-z0-9_]+$', username):
            messages.error(request, "Username can only contain letters, numbers, and underscores.")
            return redirect('user:create_account')
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('user:create_account')

        # Password validations
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('user:create_account')
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect('user:create_account')
        if not re.search(r'[A-Z]', password):
            messages.error(request, "Password must contain at least one uppercase letter.")
            return redirect('user:create_account')
        if not re.search(r'[a-z]', password):
            messages.error(request, "Password must contain at least one lowercase letter.")
            return redirect('user:create_account')
        if not re.search(r'[0-9]', password):
            messages.error(request, "Password must contain at least one digit.")
            return redirect('user:create_account')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            messages.error(request, "Password must contain at least one special character (!@#$%^&* etc).")
            return redirect('user:create_account')

        # Email uniqueness check
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already used.")
            return redirect('user:register_email')

        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)

        # Clear session
        request.session.flush()
        messages.success(request, "Account created successfully!")
        return redirect('user:account_success')

    return render(request, 'user/create_account.html')


def account_success(request):
    return render(request, 'user/account_success.html')

def user_logout(request):
    logout(request)
    return redirect('home')
def forgot_password_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if not User.objects.filter(email=email).exists():
            messages.error(request, "No account found with this email.")
            return redirect('user:forgot_password')

        request.session['email'] = email
        request.session['flow'] = 'forgot'  # <--- Important
        send_otp(email)
        return redirect('user:verify_otp')

    return render(request, 'user/forgot_password.html')



def send_otp(email):
    otp_obj, _ = EmailOTP.objects.get_or_create(email=email)
    otp_obj.generate_otp()
    otp_obj.created_at = timezone.now()  
    otp_obj.save()

   

   
    send_mail(
        subject='Your OTP for BabyMuse Signup',
        message=f'Your OTP is {otp_obj.otp}',
        from_email='tpnafeesath90@gmail.com',
        recipient_list=[email],
    )


def otp_signup_request(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        send_otp(email)
        request.session['email'] = email
        return redirect('user:verify_otp')
    return render(request, 'user/otp_request.html')


def otp_verify(request):
    email = request.session.get('email')
    otp_record = None

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        try:
            otp_record = EmailOTP.objects.get(email=email)
            if otp_record.otp == entered_otp:
                return redirect('user:set_password')
            else:
                messages.error(request, 'Invalid OTP')
        except EmailOTP.DoesNotExist:
            messages.error(request, 'No OTP sent. Please try again.')
            return redirect('user:otp_signup_request')

    if otp_record and timezone.now() - otp_record.created_at > timedelta(minutes=5):
        messages.error(request, 'OTP expired. Please request again.')
        otp_record.delete()
        return redirect('user:otp_signup_request')

    return render(request, 'user/otp_verify.html')


def resend_otp(request):
    email = request.session.get('email')
    if email:
        send_otp(email)
        messages.success(request, 'OTP resent successfully!')
    return redirect('user:verify_signup_otp')


def set_password(request):
    email = request.session.get('email')
    flow = request.session.get('flow')  # <--- track whether it's signup or forgot

    if not email or not flow:
        messages.error(request, 'Session expired or email not found.')
        return redirect('user:signup_request')

    if request.method == 'POST':
        password = request.POST.get('password')
        confirm = request.POST.get('confirm_password')

        if password != confirm:
            messages.error(request, 'Passwords do not match.')
            return redirect('user:set_password')

        if not is_strong_password(password):
            messages.error(request, "Weak password.")
            return redirect('user:set_password')

        if flow == 'signup':
            username = request.session.get('username', '').strip()
            if User.objects.filter(email=email).exists():
                messages.error(request, 'User already exists.')
                return redirect('user:user_login')

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            messages.success(request, 'Account created successfully.')
            return redirect('home')

        elif flow == 'forgot':
            try:
                user = User.objects.get(email=email)
                user.set_password(password)
                user.save()
                request.session.flush()
                messages.success(request, 'Password reset successful. Please login.')
                return redirect('user:user_login')
            except User.DoesNotExist:
                messages.error(request, 'No user found for this email.')
                return redirect('user:forgot_password')

    return render(request, 'user/set_password.html')


@login_required
def profile_view(request):
    return render(request, 'user/profile.html', {'user': request.user})



@login_required
def change_password(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not request.user.check_password(old_password):
            messages.error(request, "Old password is incorrect.")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
        elif len(new_password) < 6:
            messages.error(
                request, "New password must be at least 6 characters long.")
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(
                request, request.user)  # Keep user logged in
            messages.success(request, "Password updated successfully.")
            return redirect('user:profile')

    return render(request, 'user/change_password.html')

def sign_up(request):
    return render(request,'user/register.html')
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ProfileForm














import logging
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os

# Set up logging
logger = logging.getLogger(__name__)

@login_required
def edit_profile(request):
    user = request.user
    original_email = user.email
    logger.debug(f"User {user.username} accessing edit_profile: method={request.method} email = {user.email}")

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        logger.debug(f"Form data: {request.POST}, Files: {request.FILES}")
        if form.is_valid():
            new_email = form.cleaned_data['email']
            logger.debug(f"Current email: {original_email}, New email: {new_email}")

            # Check if email has changed
            if new_email != original_email:
                # Store form data in session
                request.session['pending_email'] = new_email
                request.session['form_data'] = request.POST.dict()
                
                # Handle file upload by saving temporarily
                if 'profile_image' in request.FILES:
                    file = request.FILES['profile_image']
                    file_name = f"temp_profile_image_{user.id}_{new_email.replace('@', '_')}"
                    file_path = default_storage.save(f'temp/{file_name}', ContentFile(file.read()))
                    request.session['temp_profile_image'] = file_path
                    logger.debug(f"Temporary file saved: {file_path}")
                else:
                    request.session['temp_profile_image'] = None
                    logger.debug("No profile image uploaded")

                # Send OTP to new email
                try:
                    generate_and_send_otp(new_email)
                    messages.info(request, "An OTP has been sent to your new email. Please verify to apply changes.")
                    logger.debug(f"OTP sent to {new_email}, redirecting to verify_email_change")
                    return redirect('user:verify_email_change')
                except Exception as e:
                    logger.error(f"Failed to send OTP to {new_email}: {str(e)}")
                    messages.error(request, "Failed to send OTP. Please try again.")
                    return redirect('user:edit_profile')

            # If email hasn't changed, save other fields directly
            logger.debug("Email unchanged, saving form directly")
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('user:profile')

        else:
            logger.debug(f"Form invalid: {form.errors}")
            # If form is invalid, re-render with errors
            return render(request, 'user/edit_profile.html', {'form': form})

    else:
        form = ProfileForm(instance=user)
        logger.debug("Rendering edit_profile form for GET request")

    return render(request, 'user/edit_profile.html', {'form': form})

@login_required
def verify_email_change(request):
    user = request.user
    pending_email = request.session.get('pending_email')
    logger.debug(f"User {user.username} accessing verify_email_change: pending_email={pending_email}")

    if not pending_email:
        logger.error("No pending email in session")
        messages.error(request, "No email change request found.")
        return redirect('user:edit_profile')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        logger.debug(f"Entered OTP: {entered_otp}")

        try:
            otp_record = EmailOTP.objects.get(email=pending_email)
            logger.debug(f"OTP record found: {otp_record.otp}, created_at={otp_record.created_at}")

            if otp_record.otp != entered_otp:
                logger.warning("Invalid OTP entered")
                messages.error(request, "Invalid OTP.")
                return redirect('user:verify_email_change')

            if timezone.now() - otp_record.created_at > timedelta(minutes=5):
                logger.warning("OTP expired")
                otp_record.delete()
                messages.error(request, "OTP expired. Try again.")
                return redirect('user:edit_profile')

            # OTP is valid — update user email and other fields
            form_data = request.session.get('form_data', {})
            logger.debug(f"Form data from session: {form_data}")

            # Handle file upload
            temp_file_path = request.session.get('temp_profile_image')
            if temp_file_path:
                with default_storage.open(temp_file_path, 'rb') as temp_file:
                    form_data = form_data.copy()
                    request.FILES['profile_image'] = InMemoryUploadedFile(
                        temp_file,
                        None,
                        os.path.basename(temp_file_path),
                        'image/jpeg',
                        temp_file.size,
                        None
                    )
                logger.debug(f"Restored temporary file: {temp_file_path}")

            # Create a new form instance with the stored data
            form = ProfileForm(form_data, request.FILES if temp_file_path else None, instance=user)
            if form.is_valid():
                logger.debug("Form is valid, updating user email and fields")
                # Update email
                user.email = pending_email
                user.save()

                # Save other fields
                form.save()

                # Clean up temporary file and session
                if temp_file_path:
                    default_storage.delete(temp_file_path)
                    logger.debug(f"Deleted temporary file: {temp_file_path}")
                otp_record.delete()
                for key in ['pending_email', 'form_data', 'temp_profile_image']:
                    request.session.pop(key, None)
                logger.debug("Session cleaned up")

                messages.success(request, "Email verified and profile updated successfully!")
                return redirect('user:profile')

            else:
                logger.error(f"Form invalid after OTP verification: {form.errors}")
                messages.error(request, "Invalid form data. Please try again.")
                return redirect('user:edit_profile')

        except EmailOTP.DoesNotExist:
            logger.error("OTP record not found")
            messages.error(request, "OTP not found. Try again.")
            return redirect('user:edit_profile')

    logger.debug("Rendering verify_email_change.html")
    return render(request, 'user/verify_email_change.html', {'email': pending_email})

@never_cache
@login_required
def address_list(request):
    addresses = request.user.address_set.all()
    return render(request, 'user/addresses.html', {'addresses': addresses})


@never_cache
@login_required
def add_address(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        if request.user.address_set.count() >= 5:
            messages.error(request, "You can only save up to 5 addresses.")
            return redirect('user:address_list')

        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user

            if form.cleaned_data.get('is_default'):
                request.user.address_set.update(is_default=False)

            address.save()

            messages.success(request, "Address added!")
            return redirect(next_url or 'user:address_list')
    else:
        form = AddressForm()

    return render(request, 'user/add_address.html', {
        'form': form,
        'next': next_url
    })


@never_cache
@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            if form.cleaned_data.get('is_default'):
                request.user.address_set.update(is_default=False)
            form.save()
            messages.success(request, "Address updated.")
            return redirect(next_url or 'user:address_list')
    else:
        form = AddressForm(instance=address)

    return render(request, 'user/edit_address.html', {'form': form, 'next': request.GET.get('next')})

@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    messages.success(request, "Address deleted.")
    return redirect('user:address_list')
@login_required
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user) 
    transactions = wallet.transactions.all().order_by("-date")
    return render(request, "user/wallet.html", {
        "wallet": wallet,
        "transactions": transactions
    })


