import csv
import io
import logging
import pandas as pd
import pytz
import random
import re
import string

from decimal import Decimal
from datetime import datetime, timedelta,timezone as dt_timezone
from io import BytesIO
from PIL import Image, UnidentifiedImageError
from datetime import timezone

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Sum, Q, OuterRef, Subquery, Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph

from shop.models import Product, Category, ProductImage, ProductOffer
from shop.forms import CategoryForm
from orders.models import Order, OrderItem, Coupon
from user.models import Wallet
from .decorators import admin_login_required
from .forms import ProductForm, ProductVariantFormSet, ProductVariant
from .models import AdminUser



logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata") 
User = get_user_model()

if not AdminUser.objects.filter(username='admin123').exists():
    admin = AdminUser(
        username='admin123',
        password=make_password('admin123'),
        email='tpnafeesath90@gmail.com'
    )
    admin.save()




def custom_admin_login(request):
    if request.session.get('admin_id'):
        return redirect('admin_panel:admin_dashboard')
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        try:
            admin = AdminUser.objects.get(username=username)
            if check_password(password, admin.password):
                request.session['admin_id'] = admin.id
                return redirect('admin_panel:admin_dashboard')
            else:
                messages.error(request, "Incorrect password")
        except AdminUser.DoesNotExist:
            messages.error(request, "Admin user not found")
    return render(request, 'admin_panel/login.html')


def generate_temp_password(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@admin_login_required
def admin_forgot_password(request):
    if request.method == 'POST':
        email = request.POST['email']
        try:
            admin = AdminUser.objects.get(email=email)
            temp_password = generate_temp_password()
            admin.password = make_password(temp_password)
            admin.save()

            send_mail(
                'BabyMuse Admin - Temporary Password',
                f'Your temporary password is: {temp_password}\nPlease login and change it immediately.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            messages.success(request, "Temporary password sent to your email.")
            return redirect('admin_panel:custom_admin_login')
        except AdminUser.DoesNotExist:
            messages.error(request, "Email not found.")
    return render(request, 'admin_panel/forgot_password.html')


@admin_login_required
def admin_dashboard(request):
    # Get filter type from query params (default = yearly)
    filter_type = request.GET.get("filter", "yearly")
    logger.debug(f"Filter type: {filter_type}")

    # Determine the truncation function and status filter based on filter type
    if filter_type == "daily":
        sales_data = (
            Order.objects.filter(status="Delivered")
            .annotate(period=TruncDay("created_at"))
            .values("period")
            .annotate(total_sales=Sum("total_price"))
            .order_by("period")
        )
    elif filter_type == "weekly":
        sales_data = (
            Order.objects.filter(status="Delivered")
            .annotate(period=TruncWeek("created_at"))
            .values("period")
            .annotate(total_sales=Sum("total_price"))
            .order_by("period")
        )
    elif filter_type == "monthly":
        sales_data = (
            Order.objects.filter(status="Delivered")
            .annotate(period=TruncMonth("created_at"))
            .values("period")
            .annotate(total_sales=Sum("total_price"))
            .order_by("period")
        )
    else:  # yearly
        sales_data = (
            Order.objects.filter(status="Delivered")
            .annotate(period=TruncYear("created_at"))
            .values("period")
            .annotate(total_sales=Sum("total_price"))
            .order_by("period")
        )

    # Convert sales data to chart-friendly format
    chart_labels = [entry["period"].strftime("%d %b %Y") for entry in sales_data]
    chart_data = [float(entry["total_sales"] or 0) for entry in sales_data]

    # Dashboard summary stats
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_revenue = (
        Order.objects.filter(status="Delivered").aggregate(total=Sum("total_price"))["total"] or 0
    )

    # Latest orders
    latest_orders = Order.objects.order_by("-created_at")[:5]

    # ✅ Best selling products (top 10) with image + fallback
    best_selling_products_raw = (
        OrderItem.objects.filter(order__status="Delivered")
        .values("product", "product__name", "product__category")  # include ids
        .annotate(total_sold=Sum("quantity"))
        .order_by("-total_sold")[:10]
    )

    best_selling_products = []
    for item in best_selling_products_raw:
        product = Product.objects.get(id=item["product"])
        category = Category.objects.get(id=item["product__category"])

        # fallback logic
        if getattr(product, "primary_image", None):
            image = product.primary_image.url if hasattr(product.primary_image, "url") else product.primary_image
        elif getattr(category, "image", None):
            image = category.image.url if hasattr(category.image, "url") else category.image
        else:
            image = None  # template will use static placeholder

        best_selling_products.append({
            "name": item["product__name"],
            "total_sold": item["total_sold"],
            "image": image,
        })

    # ✅ Best selling categories (top 10) with image
    best_selling_categories_raw = (
    OrderItem.objects.filter(order__status="Delivered")
    .values("product__category__name")
    .annotate(total_sold=Sum("quantity"))
    .order_by("-total_sold")[:10]
)

    best_selling_categories = [
    {"name": item["product__category__name"], "total_sold": item["total_sold"]}
    for item in best_selling_categories_raw
]

    return render(
        request,
        "admin_panel/dashboard.html",
        {
            "filter_type": filter_type,
            "chart_labels": chart_labels,
            "chart_data": chart_data,
            "total_users": total_users,
            "total_products": total_products,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "latest_orders": latest_orders,
            "best_selling_products": best_selling_products,
            "best_selling_categories": best_selling_categories,
        },
    )

@admin_login_required
def admin_profile(request):
    admin_user = get_object_or_404(AdminUser, id=request.session['admin_id'])
    return render(request, 'admin_panel/profile.html', {'admin_user': admin_user})


@admin_login_required
def change_admin_password(request):
    admin_user = AdminUser.objects.get(id=request.session['admin_id'])
    if request.method == "POST":
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not check_password(current_password, admin_user.password):
            messages.error(request, "Current password is incorrect")
        elif new_password != confirm_password:
            messages.error(request, "New passwords do not match")
        else:
            admin_user.password = make_password(new_password)
            admin_user.save()
            messages.success(request, "Password updated successfully")
            return redirect('admin_panel:admin_profile')
    return render(request, 'admin_panel/change_password.html')


# product management


@admin_login_required
def admin_products(request):
    products = Product.objects.all().order_by('-created_at')

    paginator = Paginator(products, 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'admin_panel/products.html', {
        'products': products,

        'page_obj': page_obj
    })


@admin_login_required
def admin_add_product(request):
    categories = Category.objects.filter(is_listed=True)
    category_discount = 0  # Default
    final_price = 0
    product_discount = 0
    base_price = 0

    if request.method == 'POST':
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        description = request.POST.get('description')
        price = request.POST.get('price')
        discount = request.POST.get('discount_percent')
        images = request.FILES.getlist('images')

        # If category selected, get its discount
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                category_discount = category.discount_percent or 0
            except ObjectDoesNotExist:
                category = None

        product_discount = float(discount) if discount else 0
        base_price = float(price) if price else 0
        best_discount = max(product_discount, category_discount)
        final_discount = min(best_discount, 30)
        final_price = round(base_price - (base_price * final_discount / 100), 2) if base_price else 0

        # ✅ Basic validation
        if not all([name, category_id, description, price]):
            messages.error(request, "Please fill out all required fields.")
            return render(request, 'admin_panel/add_product.html', {
                'categories': categories,
                'category_discount': category_discount,
                'product_discount': product_discount,
                'discounted_price': final_price
            })

        if len(images) != 3:
            messages.error(request, "Please upload exactly 3 images.")
            return render(request, 'admin_panel/add_product.html', {
                'categories': categories,
                'category_discount': category_discount,
                'product_discount': product_discount,
                'discounted_price': final_price
            })

      
        product = Product.objects.create(
            name=name,
            category=category,
            description=description,
            price=price
        )

        
        if discount and float(discount) > 0:
            discount_value = float(discount)

            if discount_value > 30:
                messages.error(request, "Product discount cannot exceed 30%.")
                return render(request, 'admin_panel/add_product.html', {
                    'categories': categories,
                    'category_discount': category_discount,
                    'product_discount': product_discount,
                    'discounted_price': final_price
                })

            
            ProductOffer.objects.create(
                product=product,
                discount_percent=Decimal(discount_value),
                is_active=True
            )

       
        for image_file in images:
            ProductImage.objects.create(product=product, image=image_file)

        messages.success(request, "Product added successfully!")
        return redirect('admin_panel:admin_products')

    return render(request, 'admin_panel/add_product.html', {
        'categories': categories,
        'category_discount': category_discount,
        'product_discount': product_discount,
        'discounted_price': final_price
    })



@admin_login_required
def admin_edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    max_images = 3

    if request.method == 'POST':
        # ✅ Validate discount before saving
        discount_str = request.POST.get("discount_percent")

        if discount_str:
            try:
                discount_value = int(discount_str)
                if discount_value > 30:  # ✅ Validation: Cannot exceed 30%
                    messages.error(request, "Product discount cannot exceed 30%.")
                    return redirect('admin_panel:admin_edit_product', product_id=product.id)
            except ValueError:
                messages.error(request, "Invalid discount value.")
                return redirect('admin_panel:admin_edit_product', product_id=product.id)

        # ✅ Handle Product Offer
        offer = ProductOffer.objects.filter(product=product).first()
        if discount_str:
            discount_value = int(discount_str)
            if offer:
                offer.discount_percent = discount_value
                offer.save()
            else:
                ProductOffer.objects.create(
                    product=product,
                    discount_percent=discount_value,
                    valid_from=timezone.now().date(),
                    valid_to=(timezone.now() + timedelta(days=30)).date(),
                    is_active=True
                )

        # ✅ Update Product Details
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully.")

        # ✅ Handle Product Images
        images = list(product.images.all())
        existing_count = len(images)

        for i in range(1, max_images + 1):
            remove_key = f'remove_image_{i}'
            file_key = f'image_input_{i}'
            image_obj = images[i - 1] if i <= existing_count else None

            # ✅ Remove Image
            if request.POST.get(remove_key) == 'true' and image_obj:
                image_obj.delete()

            # ✅ Replace or Add Image
            elif file_key in request.FILES:
                uploaded_image = request.FILES[file_key]

                # ✅ Validate image before saving
                try:
                    img = Image.open(uploaded_image)
                    img.verify()  # Validate image integrity
                except UnidentifiedImageError:
                    messages.error(request, f"Invalid image uploaded for {file_key}.")
                    continue  # Skip this file

                if image_obj:
                    image_obj.image = uploaded_image
                    image_obj.save()  # Cropping/resizing happens here
                else:
                    ProductImage.objects.create(product=product, image=uploaded_image)

        return redirect('admin_panel:admin_products')

    else:
        form = ProductForm(instance=product)

    # ✅ Ensure 3 image slots for template
    images = list(product.images.all())
    while len(images) < max_images:
        images.append(None)

    # ✅ Get categories
    categories = Category.objects.filter(parent__isnull=True, is_listed=True).prefetch_related('subcategories')

    # ✅ Discount values
    offer = ProductOffer.objects.filter(product=product).first()
    product_discount = offer.discount_percent if offer else 0
    category_discount = product.category.discount_percent if product.category else 0
    final_price = product.discounted_price

    return render(request, 'admin_panel/edit_product.html', {
        'form': form,
        'product': product,
        'categories': categories,
        'max_images': max_images,
        'image_slots': images,
        'product_discount': product_discount,
        'category_discount': category_discount,
        'discounted_price': final_price,
    })

def variant_list(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = ProductVariant.objects.filter(product=product)
    return render(request, 'admin_panel/variant_list.html', {'product': product, 'variants': variants})

@require_POST
def add_variant(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    size = request.POST.get('size')
    stock = request.POST.get('stock')
    if size and stock:
        ProductVariant.objects.create(product=product, size=size, stock=int(stock))
    return redirect('admin_panel:variant_list', product_id=product.id)
def edit_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    if request.method == 'POST':
        variant.size = request.POST.get('size')
        variant.stock = request.POST.get('stock')
        variant.save()
        return redirect('admin_panel:variant_list', product_id=variant.product.id)
    return render(request, 'admin_panel/edit_variant.html', {'variant': variant})

def toggle_variant_list(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    variant.is_listed = not variant.is_listed
    variant.save()
    return redirect('admin_panel:variant_list', product_id=variant.product.id)


# category Management

@admin_login_required
def category_list(request):
    categories = Category.objects.all()
    paginator = Paginator(categories, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/category_list.html', {'page_obj': page_obj})

@admin_login_required
def add_category(request):

    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully.')
            return redirect('admin_panel:admin_category_list')
    else:
        form = CategoryForm()
    categories = Category.objects.filter(
        parent__isnull=True)

    return render(request, 'admin_panel/add_category.html', {'form': form, 'categories': categories})


@admin_login_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('admin_panel:admin_category_list')
    else:
        form = CategoryForm(instance=category)
    
    categories = Category.objects.filter(parent__isnull=True).exclude(id=category.id)
    return render(request, 'admin_panel/edit_category.html', {'form': form, 'categories': categories})

@admin_login_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.delete()
    messages.success(request, 'Category deleted.')
    return redirect('admin_panel:admin_category_list')

# customer management

@admin_login_required
def admin_customer_list(request):
    query = request.GET.get('q', '')
    customers = User.objects.filter(is_staff=False).order_by('-date_joined')
    if query:
        customers = customers.filter(Q(username__icontains=query) | Q(
            email__icontains=query) | Q(phone__icontains=query))
    paginator = Paginator(customers, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/customer_list.html', {'page_obj': page_obj, 'query': query, 'customers': customers})


@admin_login_required
def admin_view_customer(request, customer_id):
    customer = get_object_or_404(User, id=customer_id, is_staff=False)
    return render(request, 'admin_panel/view_customer.html', {'customer': customer})


def custom_admin_logout(request):
    request.session.flush()
    return redirect('admin_panel:custom_admin_login')


@require_POST
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save()
    status = "unblocked" if user.is_active else "blocked"
    messages.success(request, f"User {user.username} has been {status}.")
    return redirect('admin_panel:admin_customer_list')


@admin_login_required
@require_POST
def toggle_product_list_status(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_listed = not product.is_listed
    product.save()
    status = "listed" if product.is_listed else "unlisted"
    messages.success(request, f"Product '{product.name}' has been {status}.")
    return redirect('admin_panel:admin_products')


@admin_login_required
@require_POST
def toggle_category_status(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.is_listed = not category.is_listed
    category.save()
    status = "listed" if category.is_listed else "unlisted"
    messages.success(request, f"Category '{category.name}' has been {status}.")
    return redirect('admin_panel:admin_category_list')

# order management
@admin_login_required
def admin_orders(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    orders = Order.objects.all()

    if query:
        orders = orders.filter(Q(order_id__icontains=query)
                               | Q(user__name__icontains=query))
    if status_filter:
        orders = orders.filter(status__iexact=status_filter)

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'
        writer = csv.writer(response)
        writer.writerow(['Order ID', 'User', 'Amount',
                        'Status', 'Payment Method', 'Date'])
        for order in orders:
            writer.writerow([order.order_id, order.user.name, order.total_price, order.status,
                            order.payment_method, order.created_at.strftime('%Y-%m-%d %H:%M')])
        return response

    paginator = Paginator(orders.order_by('-created_at'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/orders.html', {'page_obj': page_obj, 'query': query,'orders': orders, 'status_filter': status_filter})


logger = logging.getLogger(__name__)


@admin_login_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderItem.objects.filter(order=order)

    
    for item in order_items:
        if item.variant.size:
            item.variant_details = f"Size: {item.variant.size}"
        else:
            item.variant_details = "No variant"
        item.total_price = item.quantity * item.price

   
    return_items = [item for item in order_items if item.is_return_requested]

    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = ['Pending', 'Shipped', 'Delivered', 'Cancelled', 'Return accepted']
        if new_status in valid_statuses:
            if new_status == 'Cancelled' and order.status not in ['Pending', 'Shipped']:
                messages.error(request, f"Order #{order.order_id} cannot be cancelled in its current status.")
            else:
                if new_status == 'Return accepted':
                    order.is_returned = True
                order.status = new_status
                order.save()
                messages.success(request, f"Order #{order.order_id} status updated to {new_status}.")
        else:
            messages.error(request, "Invalid status selected.")
        return redirect('admin_panel:admin_order_detail', order_id=order.id)

    return render(request, 'admin_panel/order_details.html', {
        'order': order,
        'order_items': order_items,
        'return_items': return_items, 
    })

@admin_login_required
def admin_accept_return_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id)

    if item.order.status != 'Delivered':
        messages.error(request, "Only delivered orders can be returned.")
        return redirect('admin_panel:admin_order_detail', order_id=item.order.id)

    if not item.is_return_requested:
        messages.warning(request, "Return not requested by user.")
        return redirect('admin_panel:admin_order_detail', order_id=item.order.id)

    if item.is_returned:
        messages.info(request, "This item is already marked as returned.")
        return redirect('admin_panel:admin_order_detail', order_id=item.order.id)

    # Mark as returned
    item.is_returned = True
    item.save(update_fields=["is_returned"])

    # Update stock
    item.variant.stock += item.quantity
    item.variant.save(update_fields=["stock"])

    
    all_items = OrderItem.objects.filter(order=item.order)
    wallet, _ = Wallet.objects.get_or_create(user=item.order.user)

    total_order_amount = sum(i.price * i.quantity for i in all_items)
    total_paid = item.order.total_paid

    
    refunded_so_far = sum(i.refund_amount for i in all_items if i.id != item.id)

    if all(i.is_returned for i in all_items):
        # Full order returned
        refund_amount = total_paid - refunded_so_far  # remaining amount
        item.order.status = 'Return accepted'
        item.order.save(update_fields=["status"])
    else:
        # Partial return with proportional discount
        if total_order_amount > 0:
            proportion = (item.price * item.quantity) / total_order_amount
            refund_amount = (proportion * total_paid) - item.refund_amount
            refund_amount = max(refund_amount, 0)
        else:
            refund_amount = item.price * item.quantity

    # Update item refund_amount
    item.refund_amount = refund_amount
    item.save(update_fields=["refund_amount"])

    # Credit wallet
    wallet.credit(refund_amount, source=f"Refund for Item/Order #{item.order.id}")

    messages.success(
        request,
        f"Return accepted for '{item.variant.product.name}'. "
        f"Stock updated and ₹{refund_amount:.2f} credited to wallet."
    )
    return redirect('admin_panel:admin_order_detail', order_id=item.order.id)


@admin_login_required
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['Pending', 'Shipped', 'Delivered', 'Cancelled', 'Return accepted']:  # optional: validate
            order.status = new_status
            order.save(update_fields=['status'])
            messages.success(request, f"Order status updated to {new_status}")
        else:
            messages.error(request, "Invalid status selected.")
    
    return redirect('admin_panel:admin_order_detail', order_id=order.id)


@admin_login_required
def coupon_list(request):
    coupons = Coupon.objects.all().order_by('-id')
    return render(request, 'admin_panel/coupon_list.html', {'coupons': coupons})
@admin_login_required
def add_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('code').strip().upper()
        discount_type = request.POST.get('discount_type')
        discount_value = Decimal(request.POST.get('discount_value') or 0)
        min_order_amount = Decimal(request.POST.get('min_order_amount') or 0)
        start_date = request.POST.get('start_date')  # ISO format
        end_date = request.POST.get('end_date')
        usage_limit = request.POST.get('usage_limit')

        # ✅ Check if coupon already exists
        if Coupon.objects.filter(code=code).exists():
            messages.error(request, "Coupon code already exists.")
            return redirect('admin_panel:add_coupon')

        # ✅ Validate dates
        try:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=dt_timezone.utc)
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=dt_timezone.utc)
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('admin_panel:add_coupon')

        if start_dt > end_dt:
            messages.error(request, "Start date cannot be after end date.")
            return redirect('admin_panel:add_coupon')

        # ✅ Validation depending on discount type
        if discount_type == "percent":
            if discount_value <= 0 or discount_value > 100:
                messages.error(request, "Percentage discount must be between 1% and 100%.")
                return redirect('admin_panel:add_coupon')

        elif discount_type == "amount":
            if min_order_amount > 0:
                max_allowed = (min_order_amount * Decimal("0.10"))  # business rule
                if discount_value > max_allowed:
                    messages.error(
                        request,
                        f"Flat discount cannot exceed 10% of minimum order amount (₹{max_allowed})."
                    )
                    return redirect('admin_panel:add_coupon')

        else:
            messages.error(request, "Invalid discount type selected.")
            return redirect('admin_panel:add_coupon')

        # ✅ Create coupon
        Coupon.objects.create(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            min_order_amount=min_order_amount,
            start_date=start_dt,
            end_date=end_dt,
            usage_limit=int(usage_limit or 0)
        )

        messages.success(request, "Coupon created successfully.")
        return redirect('admin_panel:coupon_list')

    return render(request, 'admin_panel/add_coupon.html')
@admin_login_required
def edit_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    if request.method == 'POST':
        code = request.POST.get('code').strip().upper()
        discount_type = request.POST.get('discount_type')
        discount_value = Decimal(request.POST.get('discount_value') or 0)
        min_order_amount = Decimal(request.POST.get('min_order_amount') or 0)
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        usage_limit = request.POST.get('usage_limit')

        try:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('admin_panel:edit_coupon', coupon_id=coupon.id)

       
        if Coupon.objects.filter(code=code).exclude(id=coupon.id).exists():
            messages.error(request, "Coupon code already exists.")
            return redirect('admin_panel:edit_coupon', coupon_id=coupon.id)

        if start_dt > end_dt:
            messages.error(request, "Start date cannot be after end date.")
            return redirect('admin_panel:edit_coupon', coupon_id=coupon.id)

        coupon.code = code
        coupon.discount_type = discount_type
        coupon.discount_value = discount_value
        coupon.min_order_amount = min_order_amount
        coupon.start_date = start_dt
        coupon.end_date = end_dt
        coupon.usage_limit = int(usage_limit or 0)
        coupon.save()

        messages.success(request, "Coupon updated successfully.")
        return redirect('admin_panel:coupon_list')

    return render(request, 'admin_panel/edit_coupon.html', {'coupon': coupon})

@admin_login_required
def delete_coupon(request, coupon_id):
    coupon = Coupon.objects.filter(id=coupon_id).first()  # Avoid get_object_or_404
    if coupon:
        coupon.delete()
        messages.success(request, "Coupon deleted successfully.")
    else:
        messages.error(request, "Coupon does not exist or was already deleted.")
    return redirect('admin_panel:coupon_list')


@admin_login_required
def sales_report_view(request):
    filter_type = request.GET.get('filter_type', 'custom')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    start_date = parse_date(start_date) if start_date else None
    end_date = parse_date(end_date) if end_date else None

    today = datetime.now().date()
    if filter_type == 'daily':
        start_date = end_date = today
    elif filter_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif filter_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
    elif filter_type == 'custom' and not (start_date and end_date):
        start_date = today - timedelta(days=30)
        end_date = today
    else:
        start_date = start_date or today - timedelta(days=30)
        end_date = end_date or today

    # Fetch Delivered Orders
    orders_qs = Order.objects.filter(
        created_at__date__range=[start_date, end_date],
        status='Delivered'
    ).select_related('user', 'applied_coupon').prefetch_related('items__product', 'items__variant')

    total_orders = orders_qs.count()
    total_sales_amount = Decimal('0.00')
    total_discount = Decimal('0.00')
    total_items = 0

    orders_data = []

    for order in orders_qs:
        order_items = order.items.all()
        original_total = sum(item.product.price * item.quantity for item in order_items)
        discount = Decimal('0.00')
        coupon_code = ''

        # Coupon discount
        if order.applied_coupon:
            coupon = order.applied_coupon
            if coupon.discount_type == 'percent':
                discount = original_total * (coupon.discount_value / Decimal('100'))
            elif coupon.discount_type == 'amount':
                discount = coupon.discount_value

            if coupon.min_order_amount and original_total < coupon.min_order_amount:
                discount = Decimal('0.00')

            discount = min(discount, original_total)
            coupon_code = coupon.code

        final_amount = original_total - discount

        total_sales_amount += final_amount
        total_discount += discount
        total_items += sum(item.quantity for item in order_items)

        orders_data.append({
            'id': order.order_id,
            'user': order.user.email,
            'amount': original_total,
            'discount': discount,
            'final_amount': final_amount,
            'coupon': coupon_code,
            'status': order.status,
            'date': order.created_at,
            'items_count': sum(item.quantity for item in order_items),
        })

    context = {
        'orders': orders_data,
        'filter_type': filter_type,
        'start_date': start_date,
        'end_date': end_date,
        'total_orders': total_orders,
        'total_sales_amount': total_sales_amount,
        'total_discount': total_discount,
        'total_items': total_items,
    }
    return render(request, 'admin_panel/sales_report.html', context)

@admin_login_required
def download_sales_report_excel(request):
    start_date = parse_date(request.GET.get('start_date'))
    end_date = parse_date(request.GET.get('end_date'))
    filter_type = request.GET.get('filter_type', 'custom')

    today =datetime.now().date()
    if filter_type == 'daily':
        start_date = end_date = today
    elif filter_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif filter_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
    else:
        start_date = start_date or today - timedelta(days=30)
        end_date = end_date or today

    orders_qs = Order.objects.filter(
        created_at__date__range=[start_date, end_date],
        status='Delivered'
    ).select_related('user', 'applied_coupon').prefetch_related('items__product', 'items__variant')

    data = []
    for order in orders_qs:
        order_items = order.items.all()
        original_total = sum(item.product.price * item.quantity for item in order_items)
        discount = Decimal('0.00')
        coupon_code = ''

        if order.applied_coupon:
            coupon = order.applied_coupon
            if coupon.discount_type == 'percent':
                discount = original_total * (coupon.discount_value / Decimal('100'))
            elif coupon.discount_type == 'amount':
                discount = coupon.discount_value

            if coupon.min_order_amount and original_total < coupon.min_order_amount:
                discount = Decimal('0.00')

            discount = min(discount, original_total)
            coupon_code = coupon.code

        final_amount = original_total - discount

        data.append({
            'Order ID': order.order_id,
            'Customer': order.user.email,
            'Date': order.created_at.strftime('%d-%m-%Y'),
            'Status': order.status,
            'Total': float(original_total),
            'Discount': float(discount),
            'Coupon': coupon_code if coupon_code else '--',
            'Final Amount': float(final_amount),
            'Items Count': sum(item.quantity for item in order_items),
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=sales_report_{start_date}_to_{end_date}.xlsx'
    df.to_excel(response, index=False, engine='openpyxl')
    return response

@admin_login_required
def download_sales_report_pdf(request):
    start_date = parse_date(request.GET.get('start_date'))
    end_date = parse_date(request.GET.get('end_date'))
    filter_type = request.GET.get('filter_type', 'custom')

    today = datetime.now().date()
    if filter_type == 'daily':
        start_date = end_date = today
    elif filter_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif filter_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
    else:
        start_date = start_date or today - timedelta(days=30)
        end_date = end_date or today

    orders_qs = Order.objects.filter(
        created_at__date__range=[start_date, end_date],
        status='Delivered'
    ).select_related('user', 'applied_coupon').prefetch_related('items__product', 'items__variant')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Sales Report ({start_date} to {end_date})", styles['Title']))

    # Table header
    data = [['Order ID', 'Customer', 'Date', 'Total', 'Discount', 'Coupon', 'Final Amount', 'Items']]

    total_sales_amount = Decimal('0.00')
    total_discount_amount = Decimal('0.00')
    total_items_count = 0

    for order in orders_qs:
        order_items = order.items.all()
        original_total = sum(item.product.price * item.quantity for item in order_items)
        discount = Decimal('0.00')
        coupon_code = ''

        if order.applied_coupon:
            coupon = order.applied_coupon
            if coupon.discount_type == 'percent':
                discount = original_total * (coupon.discount_value / Decimal('100'))
            elif coupon.discount_type == 'amount':
                discount = coupon.discount_value

            if coupon.min_order_amount and original_total < coupon.min_order_amount:
                discount = Decimal('0.00')

            discount = min(discount, original_total)
            coupon_code = coupon.code

        final_amount = original_total - discount

        total_sales_amount += final_amount
        total_discount_amount += discount
        items_count = sum(item.quantity for item in order_items)
        total_items_count += items_count

        data.append([
            order.order_id,
            order.user.email,
            order.created_at.strftime('%d-%m-%Y'),
            f"₹{original_total:.2f}",
            f"₹{discount:.2f}",
            coupon_code if coupon_code else '--',
            f"₹{final_amount:.2f}",
            str(items_count),
        ])

    # Totals row
    data.append([
        'Totals', '', '', f"₹{total_sales_amount:.2f}",
        f"₹{total_discount_amount:.2f}", '₹', f"₹{total_sales_amount:.2f}",
        str(total_items_count)
    ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename=sales_report_{start_date}_to_{end_date}.pdf'
    })
