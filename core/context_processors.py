from shop.models import CartItem, Wishlist


def shared_counts(request):
    cart_count = wishlist_count = 0
    if request.user.is_authenticated:
        cart_count = CartItem.objects.filter(user=request.user).count()
        wishlist_count = Wishlist.objects.filter(user=request.user).count()
    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count
    }
