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

# Install the required packages:
# pip install requests selenium transformers torch pillow

# Initialize WebDriver: download the appropriate ChromeDriver for your OS from: https://googlechromelabs.github.io/chrome-for-testing/#stable
driver_path = r'/Users/roykisluk/Downloads/Archive/chromedriver-mac-arm64/chromedriver'  # Replace with your ChromeDriver path

# Define the download folder path
download_folder = os.path.abspath(r"/Users/roykisluk/Downloads/Datasets/")

# Target URL of the gov.in catalog
link = "https://www.data.gov.in/catalog/6th-minor-irrigation-census-village-schedule-ground-water-schemes-surface-water-schemes"

# Structure info
n_datasets=203 # number of datasets
datasets_per_page=8 # maximum number of datasets per page

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

# Check for incomplete downloads and empty folders, remove them from downloaded_datasets
for dataset_num in range(1, n_datasets):  # Check folders 1 to n_datasets
    dataset_folder = os.path.join(download_folder, str(dataset_num))
    if os.path.exists(dataset_folder):
        files = os.listdir(dataset_folder)
        # Remove if folder is empty
        if len(files) == 0 and dataset_num in downloaded_datasets:
            downloaded_datasets.remove(dataset_num)
            logging.info(f"Removed dataset {dataset_num} from downloaded list due to empty folder")
        # Remove if there are incomplete downloads
        for filename in files:
            if filename.endswith('.crdownload'):
                if dataset_num in downloaded_datasets:
                    downloaded_datasets.remove(dataset_num)
                    logging.info(f"Removed dataset {dataset_num} from downloaded list due to incomplete download")
    # Remove if folder doesn't exist
    elif not os.path.exists(dataset_folder) and dataset_num in downloaded_datasets:
        downloaded_datasets.remove(dataset_num)
        logging.info(f"Removed dataset {dataset_num} from downloaded list due to non-existent folder")

# Write updated downloaded_datasets to CSV
with open('downloaded_datasets.csv', 'w') as file:
    file.write(','.join(str(x) for x in sorted(downloaded_datasets)) + ',')


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

            # Set the download path to dataset number subfolder
            driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
            params = {'cmd': 'Page.setDownloadBehavior',
                      'params': {'behavior': 'allow', 'downloadPath': os.path.join(download_folder, str(dataset_number))}}
            driver.execute("send_command", params)

            # Press download
            final_download_button.click()

            # Add dataset details to csv
            with open('dataset_details.csv', 'r') as file:
                if not any(line.startswith(f"{dataset_number},") for line in file):
                    # Update the dataset details CSV with the download URL and other details
                    with open('dataset_details.csv', 'a') as file:
                        # Log the absolute dataset number, page, dataset index in page, dataset title, dataset link
                        file.write(f"{dataset_number},{page},{i},{dataset_info},{dataset_link}\n")

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
