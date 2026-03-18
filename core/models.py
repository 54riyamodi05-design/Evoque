from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.utils import timezone

# Create your models here.

class UserProfile(models.Model):
    ROLE_CHOICES=(
        ('ADMIN', 'Admin'),
        ('PROVIDER', 'Service Provider'),
        ('CUSTOMER', 'Customer'), 
    )

    user=models.OneToOneField(User, on_delete=models.CASCADE)
    role=models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone=models.CharField(max_length=10)

    def __str__(self):
        return f"{self.user.username}-{self.role}"

class ServiceProviderProfile(models.Model):
    user=models.OneToOneField(User, on_delete=models.CASCADE)
    phone=models.CharField(max_length=10)
    status=models.BooleanField(default=False)

    def __str__(self):
        return self.user.username
    

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
class Package(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.category.name})"
    
class Venue(models.Model):
    name=models.CharField(max_length=50)
    address=models.TextField()
    capacity=models.PositiveIntegerField()
    price=models.DecimalField(max_digits=10, decimal_places=2)
    status=models.BooleanField(default=True)
    image=models.ImageField(upload_to='venues/',null=True,blank=True)

    def __str__(self):
        return self.name
    
class Order(models.Model):
    # Order lifecycle status
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    # Theme intensity chosen by customer
    THEME_CHOICES = (
        ('CLASSIC', 'Classic'),
        ('MODERATE', 'Moderate'),
        ('SUPREME', 'Supreme'),
    )

    # Who placed the order (Customer)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    # Which event package was selected
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    # Assigned service provider (Admin assigns later)
    service_provider = models.ForeignKey(
        ServiceProviderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_orders'
    )

    # Theme level selected for this booking
    theme_type = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        default='CLASSIC'
    )

    venue=models.ForeignKey(Venue, on_delete=models.CASCADE,null=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    seasonal_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00')
    )

    # When order was placed
    order_date = models.DateTimeField(auto_now_add=True)

    # Current order status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    def clean(self):
        if self.event_date and self.event_date < timezone.localdate():
            raise ValidationError({'event_date': 'Event date cannot be in the past.'})

    def get_seasonal_discount_percent(self):
        if not self.event_date or not self.package_id:
            return Decimal('0.00')

        category_name = (self.package.category.name or '').strip().lower()
        if category_name == 'wedding' and self.event_date.month in (11, 12, 1, 2):
            return Decimal('10.00')

        return Decimal('0.00')

    def get_final_price(self):
        """
        Calculates final price based on package base price
        and theme multiplier with seasonal discount.
        """
        THEME_MULTIPLIER = {
            'CLASSIC': Decimal(1.0),
            'MODERATE': Decimal(1.3),
            'SUPREME': Decimal(1.6),
        }
        multiplier = THEME_MULTIPLIER.get(self.theme_type, Decimal(1.0))
        themed_price = self.package.price * multiplier
        discount_percent = self.get_seasonal_discount_percent()
        discount_amount = (themed_price * discount_percent) / Decimal('100')
        return themed_price - discount_amount

    def save(self, *args, **kwargs):
        self.seasonal_discount_percent = self.get_seasonal_discount_percent()
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username}"


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('COD', 'Cash On Delivery'),
        ('ONLINE', 'Online'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
    )

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHOD_CHOICES
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='PENDING'
    )

    # For future payment gateway integration
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for Order #{self.order.id}"


class Task(models.Model):
    TASK_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    )

    service_provider = models.ForeignKey(ServiceProviderProfile, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=TASK_STATUS_CHOICES)

    def __str__(self):
        return f"Task for Order #{self.order.id}"


class Notification(models.Model):
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.content[:30]


class CustomPackage(models.Model):
    customer=models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name= 'customRequests'
    )
    category=models.ForeignKey(
        Category, 
        on_delete= models.CASCADE
    )
    title=models.CharField(max_length=100)
    description=models.TextField()
    expectedBudget=models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True
    )
    STATUS_CHOICES=(
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    status=models.CharField(
        max_length=20,
        choices=STATUS_CHOICES, 
        default='PENDING'
    )

    createdAt=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title}--{self.customer.username}"


