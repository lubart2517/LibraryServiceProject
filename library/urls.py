from rest_framework import routers
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from library.views import (
    BookViewSet,
    BorrowingViewSet,
    PaymentViewSet,
    check_payment,
    cancel_payment,
    check_fine,
    cancel_fine
)


router = routers.DefaultRouter()
router.register("books", BookViewSet)
router.register("borrowings", BorrowingViewSet)
router.register("payments", PaymentViewSet)

urlpatterns = router.urls + [
    path("check_payment/<int:payment_id>/", check_payment, name="check_payment"),
    path("cancel_payment/<int:payment_id>/", cancel_payment, name="cancel_payment"),
    path("check_fine/<int:payment_id>/", check_fine, name="check_fine"),
    path("cancel_fine/<int:payment_id>/", cancel_fine, name="cancel_fine"),
]

app_name = "library"
