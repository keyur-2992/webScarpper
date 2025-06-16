# Web Scraper for Booking.com

This project is a web scraper that extracts hotel data from Booking.com using Playwright.

## How It Works

1. **Setup**: The script sets up a SQLite database to store hotel data.
2. **Browser Launch**: It launches a Chromium browser in non-headless mode (visible window).
3. **Navigation**: The script navigates to Booking.com and waits for you to enter your search details.
4. **Data Extraction**: Once you perform a search, the script extracts hotel details (name, price, rating, address, link) from the search results.
5. **Database Storage**: The extracted data is saved into a SQLite database (`hotels.db`).

## Detailed Explanation of the Script

### 1. **Database Setup**
- The script creates a SQLite database (`hotels.db`) with two tables:
  - `search_sessions`: Stores search parameters (location, check-in date, check-out date, guests).
  - `hotels`: Stores hotel details (name, price, rating, address, link) linked to a search session.

### 2. **Browser Automation**
- The script uses Playwright to launch a Chromium browser in non-headless mode, allowing you to see the automation in action.
- It navigates to Booking.com and waits for you to enter your search details manually.

### 3. **Data Extraction**
- Once you perform a search, the script extracts the following data from each hotel card:
  - **Name**: The name of the hotel.
  - **Price**: The price of the hotel.
  - **Rating**: The numerical rating of the hotel.
  - **Address**: The address of the hotel.
  - **Link**: The URL to the hotel's page on Booking.com.

### 4. **Data Storage**
- The extracted data is saved into the SQLite database:
  - A new search session is created in the `search_sessions` table.
  - Hotel details are inserted into the `hotels` table, linked to the search session.

### 5. **Error Handling**
- The script includes error handling to manage timeouts, missing data, and other exceptions during data extraction.

## Installation

1. **Install Python Dependencies**:
   ```sh
   pip install playwright
   python -m playwright install
   ```

2. **Run the Script**:
   ```sh
   python main.py
   ```

## Notes

- The script uses Playwright to automate browser interactions.
- The browser window will pop up, allowing you to see the automation in action.
- Hotel data is stored in a SQLite database (`hotels.db`).
