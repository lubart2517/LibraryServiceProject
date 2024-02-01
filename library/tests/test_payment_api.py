import datetime

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIClient
from library.models import Book, Borrowing, Payment
from library.serializers import (
    BookSerializer,
    BorrowingSerializer,
    PaymentSerializer,
)

# Assuming the following URL configurations
BOOK_URL = reverse("library:book-list")
BORROWING_URL = reverse("library:borrowing-list")
PAYMENT_URL = reverse("library:payment-list")


def sample_book(**params):
    defaults = {
        "title": "New Book",
        "author": "Author Name",
        "cover": "HARD",
        "inventory": 5,
        "daily_fee": "10.00",
    }
    defaults.update(params)

    return Book.objects.create(**defaults)


def sample_borrowing(user, **params):
    book = sample_book()
    date_format = "%Y-%m-%d"
    expected_return_date = datetime.datetime.strftime(
        datetime.datetime.now() + datetime.timedelta(days=3),
        date_format,
    )
    defaults = {
        "book": book,
        "expected_return_date": expected_return_date,
        "user": user
    }
    defaults.update(params)
    return Borrowing.objects.create(**defaults)


def sample_payment(user, **params):
    borrowing = sample_borrowing(user)
    defaults = {
        "status": "PENDING",
        "type": "FINE",
        "borrowing": borrowing,
        "session_url": "",
        "session_id": "",
        "money_to_pay": 10
    }
    defaults.update(params)
    return Payment.objects.create(**defaults)


def payment_detail_url(payment_id):
    return reverse("library:payment-detail", args=[payment_id])


class UnauthenticatedPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_payments(self):
        # Test authentication is required for listing payments
        res = self.client.get(PAYMENT_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedPaymentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "testpass",
        )
        self.client.force_authenticate(self.user)

    def test_list_payments(self):
        # Test listing borrowings with an authenticated user
        sample_payment(self.user)
        sample_payment(self.user)

        res = self.client.get(PAYMENT_URL)

        payments = Payment.objects.order_by("id")
        serializer = PaymentSerializer(payments, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_payment_detail(self):
        # Test retrieving payment details with an authenticated user
        payment = sample_payment(self.user)
        url = payment_detail_url(payment.id)
        res = self.client.get(url)

        serializer = PaymentSerializer(payment)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_payment(self):
        # Test creating a payment with an authenticated user (forbidden)
        borrowing = sample_borrowing(self.user)
        payload = {
            "status": "PENDING",
            "type": "FINE",
            "borrowing": borrowing,
            "session_url": "",
            "session_id": "",
            "money_to_pay": 10
        }
        res = self.client.post(PAYMENT_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminLibraryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            "admin@admin.com", "testpass", is_staff=True
        )
        self.client.force_authenticate(self.admin_user)

