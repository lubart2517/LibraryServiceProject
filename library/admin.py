from django.contrib import admin

from library.models import (
    Borrowing,
    Book,
    Payment
)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    pass


@admin.register(Borrowing)
class BorrowingAdmin(admin.ModelAdmin):
    pass


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    pass
