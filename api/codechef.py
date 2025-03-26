import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

def setup_webdriver():
    """Initialize and configure Chrome WebDriver with headless options"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def get_rating(username):
    """Extract rating number for a given username"""
    wd = setup_webdriver()
    try:
        wd.get(f"https://www.codechef.com/users/{username}")
        rating = wd.find_element("class name", "rating-number")
        return rating.text
    except NoSuchElementException:
        return None
    finally:
        wd.quit()

def get_ranking(username):
    """Extract global and country rankings for a given username"""
    wd = setup_webdriver()
    try:
        wd.get(f"https://www.codechef.com/users/{username}")
        ranks = wd.find_element("class name", "inline-list")
        temp = ranks.text.split()
        return {"Global Rank": temp[0], "Country Rank": temp[3]}
    except (NoSuchElementException, IndexError):
        return None
    finally:
        wd.quit()

def get_table_data(username):
    """Extract table data including headers and rows with links for a given username"""
    wd = setup_webdriver()
    try:
        wd.get(f"https://www.codechef.com/users/{username}")
        # Find the table
        table = wd.find_element("tag name", "table")
        
        # Extract headers
        headers = [header.text for header in table.find_elements("tag name", "th")]
        headers.append("Solution Link")
        
        # Extract rows
        data = []
        rows = table.find_elements("tag name", "tr")[1:]  # Skip header row
        
        for row in rows:
            cols = row.find_elements("tag name", "td")
            row_data = [col.text for col in cols[:-1]]
            last_td = cols[-1]
            
            try:
                link = last_td.find_element("tag name", "a").get_attribute("href")
            except NoSuchElementException:
                link = None
                
            row_data.append(link)
            data.append(row_data)
            
        return headers, data
    except NoSuchElementException:
        return None, None
    finally:
        wd.quit()

def get_name_display(username):
    """Extract displayed username from the page"""
    wd = setup_webdriver()
    try:
        wd.get(f"https://www.codechef.com/users/{username}")
        name = wd.find_element("class name", "h2-style")
        return name.text
    except NoSuchElementException:
        return None
    finally:
        wd.quit()
