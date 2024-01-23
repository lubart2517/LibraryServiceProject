import datetime

from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from library.models import Book, Borrowing, Payment
from library.serializers import (
    BookSerializer,
    BorrowingSerializer,
    PaymentSerializer,
)
from library.permissions import IsAdminOrReadOnly


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
    permission_classes = (IsAdminOrReadOnly,)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


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
    permission_classes = (IsAdminOrReadOnly,)

    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)