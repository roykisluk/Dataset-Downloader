# Dataset-Downloader

Automates datasets downloads and CAPTCHA handling using https://huggingface.co/anuashok/ocr-captcha-v3

CSV format:
{absolute_dataset_number},{page_number},{dataset_index_in_page},{dataset_title},{dataset_link}

## Setup

- Download the appropriate ChromeDriver for your OS from: https://googlechromelabs.github.io/chrome-for-testing/#stable
- pip install requests selenium transformers torch pillow