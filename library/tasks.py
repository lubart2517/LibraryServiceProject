import os
import datetime
import requests
import stripe
from dotenv import load_dotenv
from datetime import timedelta


from library.models import Borrowing, Payment

from library.views import send_telegram_message

load_dotenv()


def send_overdue_borrowings_report():
    tomorrow = (datetime.datetime.now() + timedelta(days=1)).date()
    overdue_borrowings = Borrowing.objects.filter(
        expected_return_date__lte=tomorrow
    )
    if not overdue_borrowings:
        text = "No borrowings overdue today!"
    else:
        text = "There are such overdue borrowings\n"
        for borrowing in overdue_borrowings:
            text += (
                f"User {borrowing.user.email} borrowed book "
                f"{borrowing.book.title} at {borrowing.borrow_date} "
                f"and will have to return by {borrowing.expected_return_date}\n"
            )
    send_telegram_message(text)


def check_expired_stripe_sessions():
    non_paid_payments = Payment.objects.filter(status="PENDING")
    for payment in non_paid_payments:
        if payment.session_url and payment.session_id:
            session = stripe.checkout.Session.retrieve(
                payment.session_id
            )
            if session.status == "expired":
                payment.status = "EXPIRED"
                payment.save()
