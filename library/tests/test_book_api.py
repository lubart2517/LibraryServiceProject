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


def book_detail_url(book_id):
    return reverse("library:book-detail", args=[book_id])


class UnauthenticatedLibraryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_book(self):
        # Test authentication is not required for listing books
        res = self.client.get(BOOK_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)


class AuthenticatedLibraryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            "test@test.com",
            "testpass",
        )
        self.client.force_authenticate(self.user)

    def test_list_books(self):
        # Test listing books with an authenticated user
        sample_book()
        sample_book()

        res = self.client.get(BOOK_URL)

        books = Book.objects.order_by("id")
        serializer = BookSerializer(books, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieve_book_detail(self):
        # Test retrieving book details with an authenticated user
        book = sample_book()
        url = book_detail_url(book.id)
        res = self.client.get(url)

        serializer = BookSerializer(book)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_create_book_forbidden(self):
        # Test creating a book with an authenticated user (forbidden)
        payload = {
            "title": "New Book",
            "author": "Author Name",
            "cover": "HARD",
            "inventory": 5,
            "daily_fee": "10.00",
        }
        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


class AdminLibraryApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = get_user_model().objects.create_user(
            "admin@admin.com", "testpass", is_staff=True
        )
        self.client.force_authenticate(self.admin_user)

    def test_create_book(self):
        # Test creating a book with an admin user
        payload = {
            "title": "New Book",
            "author": "Author Name",
            "cover": "HARD",
            "inventory": 5,
            "daily_fee": 10.00,
        }
        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        book = Book.objects.filter(title=payload["title"]).first()
        for key in payload.keys():
            self.assertEqual(payload[key], getattr(book, key))

    def test_update_book(self):
        # Test updating a book with an admin user
        payload = {
            "title": "New Book",
            "author": "Author Name",
            "cover": "HARD",
            "inventory": 5,
            "daily_fee": 10.00,
        }
        res = self.client.post(BOOK_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        book = Book.objects.filter(title=payload["title"]).first()
        book_url = book_detail_url(book.id)
        new_payload =  {
            "cover": "SOFT",
        }
        next_response = self.client.patch(book_url, new_payload)
        self.assertEqual(next_response.status_code, status.HTTP_200_OK)
