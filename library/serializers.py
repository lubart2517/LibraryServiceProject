from rest_framework import serializers

from library.models import Book, Borrowing, Payment


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ("title", "author", "cover", "inventory", "daily_fee")


class BorrowingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Borrowing
        fields = (
            "borrow_date",
            "expected_return_date",
            "actual_return_date",
            "book",
            "user",
        )


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "status",
            "type",
            "borrowing",
            "session_url",
            "session_id",
            "money_to_pay",
        )
