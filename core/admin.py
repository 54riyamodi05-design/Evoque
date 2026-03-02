from django.contrib import admin
from .models import *

# Register your models here.

admin.site.register(UserProfile)
admin.site.register(ServiceProviderProfile)
admin.site.register(Category)
admin.site.register(Package)
admin.site.register(Order)
admin.site.register(Payment)
admin.site.register(Task)
admin.site.register(Notification)
admin.site.register(CustomPackage)
admin.site.register(Venue)
