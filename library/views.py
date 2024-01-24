import os
import datetime
import requests
from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import Response
from dotenv import load_dotenv
from datetime import timedelta

from library.models import Book, Borrowing, Payment
from library.serializers import (
    BookSerializer,
    BorrowingSerializer,
    BorrowingDetailSerializer,
    BorrowingCreateSerializer,
    PaymentSerializer,
)
from library.permissions import (
    IsAdminOrReadOnly,
    IsAllowedToCreateOrAdmin,
)

load_dotenv()


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
        if self.action == "retrieve":
            return BorrowingDetailSerializer

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
        if request.user.is_staff:
            return super().list(request, *args, **kwargs)
        else:
            self.queryset = Borrowing.objects.filter(user=request.user)
            return super().list(request, *args, **kwargs)

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
                serializer.save(user=self.request.user)

                url = (f"https://api.telegram.org/"
                       f"bot{os.environ.get("TELEGRAM_BOT_TOKEN")}/"
                       f"sendMessage?chat_id={os.environ.get("TELEGRAM_USER_ID")}"
                       f"&text=new borrowing of {book.title} book. Only"
                       f"{book.inventory} of copies left"
                       )
                requests.get(url)

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