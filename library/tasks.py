import requests
import os
from dotenv import load_dotenv
import datetime
from datetime import timedelta

from library.models import Borrowing

load_dotenv()


def send_telegram_message():
    tomorrow = (datetime.datetime.now() + timedelta(days=1)).date()
    text = ""
    overdue_borrowings = Borrowing.objects.filter(expected_return_date__lte=tomorrow)
    if not overdue_borrowings:
        text = "No borrowings overdue today!"
    else:
        text = "There are such overdue borrowings\n"
        for borrowing in overdue_borrowings:
            text += (f"User {borrowing.user.email} borrowed book "
                     f"{borrowing.book.title} at {borrowing.borrow_date} "
                     f"and will have to return by {borrowing.expected_return_date}\n")
    url = (f"https://api.telegram.org/"
           f"bot{os.environ.get("TELEGRAM_BOT_TOKEN")}/"
           f"sendMessage?chat_id={os.environ.get("TELEGRAM_USER_ID")}"
           f"&text={text}"
           )
    requests.get(url)
