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

# 2Captcha API key
'''
# Set API key from environment variable
api_key = os.getenv("TWOCAPTCHA_API_KEY")
if not api_key:
    raise ValueError("2Captcha API key not found in environment variables. Please set 'TWOCAPTCHA_API_KEY'.")
# First time: set the 2Captcha API key in the system environment variables:  
# os.environ["TWOCAPTCHA_API_KEY"] = ""
'''

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

# Create a Service object for the driver
service = Service(driver_path)

# Initialize WebDriver
driver = webdriver.Chrome(service=service)

# Function to solve CAPTCHA using 2Captcha
def solve_captcha_twocaptcha(image_element):
    """Solve CAPTCHA using 2Captcha service."""
    # Save the CAPTCHA image locally
    captcha_image_path = "captcha.png"
    image_element.screenshot(captcha_image_path)
    
    # Send the CAPTCHA image to 2Captcha for solving
    with open(captcha_image_path, 'rb') as file:
        response = requests.post(
            "https://2captcha.com/in.php",
            data={"key": api_key, "method": "post", "json": 1},
            files={"file": file}
        )
    
    request_id = response.json().get("request")
    if not request_id:
        raise ValueError("Failed to get request ID from 2Captcha")
    
    
    # Poll for the CAPTCHA solution
    for _ in range(10):  # Retry up to 10 times
        time.sleep(5)  # Wait for 5 seconds before retrying
        result_response = requests.get(
            "https://2captcha.com/res.php",
            params={"key": api_key, "action": "get", "id": request_id, "json": 1}
        )
        result_data = result_response.json()
        if result_data.get("status") == 1:
            return result_data.get("request").upper()  # Return the solution in uppercase
        elif result_data.get("request") != "CAPCHA_NOT_READY":
            raise ValueError(f"2Captcha solution error: {result_data.get('request')}")
    
    raise TimeoutError("2Captcha timed out while solving the CAPTCHA.")

# Function to solve CAPTCHA using anuashok/ocr-captcha-v3
def solve_captcha(image_element):
    # Load model and processor
    image_path = "captcha.jpg"
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
if os.path.exists('downloaded_datasets.txt'):
    with open('downloaded_datasets.txt', 'r') as file:
        downloaded_datasets = set(map(int, file.read().splitlines()))

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

            '''
            # Non-robust captcha
            '''
            captcha_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[3]/div[1]/div/div/div/form/div/div/div[4]/div/div/div/img"))
            )
            captcha_solution = solve_captcha(captcha_element).upper()

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
            with open('downloaded_datasets.txt', 'a') as file:
                file.write(f"{dataset_number}\n")
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
finally:
    driver.quit()
