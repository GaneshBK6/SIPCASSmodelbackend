@echo off
pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate