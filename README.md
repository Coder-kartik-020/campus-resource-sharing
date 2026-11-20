# Campus Marketplace
A student-focused buy/sell marketplace MVP built with Flask and SQLite.

## Run locally
1. Create/activate your Python virtual environment.
2. `pip install -r requirements.txt`
3. `python app.py`
4. Open http://127.0.0.1:5000

## Features
- Registration, login, logout
- Browse and search listings, category filter
- Create listing with image upload
- Listing detail, favourites, My Ads and delete own listing
- Buyer/seller conversation threads and message posting
- Profile editing

## Notes
- Phone OTP is not implemented; a real SMS provider must be connected for OTP verification.
- Location button uses browser geolocation permission and saves coordinates as a location label. Reverse geocoding/campus location lookup is not configured.
- Images are limited to JPG, JPEG, PNG and WEBP, 8 MB maximum.
- For deployment, configure a strong `SECRET_KEY`; persistent disk/storage is recommended for SQLite and uploaded images.
