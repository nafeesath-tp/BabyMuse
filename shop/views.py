from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Avg
import json
from orders.models import Order
from django.views.decorators.cache import never_cache
from django.conf import settings

from .models import Product, Category, Wishlist, CartItem, Review, ProductVariant,ProductOffer
from django.urls import reverse



@login_required
def my_orders_view(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'shop/my_orders.html', {'orders': orders})


def shop_view(request):
    products = Product.objects.filter(is_listed=True, category__is_listed=True).prefetch_related('variants')

    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    sort_by = request.GET.get('sort', '')

    if search_query:
        products = products.filter(name__icontains=search_query)

    if category_id:
        products = products.filter(category__id=category_id)

    if price_min.isdigit() and price_max.isdigit():
        products = products.filter(price__gte=price_min, price__lte=price_max)

    if sort_by == "price_low":
        products = products.order_by('price')
    elif sort_by == "price_high":
        products = products.order_by('-price')
    elif sort_by == "name_asc":
        products = products.order_by('name')
    elif sort_by == "name_desc":
        products = products.order_by('-name')
    else:
        products = products.order_by('-created_at')
    for product in products:

        product.has_stock = any(variant.stock > 0 for variant in product.variants.all())
    paginator = Paginator(products, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'categories': Category.objects.all(),
        'selected_category': category_id,
        'price_min': price_min,
        'price_max': price_max,
        'sort_by': sort_by,

    }

    return render(request, 'shop/shop.html', context)

@never_cache
def product_detail(request, pk):
    try:
        product = Product.objects.prefetch_related(
            'images', 'variants').get(pk=pk)
        offer = ProductOffer.objects.filter(product=product, is_active=True).order_by('-id').first()


        reviews = Review.objects.filter(
            product=product).order_by('-created_at')
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
        total_reviews = reviews.count()
        print("Product instance used in variant filter:", product)
        print("Product ID:", product.id)
        print("Product type:", type(product))

        variants = ProductVariant.objects.filter(
               product__id=product.id,
                            is_listed=True,
                                 stock__gt=0)  # Optional: only include those in stock

        

        
       
        sizes = set()

        for variant in variants:
            if variant.size:
                sizes.add(variant.size)

        # Normalize product name
        name = product.name.strip().lower()

        show_size = any(x in name for x in [
                        'disposible diaper', 'ethnicwear', 'frocks'])
        best_discount = max(product.category.discount_percent if product.category else 0,
                    offer.discount_percent if offer else 0)

        context = {
            'product': product,
            'images': product.images.all(),
            'variants': variants,
            'sizes': sorted(sizes),
            'show_size': show_size,
            'final_discount': best_discount,
            
            'discounted_price':product.discounted_price,
            'offer':offer,

        }

        return render(request, 'shop/product_detail.html', context)

    except Product.DoesNotExist:
        messages.error(request, "⚠️ Product not found or has been removed.")
        return redirect('shop')


@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product').prefetch_related('product__images')
    return render(request, 'shop/wishlist.html', {'wishlist_items': wishlist_items})


@login_required
@require_POST
def ajax_add_to_wishlist(request):
    product_id = request.POST.get('product_id')
    variant_id = request.POST.get('variant_id')
    product = get_object_or_404(Product, id=product_id)
    variant = get_object_or_404(ProductVariant, id=variant_id) if variant_id else None

    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user, product=product,variant=variant)
    return JsonResponse({'status': 'added' if created else 'exists'})


@login_required
@require_POST
def ajax_remove_from_wishlist(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid data format'})

    if not product_id:
        return JsonResponse({'status': 'error', 'message': 'Product ID required'})

    Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    return JsonResponse({'status': 'success', 'message': 'Removed from wishlist'})



@login_required
def cart_view(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related(
        'product','variant'
    ).prefetch_related('product__images')

    total_price = 0
    for item in cart_items:
        price_to_show = item.product.discounted_price
        item.price_to_show = price_to_show
        item.total_price = item.quantity * price_to_show
        total_price += item.total_price

    return render(request, 'shop/cart.html', {
        'cart_items': cart_items,
        'total_price': total_price,
    })

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.urls import reverse
import json

@require_POST
def ajax_add_to_cart(request):
    if not request.user.is_authenticated:
        return JsonResponse({'redirect_url': reverse('user:user_login')}, status=401)

    # ✅ Handle JSON body
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            product_id = data.get('product_id')
            variant_id = data.get('variant_id')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid data format'})
    else:
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')

    if not product_id:
        return JsonResponse({'status': 'error', 'message': 'Product ID is required'})

    # ✅ Fetch product
    from shop.models import Product, ProductVariant, CartItem, Wishlist

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found.'})

    if not product.is_listed or not product.category.is_listed:
        return JsonResponse({'status': 'error', 'message': 'This product is not available.'})

    # ✅ Handle variant
    variant = None
    if variant_id:
        try:
            variant = ProductVariant.objects.get(id=variant_id, product=product)
        except ProductVariant.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Invalid variant selected.'})

    # ✅ Stock check
    available_stock = variant.stock if variant else 0
    if available_stock < 1:
        return JsonResponse({'status': 'error', 'message': 'Not enough stock.'})

    # ✅ Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        variant=variant,
        defaults={'quantity': 1}
    )

    if not created:
        if cart_item.quantity < available_stock:
            cart_item.quantity += 1
            cart_item.save()
        else:
            return JsonResponse({'status': 'error', 'message': 'Maximum stock reached in cart.'})

    # ✅ Remove from wishlist
    Wishlist.objects.filter(user=request.user, product=product).delete()

    cart_count = CartItem.objects.filter(user=request.user).count()
    return JsonResponse({'status': 'success', 'cart_count': cart_count})

@login_required
@require_POST
def ajax_remove_from_cart(request):
    data = json.loads(request.body)
    product_id = data.get("product_id")
    try:
        item = CartItem.objects.get(user=request.user, variant__id=product_id)
        item.delete()
        return JsonResponse({"status": "success", "message": "Item removed from cart"})
    except CartItem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Item not found"})


@require_POST
@login_required
def update_cart_quantity(request, product_id):
    print(product_id)
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            return JsonResponse({"status": "error", "message": "Quantity must be at least 1."})

        cart_item = CartItem.objects.get(
            user=request.user, variant__id=product_id)

        if quantity > cart_item.variant.stock:
            return JsonResponse({"status": "error", "message": "Exceeds stock."})

        cart_item.quantity = quantity
        cart_item.save()

        total_price = sum(
            item.quantity * item.product.price
            for item in CartItem.objects.filter(user=request.user)
        )

        return JsonResponse({
            "status": "success",
            "message": "Cart updated successfully.",
            "item_total": cart_item.quantity * cart_item.product.price,
            "unit_price": cart_item.product.price,
            "new_total": total_price
        })

    except CartItem.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Item not found in your cart."})
    except ValueError:
        return JsonResponse({"status": "error", "message": "Invalid quantity."})


@login_required
def ajax_cart_data(request):
    cart_items = CartItem.objects.filter(
        user=request.user).select_related('product')
    data = []
    total_price = 0

    for item in cart_items:
        price = item.quantity * item.product.price
        total_price += price
        data.append({
            'id': item.product.id,
            'name': item.product.name,
            'price': item.product.price,
            'quantity': item.quantity,
            'total': price,
        })

    return JsonResponse({"status": "success", "items": data, "total_price": total_price})
