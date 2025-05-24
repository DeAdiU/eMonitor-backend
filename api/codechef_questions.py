# /your_django_app/codechef_scraper.py

import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

# --- Constants for Selectors (makes updates easier) ---
# !! These are based on your Colab notebook and CodeChef's structure at the time !!
# !! They are likely to break if CodeChef changes its website !!
PROBLEM_TITLE_SELECTOR = 'h3' # Assuming title is in the main H1 tag - VERIFY THIS!
DIFFICULTY_SELECTOR = '._value_rapdk_395'
TAG_REVEAL_BUTTON_SELECTOR = '._icon__container_rapdk_362'
TAG_CONTAINER_SELECTOR = '._tags__container_rapdk_488' # Parent container for tags might be more stable
TAG_ITEM_SELECTOR = '._tagList__item_rapdk_539' # Individual tag items
# --- End Selectors ---

def fetch_problem_metadata_cc(problem_index):
    """
    Fetches CodeChef problem metadata (title, tags, difficulty) using Selenium.

    Args:
        problem_index (str): The CodeChef problem code (e.g., "START01", "MAKEPERM").

    Returns:
        dict: A dictionary with 'title', 'tags' (list), 'rating' (int),
              or None if fetching fails or the problem is not found.
    """
    problem_code = problem_index.upper()
    problem_url = f"https://www.codechef.com/problems/{problem_code}"
    logger.info(f"Attempting to fetch CodeChef metadata for {problem_code} from {problem_url}")

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    

    wd = None # Initialize wd to None
    try:
        
        wd = webdriver.Chrome(options=chrome_options)
        wd.get(problem_url)

        WebDriverWait(wd, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        fetched_data = {'title': None, 'tags': [], 'rating': None}

        try:
            title_element = WebDriverWait(wd, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, PROBLEM_TITLE_SELECTOR))
            )
            full_title = title_element.text
            if f"{problem_code} -" in full_title:
                 fetched_data['title'] = full_title.split('-', 1)[1].strip()
            else:
                 fetched_data['title'] = full_title.strip()
            logger.debug(f"Found title: {fetched_data['title']}")
        except (NoSuchElementException, TimeoutException):
            logger.warning(f"Could not find title element '{PROBLEM_TITLE_SELECTOR}' for {problem_code}")
            return None 

        try:
            difficulty_element = wd.find_element(By.CSS_SELECTOR, DIFFICULTY_SELECTOR)
            difficulty_text = difficulty_element.text
            fetched_data['rating'] = int(difficulty_text)
            logger.debug(f"Found rating: {fetched_data['rating']}")
        except NoSuchElementException:
            logger.warning(f"Could not find difficulty element '{DIFFICULTY_SELECTOR}' for {problem_code}")
        except ValueError:
            logger.warning(f"Could not convert difficulty text '{difficulty_text}' to int for {problem_code}")
        try:
            tag_button = WebDriverWait(wd, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, TAG_REVEAL_BUTTON_SELECTOR))
            )
            tag_button.click()
            logger.debug("Clicked tag reveal button")

            tag_container = WebDriverWait(wd, 2).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, TAG_CONTAINER_SELECTOR))
            )
            logger.debug("Tag container visible")
            tag_elements = tag_container.find_elements(By.CSS_SELECTOR, TAG_ITEM_SELECTOR)
            fetched_data['tags'] = [tag.text for tag in tag_elements if tag.text]
            logger.debug(f"Found tags: {fetched_data['tags']}")

        except (NoSuchElementException, TimeoutException):
            logger.warning(f"Could not find or interact with tag elements for {problem_code}. Tags might be absent or selectors changed.")

        logger.info(f"Successfully fetched metadata for {problem_code}: {fetched_data}")
        return fetched_data

    except WebDriverException as e:
        logger.error(f"Selenium WebDriver error for {problem_code}: {e}", exc_info=True)
        return None 
    except Exception as e:
        logger.error(f"Unexpected error fetching metadata for {problem_code}: {e}", exc_info=True)
        return None 
    finally:
        if wd:
            try:
                wd.quit()
                logger.debug(f"Closed WebDriver for {problem_code}")
            except Exception as e:
                logger.error(f"Error closing WebDriver for {problem_code}: {e}")


