import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import concurrent.futures
import logging
from datetime import datetime
import threading
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

def load_env():
    env_vars = {}
    with open('.env', 'r') as file:
        for line in file:
            # Skip lines that are comments or empty
            if line.startswith('#') or not line.strip():
                continue
            # Split the line into key and value
            key, value = line.strip().split('=', 1)
            env_vars[key] = value
    return env_vars

def main():
    env_vars = load_env()
    input_file = env_vars.get('INPUT_FILE')
    proxy_address = env_vars.get('PROXY_ADDRESS')
    max_worker_count = env_vars.get('MAX_WORKERS')
    chrome_driver_path = env_vars.get('CHROME_DRIVER_PATH')

    if not input_file or not proxy_address:
        logger.error("Environment variables INPUT_FILE and PROXY_ADDRESS must be set.")
        return

    df = pd.read_excel(input_file)

    # Get already processed tracking numbers
    processed_numbers = set()
    for file in os.listdir('.'):
        if file.startswith('tracking_results') and file.endswith('.xlsx'):
            logger.info(f"Filename: {file.split('.')[0]}")
            processed_df = pd.read_excel(file)
            existed_list = processed_df['tracking'].tolist()
            logger.info(f"Number of already processed tracking numbers: {len(existed_list)}")
            logger.info(f"Existing before adding: {len(processed_numbers)}")
            processed_numbers.update(existed_list)
            logger.info(f"Existing after adding: {len(processed_numbers)}")

    # Store unprocessed ref_number data into list_
    list_ = [num for num in df['ref_number'].tolist() if num not in processed_numbers]
    total_count = len(list_)  # Total count
    logger.info(f"Total number to be processed: {total_count}")

    # Set ChromeOptions
    chrome_options = Options()
    if proxy_address:
        chrome_options.add_argument(f'--proxy-server={proxy_address}')
    chrome_options.add_argument('--disable-gpu')  # Disable GPU acceleration
    chrome_options.add_argument('--no-sandbox')  # Resolve DevToolsActivePort file not found error
    chrome_options.add_argument('--disable-dev-shm-usage')  # Shared memory shortage issue

    # Create a lock
    lock = threading.Lock()

    # Find the next tracking_resultsN.xlsx filename
    file_index = 1
    while os.path.exists(f'tracking_results{file_index}.xlsx'):
        file_index += 1
    output_file = f'tracking_results{file_index}.xlsx'

    # Define a function to process each tracking number
    def fetch_tracking_info(num):
        driver = None
        retries = 3  # Set number of retries
        for attempt in range(retries):
            try:
                logger.info(f"Processing tracking number: {num}, Attempt: {attempt + 1}")
                driver = webdriver.Chrome(service=Service(chrome_driver_path), options=chrome_options)
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                      get: () => undefined
                    })
                  """
                })

                driver.get(f"https://www.fedex.com.cn/fedextrack/?trknbr={num}")
                WebDriverWait(driver, 15).until(
                    lambda d: 'duplicate-results' in d.current_url or 'trkqual' in d.current_url
                )
                # Check if current URL contains duplicate-results
                current_url = driver.current_url
                if 'duplicate-results' in current_url:
                    logger.info(f"Tracking number {num} is duplicated, setting status to: Duplicated Tracking")
                    with lock:
                        if os.path.exists(output_file):
                            existing_df = pd.read_excel(output_file)
                            new_df = pd.DataFrame([[num, 'Duplicated Tracking']], columns=['tracking', 'label_value'], dtype=str)
                            result_df = pd.concat([existing_df, new_df], ignore_index=True)
                        else:
                            result_df = pd.DataFrame([[num, 'Duplicated Tracking']], columns=['tracking', 'label_value'], dtype=str)
                        result_df.to_excel(output_file, index=False)
                    return num, 'Duplicated Tracking'

                # Wait for shipment-status-progress-step-label to appear and have a value
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, 'shipment-status-progress-step-label-info'))
                    )
                    time.sleep(2)  # Ensure the page is fully loaded
                    x = driver.page_source
                    html = BeautifulSoup(x, "html.parser")
                    active_step = html.find('div', class_='shipment-status-progress-step active')

                    label_value = None
                    if active_step:
                        label_span = active_step.find('span', class_='shipment-status-progress-step-label-info')
                        if label_span and label_span.get_text(strip=True):
                            label_value = label_span.get_text(strip=True)
                        else:
                            label_span = active_step.find('span', class_='shipment-status-progress-step-label')
                            if label_span and label_span.get_text(strip=True):
                                label_value = label_span.get_text(strip=True)
                    if label_value:
                        logger.info(f"Finished processing tracking number: {num}, Status: {label_value}")
                        # Use lock to ensure thread-safe write to Excel file
                        with lock:
                            if os.path.exists(output_file):
                                existing_df = pd.read_excel(output_file)
                                new_df = pd.DataFrame([[num, label_value]], columns=['tracking', 'label_value'], dtype=str)
                                result_df = pd.concat([existing_df, new_df], ignore_index=True)
                            else:
                                result_df = pd.DataFrame([[num, label_value]], columns=['tracking', 'label_value'], dtype=str)
                            result_df.to_excel(output_file, index=False)
                        return num, label_value
                    else:
                        raise Exception("Status label has no value")
                except Exception as e:
                    logger.warning(f"Tracking number {num} status label not found or has no value")
                    if attempt < retries - 1:
                        logger.info(f"Retrying tracking number: {num}, Attempt: {attempt + 2}")
                    else:
                        logger.error(f"Tracking number {num} processing failed, maximum retries reached")
                    continue  # Continue retrying
            except Exception as e:
                logger.error(f"Error processing tracking number {num}: {e}")
            finally:
                if driver:
                    driver.quit()

        # Record failed result after reaching maximum retries
        with lock:
            if os.path.exists(output_file):
                existing_df = pd.read_excel(output_file)
                new_df = pd.DataFrame([[num, 'Unknown']], columns=['tracking', 'label_value'], dtype=str)
                result_df = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                result_df = pd.DataFrame([[num, 'Unknown']], columns=['tracking', 'label_value'], dtype=str)
            result_df.to_excel(output_file, index=False)
        return num, None

    # Record start time
    start_time = datetime.now()

    # Use ThreadPoolExecutor to process in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_worker_count) as executor:  # Adjust max_workers based on system performance
        future_to_num = {executor.submit(fetch_tracking_info, num): num for num in list_}
        for future in concurrent.futures.as_completed(future_to_num):
            tracking_num, label_value = future.result()

    # Record end time
    end_time = datetime.now()
    # Calculate duration
    duration = end_time - start_time

    # Output duration
    hours, remainder = divmod(duration.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    logger.info(f"Program duration: {int(hours)}h {int(minutes)}m {int(seconds)}s")

    logger.info("All tracking numbers processed")

if __name__ == "__main__":
    main()