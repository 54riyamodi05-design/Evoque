from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from django.contrib import messages
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
from django.utils import timezone

def loginView(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': 'ADMIN' if (user.is_superuser or user.is_staff) else 'CUSTOMER',
                    'phone': '',
                },
            )

            if profile.role == 'ADMIN':
                return redirect('adminDashboard')
            elif profile.role == 'PROVIDER':
                provider=ServiceProviderProfile.objects.get(user=user)
                if not provider.status:
                    return render(
                        request,
                        'login.html',
                        {'error': 'Your account is pending admin approval'}
                    )

                return redirect('providerDashboard')
                
            else:
                return redirect('customerDashboard')

        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
        
        

    return render(request, 'login.html')


def logoutView(request):
    logout(request)
    return redirect('login')


@login_required
def providerDashboardView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'PROVIDER':
        return redirect('login')
    return render(request, 'providerDashboard.html')

@login_required
def customerDashboardView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'CUSTOMER':
        return redirect('login')
    return render(request, 'customerDashboard.html')

def customerRegisterView(request):
    if request.method=='POST':
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        phone=request.POST['phone']

        user=User.objects.create_user(
            username=username,
            password=password,
            email=email
        )
        UserProfile.objects.create(
            user=user,
            phone=phone,
            role='CUSTOMER'
        )
        
        messages.success(request, 'Registration Successful. Please Login')
        return redirect('login')
    
    return render(request, 'customerRegister.html')


def providerRegisterView(request):
    if request.method=='POST':
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']
        phone=request.POST['phone']

        user=User.objects.create_user(
            username=username,
            password=password,
            email=email
        )
        UserProfile.objects.create(
            user=user,
            phone=phone,
            role='PROVIDER'
        )

        ServiceProviderProfile.objects.create(
            user=user,
            phone=phone,
            status=False
        )
        
        messages.success(request, 'Registration submitted. Wait for admin approval.')
        return redirect('login')
    
    return render(request,'providerRegister.html')

        

@login_required
def customPacakgeView(request):
    if request.method == 'POST':
        CustomPackage.objects.create(
            customer=request.user,
            category_id=request.POST['category'],
            title=request.POST['title'],
            description=request.POST['description'],
            expectedBudget=request.POST.get('budget')
        )
        return redirect('customerDashboard')

    categories = Category.objects.filter(status=True)
    return render(request, 'customPackage.html', {
        'categories': categories
    })

@login_required
def myCustomPackages(request):
    requests = CustomPackage.objects.filter(customer=request.user)

    return render(
        request,
        'CustomRequests.html',
        {'requests': requests}
    )


@login_required
def categoriesListView(request):
    categories=Category.objects.filter(status=True)
    return render(request, 'categoryList.html', {'categories':categories})

def packageList(request, categoryId):
    packages=Package.objects.filter(category_id=categoryId, status=True)
    return render(request, 'packageList.html', {'packages':packages})

def packageDetail(request, packageId):
    package=Package.objects.get(id=packageId)
    venues=Venue.objects.filter(status=True)
    
    return render(
        request,
        'packageDetail.html',
        {
            'package': package,
            'venues': venues,
            'today_iso': timezone.localdate().isoformat(),
        }
    )

@login_required
def createOrder(request, packageId):
    if request.method != 'POST':
        return redirect('packageDetail', packageId=packageId)

    theme = request.POST.get('theme_type')
    venue_id = request.POST.get('venue_id')
    event_date_raw = request.POST.get('event_date', '').strip()

    if not venue_id:
        messages.error(request, 'Please select a venue.')
        return redirect('packageDetail', packageId=packageId)

    if theme not in dict(Order.THEME_CHOICES):
        messages.error(request, 'Please select a valid theme.')
        return redirect('packageDetail', packageId=packageId)

    if not event_date_raw:
        messages.error(request, 'Please select an event date.')
        return redirect('packageDetail', packageId=packageId)

    try:
        event_date = date.fromisoformat(event_date_raw)
    except ValueError:
        messages.error(request, 'Invalid event date.')
        return redirect('packageDetail', packageId=packageId)

    if event_date < timezone.localdate():
        messages.error(request, 'Past event dates are not allowed.')
        return redirect('packageDetail', packageId=packageId)

    package = get_object_or_404(Package.objects.select_related('category'), id=packageId, status=True)
    venue = get_object_or_404(Venue, id=venue_id, status=True)

    order = Order.objects.create(
        user=request.user,
        package=package,
        venue=venue,
        theme_type=theme,
        event_date=event_date,
    )

    Payment.objects.create(
        order=order,
        amount=order.get_final_price() + venue.price,
        payment_method='COD'
    )

    if order.seasonal_discount_percent > Decimal('0.00'):
        messages.success(
            request,
            f'{order.seasonal_discount_percent}% seasonal discount applied for this wedding booking.'
        )
    else:
        messages.success(request, 'Order placed successfully.')

    return redirect('customerDashboard')


from django.contrib.auth.decorators import login_required

@login_required
def customerOrder(request):
    orders = (
        Order.objects.filter(user=request.user)
        .select_related('package', 'payment')
    )

    return render(
        request,
        'customerOrder.html',
        {'orders': orders}
    )


@login_required
def orderDetail(request, orderId):
    order = get_object_or_404(
        Order.objects.select_related('package__category', 'venue', 'payment'),
        id=orderId,
        user=request.user,
    )

    try:
        payment = order.payment
    except Payment.DoesNotExist:
        payment = None

    if payment:
        final_amount = payment.amount
    else:
        venue_price = order.venue.price if order.venue else Decimal('0.00')
        final_amount = order.get_final_price() + venue_price

    context = {
        'order': order,
        'payment': payment,
        'final_amount': final_amount,
    }
    return render(request, 'orderDetail.html', context)


@login_required
def cancelOrder(request, orderId):
    order = get_object_or_404(
        Order,
        id=orderId,
        user=request.user,
    )

    if request.method == 'POST' and order.status == 'PENDING':
        order.status = 'CANCELLED'
        order.save(update_fields=['status'])

    return redirect('customerOrder')



@login_required
def adminDashboardView(request):
    # Safety check: only ADMIN allowed
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    total_customers = UserProfile.objects.filter(role='CUSTOMER').count()
    total_providers = UserProfile.objects.filter(role='PROVIDER').count()
    pending_providers = ServiceProviderProfile.objects.filter(status=False).count()
    total_orders = Order.objects.count()
    pending_custom_requests = CustomPackage.objects.filter(status='PENDING').count()

    context = {
        'total_customers': total_customers,
        'total_providers': total_providers,
        'pending_providers': pending_providers,
        'total_orders': total_orders,
        'pending_custom_requests': pending_custom_requests,
    }

    return render(request, 'adminDashboard.html', context)


@login_required
def adminProvidersView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    providers = ServiceProviderProfile.objects.select_related('user').all()
    return render(
        request,
        'adminProviders.html',
        {'providers': providers}
    )


@login_required
def approveProvider(request, providerId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    provider = get_object_or_404(ServiceProviderProfile, id=providerId)
    if request.method == 'POST':
        provider.status = True
        provider.save(update_fields=['status'])

    return redirect('adminProviders')


@login_required
def deactivateProvider(request, providerId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    provider = get_object_or_404(ServiceProviderProfile, id=providerId)
    if request.method == 'POST':
        provider.status = False
        provider.save(update_fields=['status'])

    return redirect('adminProviders')


@login_required
def adminCategoriesView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = bool(request.POST.get('status'))
        if name:
            Category.objects.create(
                name=name,
                description=description or None,
                status=status
            )
        return redirect('adminCategories')

    categories = Category.objects.all().order_by('name')
    return render(
        request,
        'adminCategories.html',
        {'categories': categories}
    )


@login_required
def adminCategoryEdit(request, categoryId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    category = get_object_or_404(Category, id=categoryId)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        status = bool(request.POST.get('status'))
        if name:
            category.name = name
            category.description = description or None
            category.status = status
            category.save()
        return redirect('adminCategories')

    return render(
        request,
        'adminCategoryEdit.html',
        {'category': category}
    )


@login_required
def adminCategoryToggle(request, categoryId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    category = get_object_or_404(Category, id=categoryId)
    if request.method == 'POST':
        category.status = not category.status
        category.save(update_fields=['status'])
    return redirect('adminCategories')


@login_required
def adminPackagesView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category_id')
        price = request.POST.get('price')
        status = bool(request.POST.get('status'))
        if name and category_id and price:
            Package.objects.create(
                name=name,
                description=description or None,
                category_id=category_id,
                price=price,
                status=status
            )
        return redirect('adminPackages')

    packages = Package.objects.select_related('category').all().order_by('name')
    categories = Category.objects.all().order_by('name')
    return render(
        request,
        'adminPackages.html',
        {'packages': packages, 'categories': categories}
    )


@login_required
def adminPackageEdit(request, packageId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    package = get_object_or_404(Package, id=packageId)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category_id')
        price = request.POST.get('price')
        status = bool(request.POST.get('status'))
        if name and category_id and price:
            package.name = name
            package.description = description or None
            package.category_id = category_id
            package.price = price
            package.status = status
            package.save()
        return redirect('adminPackages')

    categories = Category.objects.all().order_by('name')
    return render(
        request,
        'adminPackageEdit.html',
        {'package': package, 'categories': categories}
    )


@login_required
def adminPackageToggle(request, packageId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    package = get_object_or_404(Package, id=packageId)
    if request.method == 'POST':
        package.status = not package.status
        package.save(update_fields=['status'])
    return redirect('adminPackages')


@login_required
def adminVenuesView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        capacity = request.POST.get('capacity')
        price = request.POST.get('price')
        
        status = bool(request.POST.get('status'))
        if name and address and capacity and price:
            Venue.objects.create(
                name=name,
                address=address,
                capacity=capacity,
                price=price,
                image=request.FILES.get('image'),
                status=status
            )
        return redirect('adminVenues')

    venues = Venue.objects.all().order_by('name')
    return render(
        request,
        'adminVenues.html',
        {'venues': venues}
    )


@login_required
def adminVenueEdit(request, venueId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    venue = get_object_or_404(Venue, id=venueId)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        capacity = request.POST.get('capacity')
        price = request.POST.get('price')
        image=request.FILES.get('image')
        status = bool(request.POST.get('status'))
        if name and address and capacity and price:
            venue.name = name
            venue.address = address
            venue.capacity = capacity
            venue.price = price
            venue.status = status
            venue.image=image
            venue.save()
        return redirect('adminVenues')

    return render(
        request,
        'adminVenueEdit.html',
        {'venue': venue}
    )


@login_required
def adminVenueToggle(request, venueId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    venue = get_object_or_404(Venue, id=venueId)
    if request.method == 'POST':
        venue.status = not venue.status
        venue.save(update_fields=['status'])
    return redirect('adminVenues')


@login_required
def adminCustomRequests(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    requests = CustomPackage.objects.select_related('customer', 'category').all().order_by('-createdAt')
    return render(
        request,
        'adminCustomRequests.html',
        {'requests': requests}
    )


@login_required
def adminCustomRequestDetail(request, requestId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    custom_request = get_object_or_404(
        CustomPackage.objects.select_related('customer', 'category'),
        id=requestId
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            custom_request.status = 'APPROVED'
            custom_request.save(update_fields=['status'])
        elif action == 'reject':
            custom_request.status = 'REJECTED'
            custom_request.save(update_fields=['status'])
        elif action == 'create_package':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            price = request.POST.get('price')
            status = bool(request.POST.get('status'))
            if name and price:
                Package.objects.create(
                    category=custom_request.category,
                    name=name,
                    description=description or None,
                    price=price,
                    status=status
                )
                custom_request.status = 'APPROVED'
                custom_request.save(update_fields=['status'])

        return redirect('adminCustomRequestDetail', requestId=custom_request.id)

    return render(
        request,
        'adminCustomRequestDetail.html',
        {'request_obj': custom_request}
    )


@login_required
def adminOrdersView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    orders = (
        Order.objects.select_related('user', 'package', 'venue', 'payment')
        .all()
        .order_by('-order_date')
    )
    return render(
        request,
        'adminOrders.html',
        {'orders': orders}
    )


@login_required
def adminOrderDetail(request, orderId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'ADMIN':
        return redirect('login')

    order = get_object_or_404(
        Order.objects.select_related(
            'user',
            'package__category',
            'venue',
            'payment',
            'service_provider',
            'service_provider__user',
        ),
        id=orderId
    )
    providers = ServiceProviderProfile.objects.filter(status=True).select_related('user')
    tasks = Task.objects.filter(order=order).select_related('service_provider', 'service_provider__user')

    try:
        payment = order.payment
    except Payment.DoesNotExist:
        payment = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'status_confirm' and order.status == 'PENDING':
            order.status = 'CONFIRMED'
            order.save(update_fields=['status'])
        elif action == 'status_complete' and order.status == 'CONFIRMED':
            order.status = 'COMPLETED'
            order.save(update_fields=['status'])
        elif action == 'assign_provider':
            provider_id = request.POST.get('provider_id')
            if provider_id:
                order.service_provider_id = provider_id
                order.save(update_fields=['service_provider'])
        elif action == 'create_task':
            provider_id = request.POST.get('provider_id')
            description = request.POST.get('description', '').strip()
            status = request.POST.get('status', 'PENDING')
            if provider_id and description:
                Task.objects.create(
                    service_provider_id=provider_id,
                    order=order,
                    description=description,
                    status=status
                )

        return redirect('adminOrderDetail', orderId=order.id)

    return render(
        request,
        'adminOrderDetail.html',
        {
            'order': order,
            'payment': payment,
            'providers': providers,
            'tasks': tasks,
        }
    )


@login_required
def providerTasksView(request):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'PROVIDER':
        return redirect('login')

    provider = get_object_or_404(ServiceProviderProfile, user=request.user)
    tasks = (
        Task.objects.filter(service_provider=provider)
        .select_related('order', 'order__package', 'order__venue')
        .order_by('-id')
    )

    return render(
        request,
        'providerTasks.html',
        {'tasks': tasks}
    )


@login_required
def providerTaskUpdate(request, taskId):
    profile = UserProfile.objects.get(user=request.user)
    if profile.role != 'PROVIDER':
        return redirect('login')

    provider = get_object_or_404(ServiceProviderProfile, user=request.user)
    task = get_object_or_404(Task, id=taskId, service_provider=provider)

    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(Task.TASK_STATUS_CHOICES):
            task.status = status
            task.save(update_fields=['status'])

    return redirect('providerTasks')
