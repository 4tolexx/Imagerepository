from django.contrib import admin
from .models import (
    Photo,
    Coupon,
    Payment, 
    OrderPhoto, 
    Order, 
    UserProfile,
    Address
)


admin.site.register(Photo)
admin.site.register(Coupon)
admin.site.register(UserProfile)
admin.site.register(Payment)
admin.site.register(Order)
admin.site.register(OrderPhoto)
admin.site.register(Address)