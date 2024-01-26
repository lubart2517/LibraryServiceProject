import os
import datetime
import requests
import stripe
from django.db import transaction
from django.conf import settings
from django.shortcuts import redirect, reverse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from dotenv import load_dotenv
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Subquery, OuterRef, Count, F
from django.http import JsonResponse
from django.core.serializers import serialize

from library.models import Book, Borrowing, Payment
from library.serializers import (
    BookSerializer,
    BorrowingSerializer,
    BorrowingCreateSerializer,
    PaymentSerializer,
    CardInformationSerializer
)
from library.permissions import (
    IsAdminOrReadOnly,
    IsAllowedToCreateOrAdmin,
)

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

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


def create_checkout_session(borrowing_id, payment_id):
    try:
        borrowing = Borrowing.objects.get(id=borrowing_id)
        diff = int((borrowing.expected_return_date - datetime.datetime.now().date()).days)
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': int(borrowing.book.daily_fee * 100 * diff),
                        'product_data': {
                            'name': borrowing.book.title,
                        }
                    },
                    'quantity': 1,
                },
            ],
            metadata={
                "borrowing_id": borrowing.id
            },
            mode='payment',
            # success_url=reverse("library:payments", kwargs={'borrowing.id': borrowing.id}) + '?success=true',
            success_url=settings.SITE_URL + '?succcess=true',
            cancel_url=settings.SITE_URL + '?canceled=true',
        )
        payment = Payment.objects.get(id=payment_id)
        payment.session_url = checkout_session.url,
        payment.session_id = checkout_session.id,
        payment.save()
        return checkout_session.url
    except Exception as e:
        return Response({'msg': 'something went wrong while creating stripe session', 'error': str(e)}, status=500)


class BorrowingViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Borrowing.objects
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
        self.queryset = Borrowing.objects
        if not request.user.is_staff:
            self.queryset = self.queryset.filter(user=request.user)

        serializer = self.get_serializer(self.queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        book = Book.objects.get(id=serializer.validated_data["book"].id)
        if book.inventory == 0:
            return Response(
                {
                    f"There are no more inventories of the book {book.title} in the library"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        else:
            with transaction.atomic():
                book.inventory -= 1
                book.save()
                borrowing = serializer.save(user=self.request.user)
                url = (f"https://api.telegram.org/"
                       f"bot{os.environ.get("TELEGRAM_BOT_TOKEN")}/"
                       f"sendMessage?chat_id={os.environ.get("TELEGRAM_USER_ID")}"
                       f"&text=new borrowing of {book.title} book. Only"
                       f"{book.inventory} of copies left"
                       )
                requests.get(url)
                diff = int((borrowing.expected_return_date - datetime.datetime.now().date()).days)
                payment = Payment.objects.create(
                    status="PENDING",
                    type="PAYMENT",
                    borrowing=borrowing,
                    session_url="",
                    session_id="",
                    money_to_pay=borrowing.book.daily_fee * diff,
                )
                payment.save()
                return create_checkout_session(borrowing.id, payment.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        new_data = {"payment_session_url": response}
        new_data.update(serializer.data)
        return Response(new_data, status=status.HTTP_201_CREATED, headers=headers)

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
        """Endpoint to view route flights"""
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
                serializer = BorrowingDetailSerializer(borrowing)
                return Response(serializer.data, status=status.HTTP_200_OK)


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
    permission_classes = (IsAllowedToCreateOrAdmin,)

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


stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


@csrf_exempt
def stripe_webhook_view(request, payment_id):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_SECRET_WEBHOOK
        )
    except ValueError as e:
        # Invalid payload
        return Response(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return Response(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        print(session)
        borrowing_id = session['metadata']['borrowing_id']
        borrowing = Borrowing.objects.get(id=borrowing_id)
        # sending confirmation message
        url = (f"https://api.telegram.org/"
               f"bot{os.environ.get("TELEGRAM_BOT_TOKEN")}/"
               f"sendMessage?chat_id={os.environ.get("TELEGRAM_USER_ID")}"
               f"&text=Thank for your purchase your order is ready."
               f"{borrowing.book.title}"
               )
        requests.get(url)
        payment = Payment.objects.get(id=payment_id)
        payment.status = "PAID"
        payment.save()
        # Passed signature verification
        return Response(status=status.HTTP_200_OK)
