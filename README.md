# LibraryServiceProject
## Introduction and Overview

A RESTful API for a library service.
Allow manage  Books, Borrowings, Payments.

## Installation Instructions
Install PostgreSQL and create a database.
Clone the GitHub repository: 
git clone https://github.com/lubart2517/LibraryServiceProject.git
Navigate to the project directory: cd LibraryServiceProject
Create a virtual environment and activate it:
python -m venv .venv
source venv/bin/activate
Install required dependencies: pip install -r requirements.txt
Create your ovn .env file according to .env.sample

To use sqlite db, uncomment sqlite db config in settings and comment postgres

Run database migrations: python manage.py migrate
Start the development server: python manage.py runserver

This project should be launched in docker container (use docker-compose up)


## Usage Guidelines
To create superuser:
python manage.py createsuperuser

To load fixture data:
python manage.py loaddata db_to_load.json

To create user:
api/user/register

To get access and refresh tokens:
api/user/token

To visit start page, add Authorization header with value:
"Bearer <your access token>" and go to /api/airport/


## Configuration Details
Documentation is located at /api/doc/swagger/: 
This means that the API documentation is located at the URL /api/doc/swagger/

### To set up telegram notifications:

1. Write to https://t.me/BotFather
Choose valid new bot name.
2. After creation, save your bot api token.
3. Paste this token to .env file as TELEGRAM_BOT_TOKEN 
variable. Also, write any message to your bot
to open possibility of receiving messages from bot.
4. Write to https://t.me/userinfobot and get your id.
Save this id and paste to .env file as TELEGRAM_USER_ID.
After setting those variables, you will receive message from
bot after creation new borrowing.

### To launch django q tasks:
Login to admin page, create cheduled tasks for functions in library.tasks.py
Launch python manage.py qcluster command in separate terminal window

### To set up stripe support:
Login to stripe.com and get your STRIPE_SECRET_KEY and 
STRIPE_PUBLISHABLE_KEY, add their values to .env file

## Features
API is JWT authenticated: 
This means that the admin panel is protected using JSON Web Tokens (JWTs). 
JWTs are a secure way to authenticate users without storing their passwords 
on the server
