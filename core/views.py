from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from shop.models import Product, Wishlist, CartItem


def home_view(request):
    if request.user.is_authenticated:
        products = Product.objects.filter(
            
            is_listed=True,
            category__is_listed=True,  
            category__name__in=['Custom', 'Personalized']
        )
        customized = True
    else:
        products = Product.objects.filter(
            
            is_listed=True,
            category__is_listed=True  
        )[:6]
        customized = False

    return render(request, 'core/home.html', {
        'products': products,
        'customized': customized,
    })



def search(request):
    query = request.GET.get('query', '')  
   
    results = []  
    return render(request, 'core/search_results.html', {
        'query': query,
        'results': results
    })


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    return render(request, 'core/contact.html')
