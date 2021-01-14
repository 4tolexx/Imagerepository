from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse, reverse_lazy
from django.contrib.auth.models import User
from django.views import View
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.generic import (
    CreateView, 
    ListView, 
    DetailView, 
    UpdateView, 
    TemplateView,
    DeleteView
)
from .models import (
    Photo, 
    Order, 
    OrderPhoto, 
    Coupon, 
    Payment, 
    UserProfile,
    Address,
)
from .forms import (
    PaymentForm, 
    CouponForm, 
    CheckoutForm,
)
import stripe



def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid



class PhotoCreateView(LoginRequiredMixin, CreateView):
    model = Photo
    fields  = ["image", "description", "price", "discount_price"]
    template_name = "imageapp/add_image_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)



class PhotoDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Photo
    template_name_suffix = "_confirm_delete"
    success_url = reverse_lazy("imageapp:photo-list")

    def test_func(self):
        photo = self.get_object()
        if self.request.user == photo.user:
            return True
        return False



class PhotoDetailView(DetailView):
    model = Photo
    context_object_name = "photo"
    template_name = "imageapp/image_detail.html"


class PhotoListView(ListView):
    model = Photo
    paginate_by = 10
    context_object_name = "photos"
    template_name = "imageapp/image_list.html"



class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'imageapp/order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("imageapp:photo-list")



@login_required
def add_to_cart(request, slug):
    photo = get_object_or_404(Photo, slug=slug)
    order_photo, created = OrderPhoto.objects.get_or_create(
        photo=photo,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.photos.filter(photo__slug=photo.slug).exists():
            order_photo.quantity += 1
            order_photo.save()
            messages.info(request, "This item quantity was updated.")
            return redirect("imageapp:order-summary")
        else:
            order.photos.add(order_photo)
            messages.info(request, "This item was added to your cart.")
            return redirect("imageapp:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.photos.add(order_photo)
        messages.info(request, "This item was added to your cart.")
        return redirect("imageapp:order-summary")


@login_required
def remove_from_cart(request, slug):
    photo = get_object_or_404(Photo, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.photos.filter(photo__slug=photo.slug).exists():
            order_photo = OrderPhoto.objects.filter(
                photo=photo,
                user=request.user,
                ordered=False
            )[0]
            order.photos.remove(order_photo)
            order_photo.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("imageapp:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("imageapp:photo-list", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("imageapp:photo-list", slug=slug)



@login_required
def remove_single_item_from_cart(request, slug):
    photo = get_object_or_404(Photo, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.photos.filter(photo__slug=photo.slug).exists():
            order_photo = OrderPhoto.objects.filter(
                photo=photo,
                user=request.user,
                ordered=False
            )[0]
            if order_photo.quantity > 1:
                order_photo.quantity -= 1
                order_photo.save()
            else:
                order.photos.remove(order_photo)
            messages.info(request, "This item quantity was updated.")
            return redirect("imageapp:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("imageapp:photo-list", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("imageapp:photo-list", slug=slug)



class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True
            )
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})

            billing_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True
            )
            if billing_address_qs.exists():
                context.update(
                    {'default_billing_address': billing_address_qs[0]})
            return render(self.request, "imageapp/checkout.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("imageapp:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():

                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    print("Using the defualt shipping address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No default shipping address available")
                        return redirect('imageapp:checkout')
                else:
                    print("User is entering a new shipping address")
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()

                    else:
                        messages.info(
                            self.request, "Please fill in the required shipping address fields")

                use_default_billing = form.cleaned_data.get(
                    'use_default_billing')
                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')

                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Using the defualt billing address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='B',
                        default=True
                    )
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No default billing address available")
                        return redirect('imageapp:checkout')
                else:
                    print("User is entering a new billing address")
                    billing_address1 = form.cleaned_data.get(
                        'billing_address')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()

                    else:
                        messages.info(
                            self.request, "Please fill in the required billing address fields")

                payment_option = form.cleaned_data.get('payment_option')

                if payment_option == 'S':
                    return redirect('imageapp:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('imageapp:payment', payment_option='paypal')
                else:
                    messages.warning(
                        self.request, "Invalid payment option selected")
                    return redirect('imageapp:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("imageapp:order-summary")


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
                'STRIPE_PUBLIC_KEY' : settings.STRIPE_PUBLIC_KEY
            }
            userprofile = self.request.user.userprofile
            if userprofile.one_click_purchasing:
                # fetch the users card list
                cards = stripe.Customer.list_sources(
                    userprofile.stripe_customer_id,
                    limit=3,
                    object='card'
                )
                card_list = cards['data']
                if len(card_list) > 0:
                    # update the context with the default card
                    context.update({
                        'card': card_list[0]
                    })
            return render(self.request, "imageapp/payment.html", context)
        else:
            messages.warning(
                self.request, "You have not added a billing address")
            return redirect("imageapp:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST)
        userprofile = UserProfile.objects.get(user=self.request.user)
        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            if save:
                if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                    customer = stripe.Customer.retrieve(
                        userprofile.stripe_customer_id)
                    customer.sources.create(source=token)

                else:
                    customer = stripe.Customer.create(
                        email=self.request.user.email,
                    )
                    customer.sources.create(source=token)
                    userprofile.stripe_customer_id = customer['id']
                    userprofile.one_click_purchasing = True
                    userprofile.save()

            amount = int(order.get_total() * 100)

            try:

                if use_default or save:
                    # charge the customer because we cannot charge the token more than once
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="usd",
                        customer=userprofile.stripe_customer_id
                    )
                else:
                    # charge once off on the token
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="usd",
                        source=token
                    )

                # create the payment
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()

                # assign the payment to the order

                order_items = order.items.all()
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()

                messages.success(self.request, "Your order was successful!")
                return redirect("imageapp:photo-list")

            except stripe.error.CardError as e:
                body = e.json_body
                err = body.get('error', {})
                messages.warning(self.request, f"{err.get('message')}")
                return redirect("imageapp:photo-list")

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                messages.warning(self.request, "Rate limit error")
                return redirect("imageapp:photo-list")

            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                print(e)
                messages.warning(self.request, "Invalid parameters")
                return redirect("imageapp:photo-list")

            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                messages.warning(self.request, "Not authenticated")
                return redirect("imageapp:photo-list")

            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                messages.warning(self.request, "Network error")
                return redirect("imageapp:photo-list")

            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                messages.warning(
                    self.request, "Something went wrong. You were not charged. Please try again.")
                return redirect("imageapp:photo-list")

            except Exception as e:
                # send an email to ourselves
                messages.warning(
                    self.request, "A serious error occurred. We have been notifed.")
                return redirect("imageapp:photo-list")

        messages.warning(self.request, "Invalid data received")
        return redirect("/payment/stripe/")



def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("imageapp:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("imageapp:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You do not have an active order")
                return redirect("imageapp:checkout")



class UserImageDetailView(DetailView):
    model = User
    context_object_name = 'user'
    template_name = "imageapp/user_image_detail.html"

    def get_context_data(self, **kwargs):
        context = super(UserImageDetailView, self).get_context_data(**kwargs)
        context['photos'] = Photo.objects.filter(user__username=self.kwargs['username'])
        return context

    def get_object(self):
        return get_object_or_404(self.model, username=self.kwargs['username'])



class UserImageEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Photo
    fields = ["image", "description", "price", "discount_price"]
    template_name = "imageapp/add_image_form.html"

    def test_func(self):
        photo = self.get_object()
        if self.request.user == photo.user:
            return True
        return False


