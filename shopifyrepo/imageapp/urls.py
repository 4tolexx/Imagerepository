from django.urls import path
from django.conf.urls import url
from . import views

app_name = "imageapp"

urlpatterns = [
    path('checkout/', views.CheckoutView.as_view(), name='checkout'),
    path('', views.PhotoListView.as_view(), name='photo-list'),
    path('add-photo/', views.PhotoCreateView.as_view(), name='add-photo'),
    path("photo-delete/<int:pk>/", views.PhotoDeleteView.as_view(), name="photo-delete"),
    path('order-summary/', views.OrderSummaryView.as_view(), name='order-summary'),
    path('photo-details/<slug:slug>/', views.PhotoDetailView.as_view(), name='photo-details'),
    path('add-to-cart/<slug:slug>/', views.add_to_cart, name='add-to-cart'),
    path('add-coupon/', views.AddCouponView.as_view(), name='add-coupon'),
    path('remove-from-cart/<slug:slug>/', views.remove_from_cart, name='remove-from-cart'),
    path('remove-item-from-cart/<slug:slug>/', views.remove_single_item_from_cart,
         name='remove-single-item-from-cart'),
    path('payment/<payment_option>/', views.PaymentView.as_view(), name='payment'),
    url(r"^(?P<username>[-\w]+)$", views.UserImageDetailView.as_view(), name="user-image-detail"),
    path("user-image-edit/<int:pk>/", views.UserImageEditView.as_view(), name="user-image-edit"),

]