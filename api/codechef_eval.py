import time
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException

logger = logging.getLogger(__name__)

def parse_time_to_millis(time_str):
    if not time_str: return None
    try:
        if 'sec' in time_str: return int(float(time_str.split()[0]) * 1000)
    except: pass
    return None

def parse_memory_to_bytes(memory_str):
    if not memory_str: return None
    try:
        value, unit = memory_str.split()
        value = float(value)
        if unit.upper() == 'MB': return int(value * 1024 * 1024)
        elif unit.upper() == 'KB': return int(value * 1024)
    except: pass
    return None

def setup_webdriver():
    """Initialize and configure Chrome WebDriver with headless options"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    logger.info("Setting up new WebDriver instance...")
    try:
        wd = webdriver.Chrome(options=chrome_options)
        wd.implicitly_wait(5) 
        logger.info("WebDriver instance created.")
        return wd
    except WebDriverException as e:
        logger.error(f"Failed to setup WebDriver (driver likely not found in PATH): {e}", exc_info=True)
        raise ConnectionError(f"Could not start WebDriver (check chromedriver in PATH): {e}")
    except Exception as e:
         logger.error(f"Unexpected error during WebDriver setup: {e}", exc_info=True)
         raise ConnectionError(f"Unexpected error starting WebDriver: {e}")


def get_table_data(username):
    """Extract table data including headers and rows with links for a given username"""
    wd = None 
    try:
        wd = setup_webdriver() 
        profile_url = f"https://www.codechef.com/users/{username}"
        logger.info(f"Getting table data from: {profile_url}")
        wd.get(profile_url)
        table = wd.find_element(By.TAG_NAME, "table")

        headers = [header.text for header in table.find_elements(By.TAG_NAME, "th")]
        headers.append("Solution Link")

        data = []
        rows = table.find_elements(By.TAG_NAME, "tr")[1:] 

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if not cols: continue
            row_data = [col.text for col in cols[:-1]]
            last_td = cols[-1]
            link = None
            try:
                link = last_td.find_element(By.TAG_NAME, "a").get_attribute("href")
            except NoSuchElementException:
                link = None

            row_data.append(link)
            data.append(row_data)

        logger.info(f"Extracted {len(data)} rows from table for {username}.")
        return headers, data
    except NoSuchElementException:
        logger.error(f"Could not find the submission table element ('table' tag) for {username}.")
        return None, None
    except ConnectionError:
         logger.error(f"Failed to setup WebDriver within get_table_data for {username}.")
         return None, None
    except Exception as e:
        logger.error(f"Unexpected error in get_table_data for {username}: {e}", exc_info=True)
        return None, None
    finally:
        if wd:
            logger.info("Quitting WebDriver instance from get_table_data.")
            wd.quit()


def _scrape_solution_details_page(solution_link: str):
    """
    Scrapes details from the individual solution page: Code, Passed Tests, Time, Memory.
    Uses its own WebDriver instance via setup_webdriver().
    """
    if not solution_link:
        logger.warning("Scraper received no solution link for details page.")
        return {}

    wd = None 
    logger.info(f"Attempting to scrape solution detail page: {solution_link}")
    try:
        wd = setup_webdriver() 
        wd.get(solution_link)
        logger.info("Navigated to solution detail page.")

        details = {}

        try:
            code_element = wd.find_element(By.CLASS_NAME, "ace_content")
            details["code"] = code_element.text
            logger.info("Scraper got code from solution page.")
        except NoSuchElementException:
            logger.error("Scraper could not find code element using class 'ace_content'.")
            details["code"] = None
        except Exception as e:
            logger.error(f"Scraper unexpected error scraping code: {e}", exc_info=True)
            details["code"] = None

        passed_count = 0
        try:
            table = wd.find_element(By.TAG_NAME, "table") 
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if not cols: continue
                try:
                    test_verdict = cols[2].text.strip() 
                    if "AC" in test_verdict.upper() or "CORRECT" in test_verdict.upper():
                        passed_count += 1
                except IndexError: pass
            details["passed_tests"] = passed_count
            logger.info(f"Scraper processed test cases: Passed={passed_count}")
        except NoSuchElementException:
            logger.warning("Scraper did not find a results table ('table' tag) on solution page.")
            details["passed_tests"] = None
        except Exception as e:
            logger.error(f"Scraper unexpected error scraping results table: {e}", exc_info=True)
            details["passed_tests"] = None

        try:
            memory_time_element = wd.find_element(By.CLASS_NAME, "_scoreTimeMem__container_1xnpw_344") # Fragile selector
            memory_time_text = memory_time_element.text
            time_str, memory_str = None, None
            parts = memory_time_text.split()
            for i, part in enumerate(parts):
                if "Time:" in part and i + 1 < len(parts): time_str = parts[i+1] + (parts[i+2] if "sec" in parts[i+2] else "")
                if "Memory:" in part and i + 1 < len(parts): memory_str = parts[i+1] + (parts[i+2] if "MB" in parts[i+2] or "KB" in parts[i+2] else "")
            details["time_millis"] = parse_time_to_millis(time_str)
            details["memory_bytes"] = parse_memory_to_bytes(memory_str)
            logger.info(f"Scraper parsed Time/Memory: Time={time_str}, Memory={memory_str}")
        except NoSuchElementException:
            logger.warning("Scraper could not find time/memory element using class '_scoreTimeMem__container_1xnpw_344'.")
            details["time_millis"] = None
            details["memory_bytes"] = None
        except Exception as e:
            logger.error(f"Scraper unexpected error scraping/parsing time/memory: {e}", exc_info=True)
            details["time_millis"] = None
            details["memory_bytes"] = None

        return details

    except ConnectionError: 
         logger.error(f"Failed to setup WebDriver within _scrape_solution_details_page.")
         return {} 
    except Exception as e:
        logger.error(f"Unexpected error scraping solution page {solution_link}: {e}", exc_info=True)
        return {}
    finally:
        if wd:
            logger.info("Quitting WebDriver instance from _scrape_solution_details_page.")
            wd.quit()


def scrape_codechef_submission(codechef_handle: str, problem_code: str) -> dict:
    """
    Orchestrates the scraping process using user's provided functions structure.
    WARNING: Creates multiple WebDriver instances - inefficient.

    Args:
        codechef_handle: The user's CodeChef handle.
        problem_code: The CodeChef problem code.

    Returns:
        A dictionary containing scraped data, or empty dict if submission not found.

    Raises:
        ConnectionError: If WebDriver fails critically during setup.
    """
    logger.warning("Executing scrape_codechef_submission using multi-driver approach (inefficient).")
    try:
        headers, table_data = get_table_data(codechef_handle)

        if headers is None or table_data is None:
            logger.warning(f"Could not extract submission table data for user {codechef_handle}.")
            return {} 

        PROBLEM_CODE_COLUMN_INDEX = 1 
        latest_matching_row = None
        
        latest_matching_row = table_data[0]

        if not latest_matching_row:
            logger.warning(f"No submission found for problem {problem_code} in the table for user {codechef_handle}.")
            return {} 
        try:
            submission_id = latest_matching_row[-1].split("/")[-1] if len(latest_matching_row) > 0 else None
            verdict = latest_matching_row[2].strip() if len(latest_matching_row) > 3 else None
            language = latest_matching_row[3].strip() if len(latest_matching_row) > 4 else None
            solution_link = latest_matching_row[-1]

            if verdict=="(100)":
                verdict="OK"
        except IndexError:
            logger.error("IndexError accessing data in the found submission row. Table structure might have changed.")
            return {}

        logger.info(f"Found matching submission in table: ID={submission_id}, Verdict={verdict}, Lang={language}, Link={solution_link}")

        details = {}
        if solution_link:
            details = _scrape_solution_details_page(solution_link)
        else:
            logger.warning("No solution link found in table row, cannot scrape details (code, tests, etc.).")

        result_data = {
            'codeforces_submission_id': int(submission_id) if submission_id else None,
            'verdict': verdict,
            'language': language,
            'submitted_code': details.get("code"),
            'passed_test_count': details.get("passed_tests"),
            'time_consumed_millis': details.get("time_millis"),
            'memory_consumed_bytes': 10
        }
        logger.info("Scraping process completed.")
        return result_data

    except ConnectionError as e: 
        logger.error(f"Scraping failed due to WebDriver setup error: {e}")
        raise 
    except Exception as e: 
         logger.error(f"Unexpected error during scraping orchestration: {e}", exc_info=True)
         raise ConnectionError(f"Unexpected scraping error: {e}")