
# orders/views.py

import io, uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, HttpRequest
from django.shortcuts import get_object_or_404, redirect, render


from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db.models import F



from shop.models import CartItem, Product,ProductVariant,ProductOffer
from user.models import Address
from .models import Order, OrderItem
from .forms import ItemReturnForm
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from orders.models import Payment
from django.middleware.csrf import get_token
from .models import Coupon

from django.http import FileResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Table, TableStyle, Paragraph, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
import io
import os
from decimal import Decimal


client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


@login_required
def my_orders_view(request: HttpRequest):
    orders = Order.objects.all()
    qs = Order.objects.filter(user=request.user)
    print(qs)
    print(f"all orders: {orders}")
    q  = request.GET.get("q", "").strip().upper()
    if q:
        qs = qs.filter(order_id__icontains=q)

    return render(
        request,
        "orders/user_orders.html",
        {"orders": qs.order_by("-created_at"), "q": q},
    )



@login_required
def order_detail_view(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"),  
        pk=order_id,
        user=request.user,
    )

    order_item = OrderItem.objects.all()

    # Calculate subtotal for each item
    for item in order.items.all():
        item.subtotal = item.quantity * item.price

    return render(request, "orders/order_detail.html", {"order": order,'order_item':order_item})




@login_required
def cancel_order_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    if order.status in ("Cancelled", "Delivered"):
        messages.error(request, "This order can’t be cancelled.")
        return redirect("orders:order_detail", order_id=order.id)

    if request.method == "POST":
        reason = request.POST.get("reason", "")  
        with transaction.atomic():
            for item in order.items.select_related("product"):
                item.product.stock += item.quantity
                item.product.save(update_fields=["stock"])
            order.status = "Cancelled"
            order.save(update_fields=["status"])
        messages.success(request, "Order cancelled ✔️")
        return redirect("orders:order_detail", order_id=order.id)

    return render(request, "orders/order_cancel_confirm.html", {"order": order})


@login_required
def return_order_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    if order.status != "Delivered":
        messages.error(request, "Only delivered orders may be returned.")
        return redirect("orders:order_detail", order_id=order.id)

    if request.method == "POST":
        form = ItemReturnForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']

            with transaction.atomic():
                order.status = "Returned"
                order.is_returned = True
                order.save(update_fields=["status", "is_returned"])

                for item in order.items.select_related("product","variant"):
                    item.variant.stock += item.quantity
                    item.variant.save(update_fields=["stock"])
                    item.is_return_requested = True  
                    item.save(update_fields=["is_return_requested"])

            messages.success(request, "Return request submitted ✔️")
            return redirect("orders:order_detail", order_id=order.id)
        else:
            messages.error(request, "Return reason is required.")
    else:
        form = ItemReturnForm()

    return render(request, "orders/order_return_form.html", {"order": order, "form": form})
@login_required
def return_item_view(request, item_id):
    item = get_object_or_404(OrderItem, pk=item_id, order__user=request.user)

    if item.order.status != "Delivered" or item.is_returned:
        messages.error(request, "This item cannot be returned.")
        return redirect("orders:order_detail", order_id=item.order.id)

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "Return reason is required.")
            return redirect("orders:return_item", item_id=item.id)

        
        item.is_return_requested = True
        item.return_reason = reason
        item.save(update_fields=["is_return_requested", "return_reason"])

        messages.success(request, "Return request submitted. Waiting for approval ✔️")
        return redirect("orders:order_detail", order_id=item.order.id)

    return render(request, "orders/item_return_form.html", {"item": item})



@login_required
def checkout_view(request):
    user = request.user
    cart_items = CartItem.objects.filter(user=user).select_related("product", "variant")
    addresses = Address.objects.filter(user=user)
    default_address = addresses.filter(is_default=True).first()

    # ✅ Calculate totals
    final_total = 0
    total_discount = 0
    for item in cart_items:
        product = item.product
        item.price_to_show = product.discounted_price
        final_total += item.price_to_show * item.quantity
        total_discount += (product.price - item.price_to_show) * item.quantity

    if final_total < 1:
        return redirect("shop:cart")

    now = timezone.now()

    # ✅ Available coupons
    available_coupons = Coupon.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
        min_order_amount__lte=final_total
    )

    applied_coupon = None
    discount_amount = 0
    if 'applied_coupon' in request.session:
        try:
            applied_coupon = Coupon.objects.get(code=request.session['applied_coupon'])
            if applied_coupon.is_valid():
                if final_total >= applied_coupon.min_order_amount:
                    if applied_coupon.discount_type == 'percent':
                        discount_amount = (final_total * applied_coupon.discount_value) / 100
                    else:
                        discount_amount = applied_coupon.discount_value
                else:
                    messages.warning(request, f"Coupon requires a minimum order of ₹{applied_coupon.min_order_amount}.")
                    del request.session['applied_coupon']
                    applied_coupon = None
            else:
                messages.warning(request, "Coupon is not valid anymore.")
                del request.session['applied_coupon']
                applied_coupon = None
        except Coupon.DoesNotExist:
            del request.session['applied_coupon']
            applied_coupon = None

    if discount_amount > final_total:
        discount_amount = final_total

    final_total_after_discount = final_total - discount_amount

    # ✅ Razorpay order creation
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    razorpay_order = client.order.create({
        "amount": int(final_total_after_discount * 100),
        "currency": "INR",
        "payment_capture": "1"
    })

    # ✅ Handle form submission
    if request.method == "POST":
        selected_address_id = request.POST.get("selected_address")
        payment_method = request.POST.get("payment_method")

        if not selected_address_id or not payment_method:
            messages.error(request, "Please select both address and payment method.")
            return redirect("orders:checkout")

        if applied_coupon and not applied_coupon.is_valid():
            messages.error(request, "Coupon is no longer valid.")
            if 'applied_coupon' in request.session:
                del request.session['applied_coupon']
            return redirect("orders:checkout")

        try:
            address = Address.objects.get(id=selected_address_id)
        except Address.DoesNotExist:
            messages.error(request, "Selected address not found.")
            return redirect("orders:checkout")

        # ✅ Razorpay AJAX
        if payment_method == "Razorpay" and request.headers.get("X-Requested-With", "").lower() == "xmlhttprequest":
            order = Order.objects.create(
                user=user,
                address=address,
                total_price=final_total_after_discount,
                payment_method="Razorpay",
                status="Pending",
                razorpay_order_id=razorpay_order["id"],
                applied_coupon=applied_coupon
            )
            return JsonResponse({
                "razorpay_order_id": razorpay_order["id"],
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "amount": int(final_total_after_discount * 100),
                "order_id": order.id
            })

        # ✅ COD
        if payment_method == "COD":
            try:
                with transaction.atomic():
                    order = Order.objects.create(
                        user=user,
                        address=address,
                        total_price=final_total_after_discount,
                        payment_method="COD",
                        applied_coupon=applied_coupon
                    )

                    for item in cart_items:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            variant=item.variant,
                            quantity=item.quantity,
                            price=item.product.discounted_price,
                        )
                        item.variant.stock -= item.quantity
                        item.variant.save(update_fields=["stock"])

                    Payment.objects.create(
                        user=user,
                        method="COD",
                        amount=final_total_after_discount,
                        status="success"
                    )

                    # ✅ Increment coupon usage safely
                    if applied_coupon:
                        Coupon.objects.filter(id=applied_coupon.id).update(
                            used_count=F('used_count') + 1
                        )
                        request.session.pop('applied_coupon', None)

                    cart_items.delete()

                messages.success(request, "Order placed successfully via COD.")
                return redirect("orders:order_success", order_id=order.id)

            except Exception as e:
                messages.error(request, f"COD order placement failed: {e}")
    available_coupons = Coupon.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    ).exclude(usage_limit__gt=0, used_count__gte=F('usage_limit'))            

    context = {
        "cart_items": cart_items,
        "final_total": final_total,
        "total_discount": total_discount,
        "addresses": addresses,
        "default_address": default_address,
        "razorpay_order_id": razorpay_order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "final_total_after_discount": final_total_after_discount,
        "applied_coupon": applied_coupon,
        "discount_amount": discount_amount,
        "available_coupons": available_coupons,
    }

    return render(request, "orders/checkout.html", context)


@csrf_exempt
def razorpay_success(request):
    if request.method == "POST":
        try:
            user = request.user
            if not user.is_authenticated:
                return JsonResponse({"error": "User not authenticated."}, status=401)

            data = request.POST
            order_id = data.get("order_id")
            payment_id = data.get("razorpay_payment_id")

            if not order_id or not payment_id:
                return JsonResponse({"error": "Missing order or payment ID."}, status=400)

            # ✅ Verify Razorpay signature
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature({
                'razorpay_order_id': data.get("razorpay_order_id"),
                'razorpay_payment_id': data.get("razorpay_payment_id"),
                'razorpay_signature': data.get("razorpay_signature")
            })

            order = Order.objects.select_related("applied_coupon").get(id=order_id, user=user)

            # ✅ Validate coupon
            if order.applied_coupon and not order.applied_coupon.is_valid():
                return JsonResponse({"error": "Coupon is no longer valid."}, status=400)

            # ✅ Update order status
            order.status = "Processing"
            order.save(update_fields=["status"])

            # ✅ Move cart items
            cart_items = CartItem.objects.filter(user=user).select_related("product", "variant")
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    price=item.product.discounted_price
                )
                item.variant.stock -= item.quantity
                item.variant.save(update_fields=["stock"])
            cart_items.delete()

            # ✅ Create Payment
            Payment.objects.create(
                user=user,
                method="Razorpay",
                amount=order.total_price,
                transaction_id=payment_id,
                status="success"
            )

            # ✅ Increment coupon usage
            if order.applied_coupon:
                Coupon.objects.filter(id=order.applied_coupon.id).update(
                    used_count=F('used_count') + 1
                )

            request.session.pop('applied_coupon', None)

            return JsonResponse({
                "redirect_url": reverse("orders:order_success", args=[order.id])
            })

        except razorpay.errors.SignatureVerificationError:
            return JsonResponse({"error": "Payment signature verification failed."}, status=400)
        except Exception as e:
            print("Payment Error:", str(e))
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request."}, status=400)

@login_required
def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip().upper()

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            messages.error(request, "Invalid coupon code.")
            return redirect('orders:checkout')

        # ✅ Validate coupon
        if not coupon.is_valid():
            messages.error(request, "This coupon is expired, inactive, or usage limit reached.")
            return redirect('orders:checkout')

        # ✅ Calculate cart total
        cart_items = CartItem.objects.filter(user=request.user)
        cart_total = sum(item.quantity * item.product.discounted_price for item in cart_items)

        if cart_total < coupon.min_order_amount:
            messages.error(request, f"Minimum order amount for this coupon is ₹{coupon.min_order_amount}.")
            return redirect('orders:checkout')

        # ✅ Save coupon in session
        request.session['applied_coupon'] = coupon.code
        messages.success(request, f"Coupon '{coupon.code}' applied successfully!")
        return redirect('orders:checkout')

    return redirect('orders:checkout')


def remove_coupon(request):
    if 'applied_coupon' in request.session:
        del request.session['applied_coupon']
        messages.info(request, "Coupon removed.")
    return redirect("orders:checkout")


@login_required
def order_success_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "orders/order_success.html", {"order": order})
@login_required
def apply_coupon(request):
    if request.method == 'POST':
        code = request.POST.get('coupon_code', '').strip().upper()

        try:
            coupon = Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            messages.error(request, "Invalid coupon code.")
            return redirect('orders:checkout')

        # ✅ Validate coupon status
        if not coupon.is_valid():
            messages.error(request, " usage limit reached.")
            return redirect('orders:checkout')

  


        # ✅ Calculate cart total
        cart_items = CartItem.objects.filter(user=request.user)
        cart_total = sum(item.quantity * item.product.discounted_price for item in cart_items)

        if cart_total < coupon.min_order_amount:
            messages.error(request, f"Minimum order amount for this coupon is ₹{coupon.min_order_amount}.")
            return redirect('orders:checkout')

        # ✅ Save coupon in session
        request.session['applied_coupon'] = coupon.code
        messages.success(request, f"Coupon '{coupon.code}' applied successfully!")
        return redirect('orders:checkout')

    return redirect('orders:checkout')

def remove_coupon(request):
    if 'applied_coupon' in request.session:
        del request.session['applied_coupon']
    messages.success(request, "Coupon removed successfully.")
    return redirect('orders:checkout')
def payment_failure_view(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status == "Pending":
        order.status = "Failed"
        order.save(update_fields=["status"])
    return render(request, "orders/payment_failure.html", {"order": order})

pdfmetrics.registerFont(TTFont('Arial', 'C:\\Windows\\Fonts\\arial.ttf'))

@login_required
def download_invoice_view(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # ✅ Use Arial font everywhere
    c.setFont("Arial", 12)

    # ✅ Add Logo (top-left)
    logo_path = os.path.join('static', 'images', 'logo.png')  # Ensure logo exists
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 80, width=80, height=40, preserveAspectRatio=True)

    # ✅ Company Name & Details
    c.setFont("Arial", 18)
    c.drawCentredString(width / 2 + 40, height - 40, "BabyMuse Pvt Ltd")

    c.setFont("Arial", 10)
    c.drawCentredString(width / 2 + 40, height - 55, "www.babymuse.com | support@babymuse.com")

    # ✅ Invoice Title
    y_position = height - 100
    c.setFont("Arial", 14)
    c.drawString(40, y_position, f"Invoice – Order #{order.order_id}")
    y_position -= 18
    c.setFont("Arial", 10)
    c.drawString(40, y_position, f"Date: {order.created_at.strftime('%d %b %Y')}")

    # ✅ Shipping Address
    y_position -= 30
    c.setFont("Arial", 12)
    c.drawString(40, y_position, "Shipping Address:")
    y_position -= 14
    c.setFont("Arial", 10)
    address = order.address
    c.drawString(40, y_position, f"{address.name}")
    y_position -= 12
    c.drawString(40, y_position, f"{address.address_line}")
    y_position -= 12
    c.drawString(40, y_position, f"{address.city}, {address.state} - {address.postal_code}")
    y_position -= 12
    c.drawString(40, y_position, f"Phone: {address.phone}")

    # ✅ Order Table
    y_position -= 40
    data = [["Product", "Qty", "Price", "Subtotal"]]
    total = Decimal("0.00")
    for itm in order.items.all():
        line_total = itm.quantity * itm.price
        total += line_total
        data.append([
            itm.product.name,
            str(itm.quantity),
            f"₹{itm.price:.2f}",
            f"₹{line_total:.2f}"
        ])

    # ✅ Add Total Row
    data.append(["", "", "Total:", f"₹{total:.2f}"])

    table = Table(data, colWidths=[200, 50, 80, 80])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Arial'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
    ]))

    # ✅ Position Table
    table.wrapOn(c, width, height)
    table.drawOn(c, 40, y_position - (len(data) * 18))

    # ✅ Footer
    c.setFont("Arial", 10)
    c.drawString(40, 50, "Thank you for shopping with BabyMuse!")

    c.showPage()
    c.save()

    buf.seek(0)
    return FileResponse(buf, as_attachment=True, filename=f"invoice_{order.order_id}.pdf")