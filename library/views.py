import os
import datetime
import requests
import stripe

from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action, api_view
from rest_framework.reverse import reverse
from rest_framework.response import Response
from dotenv import load_dotenv

from library.models import Book, Borrowing, Payment
from library.serializers import (
    BookSerializer,
    BorrowingSerializer,
    BorrowingCreateSerializer,
    PaymentSerializer,
)
from library.permissions import (
    IsAdminOrReadOnly,
    IsAllowedToCreateOrAdmin,
    IsAllowedToViewOwnOrAdmin
)

FINE_MULTIPLIER = 2

load_dotenv()
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


class BookViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Book.objects
    serializer_class = BookSerializer
    permission_classes = (IsAdminOrReadOnly,)


def check_unpaid_borrowings(user_id):
    has_unpaid_borrowings = Borrowing.objects.filter(
        user__id=user_id,
        payments__status__in=["PENDING", "EXPIRED"]
    ).exists()
    return has_unpaid_borrowings


def send_telegram_message(text):
    url = (f"https://api.telegram.org/"
           f"bot{os.environ.get("TELEGRAM_BOT_TOKEN")}/"
           f"sendMessage?chat_id={os.environ.get("TELEGRAM_USER_ID")}"
           f"&text={text}"
           )
    requests.get(url)


def create_session(
        borrowing_id,
        payment_id,
        success_url,
        cancel_url,
        money,
        is_fine
):
    try:
        borrowing = Borrowing.objects.get(id=borrowing_id)
        if is_fine:
            name = f"FINE for book {borrowing.book.title}"
        else:
            name = f"Payment for book {borrowing.book.title}"
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(money * 100),
                        "product_data": {
                            "name": name,
                        }
                    },
                    "quantity": 1,
                },
            ],
            metadata={
                "borrowing_id": borrowing.id
            },
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
        )
        payment = Payment.objects.get(id=payment_id)
        payment.session_url = checkout_session.url
        payment.session_id = checkout_session.id
        payment.save()
        return checkout_session.url
    except Exception as e:
        return Response(
            {"msg": "something went wrong while creating stripe session",
             "error": str(e)}, status=500)


class BorrowingViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Borrowing.objects.select_related(
        "book"
    ).prefetch_related("payments")
    serializer_class = BorrowingSerializer
    permission_classes = (IsAllowedToCreateOrAdmin,)

    def get_serializer_class(self):
        if self.action == "create":
            return BorrowingCreateSerializer

        return BorrowingSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "is_active",
                type=OpenApiTypes.STR,
                description=(
                    "Filter by state of borrowing(returned or not)"
                    "(ex. ?is_active=True)"
                ),
            ),
            OpenApiParameter(
                "user_id",
                type={"type": "number"},
                description="Filter by user id (ex. ?user_id=2)",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        if not request.user.is_staff:
            self.queryset = self.queryset.filter(user=request.user)

        serializer = self.get_serializer(self.queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer, request):
        book = Book.objects.get(id=serializer.validated_data["book"].id)
        if book.inventory == 0:
            return Response(
                {
                    f"There are no more inventories of the book "
                    f"{book.title} in the library"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            with transaction.atomic():
                book.inventory -= 1
                book.save()
                borrowing = serializer.save(user=self.request.user)
                send_telegram_message(
                    f"New borrowing of {book.title} book. "
                    f"Only {book.inventory} of copies left")
                money = int(
                    (
                        borrowing.expected_return_date
                        - datetime.datetime.now().date()
                    ).days
                ) * borrowing.book.daily_fee
                payment = Payment.objects.create(
                    status="PENDING",
                    type="PAYMENT",
                    borrowing=borrowing,
                    session_url="",
                    session_id="",
                    money_to_pay=money,
                )
                payment.save()
                success_url = reverse(
                    "library:check_payment",
                    args=[payment.id],
                    request=request
                )
                cancel_url = reverse(
                    "library:cancel_payment",
                    args=[payment.id],
                    request=request
                )
                return create_session(
                    borrowing.id,
                    payment.id,
                    success_url,
                    cancel_url,
                    money,
                    is_fine=False
                )

    def create(self, request, *args, **kwargs):
        if check_unpaid_borrowings(request.user.id):
            response_text = {"message": "You have pending or expired payments"
                             }
            return Response(response_text, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = self.perform_create(serializer, request)
        headers = self.get_success_headers(serializer.data)
        new_data = {"payment_session_url": response}
        new_data.update(serializer.data)
        return Response(
            new_data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    def get_queryset(self):
        """Retrieve the borrowing with filters"""
        is_active = self.request.query_params.get("is_active")
        user_id = self.request.query_params.get("user_id")
        queryset = self.queryset

        if is_active:
            if is_active == "True":
                queryset = queryset.filter(
                    actual_return_date__isnull=True
                )
            elif is_active == "False":
                queryset = queryset.filter(
                    actual_return_date__isnull=False
                )

        if user_id:
            queryset = queryset.filter(user__id=user_id)

        return queryset.distinct()

    @action(
        methods=["GET"],
        detail=True,
        url_path="return",
        permission_classes=[IsAllowedToCreateOrAdmin],
    )
    def return_me(self, request, pk=None):
        """Endpoint to return borrowings"""
        borrowing = self.get_object()
        if borrowing.actual_return_date:
            return Response(
                status=status.HTTP_304_NOT_MODIFIED,
            )
        else:
            with transaction.atomic():
                borrowing.actual_return_date = datetime.datetime.now().date()
                borrowing.save()
                book = borrowing.book
                book.inventory += 1
                book.save()
                send_telegram_message(
                    f"Borrowing {borrowing.id} of {book.title} was returned."
                    f"There are {book.inventory} of copies now")
                if (
                        borrowing.actual_return_date
                        > borrowing.expected_return_date
                ):
                    money = int(
                        (
                            borrowing.actual_return_date
                            - borrowing.expected_return_date
                        ).days
                    ) * borrowing.book.daily_fee * FINE_MULTIPLIER
                    payment = Payment.objects.create(
                        status="PENDING",
                        type="FINE",
                        borrowing=borrowing,
                        session_url="",
                        session_id="",
                        money_to_pay=money,
                    )
                    payment.save()
                    success_url = reverse(
                        "library:check_fine",
                        args=[payment.id],
                        request=request
                    )
                    cancel_url = reverse(
                        "library:cancel_fine",
                        args=[payment.id],
                        request=request
                    )
                    is_fine = True
                    response = create_session(
                        borrowing.id,
                        payment.id,
                        success_url,
                        cancel_url,
                        money,
                        is_fine
                    )
                    new_data = {"payment_session_url": response}
                    return Response(new_data, status=status.HTTP_201_CREATED)
                else:
                    serializer = BorrowingSerializer(borrowing)
                    return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        methods=["GET"],
        detail=True,
        url_path="renew_session",
        permission_classes=[IsAllowedToCreateOrAdmin],
    )
    def renew_session(self, request, pk=None):
        """Endpoint to renew borrowing payment session"""
        borrowing = self.get_object()
        payment = borrowing.payments.filter(status="EXPIRED").first()
        is_fine = payment.type == "FINE"
        if is_fine:
            success_url = reverse(
                "library:check_fine",
                args=[payment.id],
                request=request
            )
            cancel_url = reverse(
                "library:cancel_fine",
                args=[payment.id],
                request=request
            )
        else:
            success_url = reverse(
                "library:check_payment",
                args=[payment.id],
                request=request
            )
            cancel_url = reverse(
                "library:cancel_payment",
                args=[payment.id],
                request=request
            )
        money = payment.money_to_pay

        return Response(create_session(
            borrowing_id=borrowing.id,
            payment_id=payment.id,
            success_url=success_url,
            cancel_url=cancel_url,
            money=money,
            is_fine=is_fine

        ))


class PaymentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Payment.objects
    serializer_class = PaymentSerializer
    permission_classes = (IsAllowedToViewOwnOrAdmin,)

    def get_queryset(self):
        """Retrieve the payments with filters"""
        user_id = self.request.query_params.get("user_id")
        queryset = self.queryset

        if user_id:
            queryset = queryset.filter(borrowing__user__id=user_id)

        return queryset.distinct()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "user_id",
                type={"type": "number"},
                description="Filter by borrowing__user id (ex. ?user_id=2)",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        if request.user.is_staff:
            return super().list(request, *args, **kwargs)
        else:
            self.queryset = Payment.objects.filter(borrowing__user=request.user)
            return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(("GET",))
def check_payment(request, payment_id):
    payment = Payment.objects.get(id=payment_id)
    borrowing_id = payment.borrowing.id
    borrowing = Borrowing.objects.get(id=borrowing_id)
    send_telegram_message(f"Payment for borrowing{borrowing_id} was paid."
                          f"Book is {borrowing.book.title}")

    payment.status = "PAID"
    payment.save()
    response_text = {"message": f"Thank for your order {borrowing.book.title}"
                     }
    return Response(response_text, status=status.HTTP_200_OK)


@api_view(("GET",))
def check_fine(request, payment_id):
    payment = Payment.objects.get(id=payment_id)
    send_telegram_message(f"Fine for borrowing {payment.borrowing.id} was paid")

    payment.status = "PAID"
    payment.save()
    response_text = {
        "message": f"Thank for paying your fine"
        f"{payment.borrowing.user.email}"
    }
    return Response(response_text, status=status.HTTP_200_OK)


@api_view(("GET",))
def cancel_payment(request, payment_id):
    payment = Payment.objects.get(id=payment_id)
    borrowing_id = payment.borrowing.id
    send_telegram_message(f"Payment {payment_id} for borrowing"
                          f" {borrowing_id} was canceled"
                          f"User will be able to pay by "
                          f"link during 24 hours")
    response_text = {"result": "Payment was canceled",
                     "payment_url": f"{payment.session_url}"
                     }
    return Response(response_text, status=status.HTTP_200_OK)


@api_view(("GET",))
def cancel_fine(request, payment_id):
    payment = Payment.objects.get(id=payment_id)
    borrowing_id = payment.borrowing.id
    send_telegram_message(f"Payment fine {payment_id} for borrowing "
                          f"{borrowing_id} was canceled"
                          f"User will be able to pay by "
                          f"link during 24 hours")
    response_text = {"result": "Fine payment was canceled",
                     "payment_url": f"{payment.session_url}"
                     }
    return Response(response_text, status=status.HTTP_200_OK)
