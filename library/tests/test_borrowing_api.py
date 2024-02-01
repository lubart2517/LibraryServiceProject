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


def borrowing_detail_url(borrowing_id):
    return reverse("library:borrowing-detail", args=[borrowing_id])


class UnauthenticatedBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_borrowings(self):
        # Test authentication is required for listing borrowings
        res = self.client.get(BORROWING_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedBorrowingApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "testpass",
        )
        self.client.force_authenticate(self.user)

    def test_list_borrowings(self):
        # Test listing borrowings with an authenticated user
        sample_borrowing(self.user)
        sample_borrowing(self.user)

        res = self.client.get(BORROWING_URL)

        borrowings = Borrowing.objects.order_by("id")
        serializer = BorrowingSerializer(borrowings, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_borrowing_detail(self):
        # Test retrieving book details with an authenticated user
        borrowing = sample_borrowing(self.user)
        url = borrowing_detail_url(borrowing.id)
        res = self.client.get(url)

        serializer = BorrowingSerializer(borrowing)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_borrowing(self):
        # Test creating a borrowing with an authenticated user
        book = sample_book()
        date_format = "%Y-%m-%d"
        expected_return_date = datetime.datetime.strftime(
            datetime.datetime.now() + datetime.timedelta(days=3),
            date_format,
        )
        payload = {
            "book": book.id,
            "expected_return_date": expected_return_date,
        }
        res = self.client.post(BORROWING_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)


class AdminLibraryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            "admin@admin.com", "testpass", is_staff=True
        )
        self.client.force_authenticate(self.admin_user)

