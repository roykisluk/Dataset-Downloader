import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging
import os
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
import torch
from PIL import Image
from selenium.webdriver.chrome.options import Options

####################################################################################################
### SETUP ###
####################################################################################################

####################################################################################################
### CRITICAL ###
####################################################################################################

# Install the required packages
# pip install requests selenium transformers torch pillow

# Initialize WebDriver: download the appropriate ChromeDriver for your OS from: https://googlechromelabs.github.io/chrome-for-testing/#stable
driver_path = '/Users/roykisluk/Downloads/Archive/chromedriver-mac-arm64/chromedriver'  # Replace with your ChromeDriver path

####################################################################################################
### OPTIONAL ###
####################################################################################################

# Define the download folder path
download_folder = os.path.abspath("/Volumes/SSD")

# Target URL, first page
link = "https://www.data.gov.in/catalog/6th-minor-irrigation-census-village-schedule-ground-water-schemes-surface-water-schemes"

# Structure info
n_datasets=203 # number of datasets
datasets_per_page=8 # number of datasets per page

# Define model for OCR
processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")

####################################################################################################

# Configure logging
logging.basicConfig(filename='download_log.txt', level=logging.INFO, format='%(asctime)s - %(message)s')

# Set Chrome options
chrome_options = Options()
prefs = {
    "download.default_directory": download_folder,  # Set default download directory
    "download.prompt_for_download": False,          # Disable the download prompt
    "safebrowsing.enabled": True                    # Enable safe browsing
}
chrome_options.add_experimental_option("prefs", prefs)

# Create a Service object for the driver
service = Service(driver_path)

# Initialize WebDriver
driver = webdriver.Chrome(service=service, options=chrome_options)

# Function to solve CAPTCHA using anuashok/ocr-captcha-v3
def solve_captcha(image_element):
    # Load model and processor
    image_path = "captcha.png"
    image_element.screenshot(image_path)
    # Load image
    image = Image.open(image_path).convert("RGB")
    # Load and preprocess image for display
    image = Image.open(image_path).convert("RGBA")
    # Create white background
    background = Image.new("RGBA", image.size, (255, 255, 255))
    combined = Image.alpha_composite(background, image).convert("RGB")

    # Prepare image
    pixel_values = processor(combined, return_tensors="pt").pixel_values

    # Generate text
    generated_ids = model.generate(pixel_values)
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    # print(generated_text)
    return generated_text.upper()


# Read the log file to get the status of each dataset
downloaded_datasets = set()
if os.path.exists('downloaded_datasets.csv'):
    with open('downloaded_datasets.csv', 'r') as file:
        content = file.read().strip()
        if content:  # Only try to parse if file is not empty
            downloaded_datasets = set(int(x) for x in content.split(',') if x)  # Only convert non-empty strings

dataset_number = 1  # Initialize dataset number

try:
    # Navigate to the webpage
    driver.get(link)  

    for page in range(1, n_datasets//datasets_per_page+1):
        for i in range(1, datasets_per_page+1):
            if dataset_number in downloaded_datasets:
                dataset_number += 1
                continue
            
            print("Attempt - dataset index:", dataset_number," page: ", page, " dataset: ", i)
            # Gather information about the dataset
            dataset_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f'/html/body/div[1]/div/div/main/section[2]/div/div/div[2]/div/div[3]/div[1]/div/div[{i}]/div/div[1]/h3/a'))
            )
            dataset_info = dataset_element.text
            dataset_link = dataset_element.get_attribute('href')
            
            # Log dataset details to CSV
            with open('dataset_details.csv', 'a') as file:
                file.write(f"{dataset_number},{page},{i},{dataset_info},{dataset_link}\n")

            # Click on the download button
            download_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f'/html/body/div[1]/div/div/main/section[2]/div/div/div[2]/div/div[3]/div[1]/div/div[{i}]/div/div[2]/div[1]/div[1]/div[1]/div[1]/a'))
            )
            download_button.click()

            # Select "non-commercial"
            non_commercial_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[3]/div[1]/div/div/div/form/div/div/div[1]/fieldset/div/div/div[2]/label"))
            )
            non_commercial_option.click()

            # Select "academic purpose"
            academia_purpose_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[3]/div[1]/div/div/div/form/div/div/div[2]/fieldset/div/div/div[1]/label"))
            )
            academia_purpose_option.click()

            time.sleep(5)

            final_download_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[3]/div[1]/div/div/div/form/div/div/div[6]/button"))
            )

            captcha_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[3]/div[1]/div/div/div/form/div/div/div[4]/div/div/div/img"))
            )
            try:
                captcha_solution = solve_captcha(captcha_element).upper()
                if not captcha_solution:
                    raise ValueError("Empty CAPTCHA solution")
            except Exception as e:
                logging.error(f"CAPTCHA solution failed: {e}")
                continue

            # Fill in the CAPTCHA solution
            captcha_input = driver.find_element(By.XPATH, "/html/body/div[3]/div[1]/div/div/div/form/div/div/div[4]/div/div/input")
            # captcha_input.clear()
            captcha_input.send_keys(captcha_solution)

            # Press download
            final_download_button.click()

            # Wait for the download to complete     
            time.sleep(5)           

            # Log the successful download
            logging.info(f"Successfully downloaded dataset {dataset_number}")
            with open('downloaded_datasets.csv', 'a') as file:
                file.write(f"{dataset_number},")
            dataset_number += 1

            # Switch back to the original tab
            driver.switch_to.window(driver.window_handles[0])

            # Repeat the process for the next dataset
            print("Success - dataset index:", dataset_number," page: ", page, " dataset: ", i)
            print("Proceeding to the next dataset...\n")

        # Next page
        next_page = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/main/section[2]/div/div/div[2]/div/div[4]/ul/li[8]/button"))
        )
        next_page.click()
        time.sleep(3)

    print("Finished downloading all datasets.")


except Exception as e:
    print(f"An error occurred: {e}")
    # Wait for user input before closing browser
    input("Check if downloads have finished, then enter any key to close the browser...")
finally:
    try:
        driver.quit()
    except Exception as e:
        logging.error(f"Error closing driver: {e}")
