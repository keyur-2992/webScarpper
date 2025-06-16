import re
from playwright.sync_api import Playwright, sync_playwright, expect, TimeoutError
from six import raise_from
import sqlite3
import time
import os
from datetime import datetime, timedelta

def create_database():
    """Create the SQLite database and necessary tables if they don't exist."""
    conn = sqlite3.connect('hotels.db')
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS search_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        location TEXT NOT NULL,
        check_in_date TEXT NOT NULL,
        check_out_date TEXT NOT NULL,
        guests INTEGER NOT NULL,
        search_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create hotels table with session reference
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hotels (
        hotel_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        name TEXT NOT NULL,
        price TEXT NOT NULL,
        rating TEXT,
        address TEXT,
        link TEXT,
        FOREIGN KEY (session_id) REFERENCES search_sessions(session_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def get_search_parameters(page):
    """Extract search parameters from the Booking.com page quickly and reliably."""
    try:
        print("Extracting search parameters from Booking.com...")
        # Get location - try multiple selectors
        location = None
        selectors = [
            'input[name="ss"]',
            'input[data-testid="destination-input"]',
            'input[placeholder*="Where"]',
            'input[placeholder*="Destination"]'
        ]
        for selector in selectors:
            try:
                location = page.locator(selector).input_value()
                if location:
                    break
            except:
                continue
        if not location:
            url = page.url
            if 'booking.com/search' in url and 'ss=' in url:
                location = url.split('ss=')[1].split('&')[0]
        print(f"Location: {location}")

        # FASTEST: Try to get dates from URL first
        check_in = None
        check_out = None
        url = page.url
        if 'checkin=' in url and 'checkout=' in url:
            try:
                check_in = url.split('checkin=')[1].split('&')[0]
                check_out = url.split('checkout=')[1].split('&')[0]
            except Exception as e:
                print(f"URL date extraction failed: {e}")
        # If not found, try date buttons (should be quick)
        if not check_in or not check_out:
            try:
                date_buttons = page.locator('button[data-testid^="date-display-field"]').all()
                if len(date_buttons) >= 2:
                    check_in = date_buttons[0].get_attribute('data-date')
                    check_out = date_buttons[1].get_attribute('data-date')
            except Exception as e:
                print(f"Date button extraction failed: {e}")
        # Only as a last resort, try the slow date box selector (with short timeout)
        if not check_in or not check_out:
            try:
                date_box = page.locator('div[data-testid="searchbox-dates-container"]')
                if date_box.is_visible(timeout=2000):
                    date_text = date_box.inner_text()
                    date_pattern = r'[A-Za-z]{3}, ([A-Za-z]{3}) (\d{1,2}) \u2014 [A-Za-z]{3}, ([A-Za-z]{3}) (\d{1,2})'
                    match = re.search(date_pattern, date_text)
                    if match:
                        month_map = {
                            'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                            'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                            'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                        }
                        current_year = datetime.now().year
                        check_in = f"{current_year}-{month_map[match.group(1)]}-{match.group(2).zfill(2)}"
                        check_out = f"{current_year}-{month_map[match.group(3)]}-{match.group(4).zfill(2)}"
            except Exception as e:
                print(f"Date box extraction failed: {e}")
        print(f"Check-in: {check_in}")
        print(f"Check-out: {check_out}")

        # FASTEST: Try to get guests from URL first
        guests = None
        if 'group_adults=' in url:
            try:
                guests = url.split('group_adults=')[1].split('&')[0]
            except Exception as e:
                print(f"URL guest extraction failed: {e}")
        # Try input fields (should be quick)
        if not guests:
            guest_selectors = [
                'input[name="group_adults"]',
                'span[data-testid="occupancy-config"]',
                'div[data-testid="occupancy-config"]'
            ]
            for selector in guest_selectors:
                try:
                    guests = page.locator(selector).input_value()
                    if not guests:
                        guests = page.locator(selector).inner_text()
                        if guests:
                            guests = re.findall(r'\d+', guests)[0]
                    if guests:
                        break
                except:
                    continue
        if not guests:
            guests = "2"
        print(f"Guests: {guests}")
        if not location:
            print("Warning: Could not extract location")
            location = "Unknown Location"
        if not check_in or not check_out:
            print("Warning: Could not extract dates")
            today = datetime.now()
            check_in = today.strftime('%Y-%m-%d')
            check_out = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        return location, check_in, check_out, int(guests)
    except Exception as e:
        print(f"Error extracting search parameters: {e}")
        today = datetime.now()
        return "Unknown Location", today.strftime('%Y-%m-%d'), (today + timedelta(days=1)).strftime('%Y-%m-%d'), 2

def clean_rating(rating_text):
    """Extract just the numerical rating from the rating text."""
    try:
        # Extract the first number from the text (e.g., "Scored 7.9" -> "7.9")
        match = re.search(r'(\d+\.?\d*)', rating_text)
        if match:
            return match.group(1)
        return "No rating"
    except:
        return "No rating"

def load_all_hotels(page):
    """Scroll and load all available hotels."""
    print("Loading all available hotels...")
    last_height = 0
    no_new_hotels_count = 0
    max_attempts = 100
    
    for attempt in range(max_attempts):
        # Scroll to bottom quickly
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)  # Reduced wait time
        
        # Try to find and click load more button
        try:
            load_more = page.locator('button:has-text("Load more results")')
            if load_more.is_visible():
                load_more.click()
                time.sleep(0.5)  # Reduced wait time
        except:
            pass
        
        # Get current height and hotel count
        current_height = page.evaluate("document.body.scrollHeight")
        current_hotels = page.locator('div[data-testid="property-card"]').count()
        print(f"\rCurrently loaded {current_hotels} hotels...", end="")
        
        if current_height == last_height:
            no_new_hotels_count += 1
            if no_new_hotels_count >= 2:  # Reduced attempts before breaking
                print("\nNo more hotels to load.")
                break
        else:
            no_new_hotels_count = 0
            
        last_height = current_height

def collect_hotel_data(hotel, timeout=5000):
    """Collect data from a single hotel card with timeout."""
    try:
        # Set a timeout for each data collection attempt
        name = hotel.locator('div[data-testid="title"]').inner_text(timeout=timeout)
        price = hotel.locator('span[data-testid="price-and-discounted-price"]').inner_text(timeout=timeout)
        
        # Get hotel link
        try:
            link_element = hotel.locator('a[data-testid="title-link"]')
            link = link_element.get_attribute('href', timeout=timeout)
            if link and not link.startswith('http'):
                link = f"https://www.booking.com{link}"
        except:
            link = "No link available"
        
        # Get address
        try:
            address = hotel.locator('span[data-testid="address"]').inner_text(timeout=timeout)
        except:
            address = "No address available"
        
        # Get rating
        try:
            rating_text = hotel.locator('div[data-testid="review-score"]').inner_text(timeout=timeout)
            rating = clean_rating(rating_text)
        except:
            rating = "No rating"
        
        return {
            "name": name, 
            "price": price,
            "rating": rating,
            "address": address,
            "link": link
        }
    except TimeoutError:
        print(f"\nTimeout while collecting hotel data, skipping...")
        return None
    except Exception as e:
        print(f"\nError scraping hotel: {e}")
        return None

def save_to_database(session_data, hotels_data):
    """Save the search session and hotel data to the database."""
    conn = sqlite3.connect('hotels.db')
    cursor = conn.cursor()
    
    try:
        # Insert search session
        cursor.execute('''
        INSERT INTO search_sessions (location, check_in_date, check_out_date, guests)
        VALUES (?, ?, ?, ?)
        ''', (session_data['location'], session_data['check_in'], 
              session_data['check_out'], session_data['guests']))
        
        session_id = cursor.lastrowid
        
        # Insert hotel data
        for hotel in hotels_data:
            cursor.execute('''
            INSERT INTO hotels (session_id, name, price, rating, address, link)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, hotel['name'], hotel['price'], 
                  hotel['rating'], hotel['address'], hotel['link']))
        
        conn.commit()
        print(f"\nSuccessfully saved {len(hotels_data)} hotels to database")
        print(f"Session ID: {session_id}")
        
    except Exception as e:
        print(f"Error saving to database: {e}")
        conn.rollback()
    finally:
        conn.close()

def run(playwright: Playwright) -> None:
    # Create database and tables
    create_database()
    
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    print("\nNavigating to Booking.com...")
    try:
        page.goto("https://www.booking.com", wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception as e:
        print(f"Error loading page: {e}")
        context.close()
        browser.close()
        return
    
    try:
        cookie_button = page.locator('button:has-text("Accept")').first
        if cookie_button.is_visible():
            cookie_button.click()
    except:
        pass

    print("\nWaiting for you to enter search details in Booking.com...")
    print("Please enter your search details and click the search button.")
    
    try:
        # Wait for search results
        page.wait_for_selector('div[data-testid="property-card"]', timeout=30000)
        print("Search results found!")
        
        # Extract search parameters from the page
        location, check_in, check_out, guests = get_search_parameters(page)
        if not all([location, check_in, check_out, guests]):
            print("Could not extract all search parameters. Please try again.")
            context.close()
            browser.close()
            return
            
        print("\nStarting to load all hotels...")
        load_all_hotels(page)
        
        # Collect hotel data
        hotel_elements = page.locator('div[data-testid="property-card"]')
        count = hotel_elements.count()
        print(f"\nFound {count} hotel cards, collecting data...")

        # Collect data from all hotels
        hotels_data = []
        failed_attempts = 0
        max_failed_attempts = 5

        for i, hotel in enumerate(hotel_elements.all(), 1):
            data = collect_hotel_data(hotel)
            if data:
                hotels_data.append(data)
                print(f"\rCollected data for {i}/{count} hotels...", end="")
                failed_attempts = 0  # Reset failed attempts on success
            else:
                failed_attempts += 1
                if failed_attempts >= max_failed_attempts:
                    print(f"\nToo many failed attempts ({max_failed_attempts}), stopping collection.")
                    break
                time.sleep(1)  # Wait a bit before trying next hotel
        
        print(f"\nSuccessfully collected data for {len(hotels_data)} hotels")

        # Save to database
        if hotels_data:
            session_data = {
                'location': location,
                'check_in': check_in,
                'check_out': check_out,
                'guests': guests
            }
            save_to_database(session_data, hotels_data)
        else:
            print("No hotel data collected to save")
            
    except Exception as e:
        print(f"Error: {e}")

    context.close()
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)

