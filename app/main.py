from fastapi import FastAPI, Query
from typing import Annotated
from selenium import webdriver
import html2text
from pyvirtualdisplay import Display
from typing import Annotated

app = FastAPI()

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--window-size=1920,1080')
#chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-dev-shm-usage')

# HTML2TEXT
h = html2text.HTML2Text()
h.ignore_links = True
h.ignore_images = True

@app.get("/scrape_urls")
def scrape_urls(urls: Annotated[list[str], Query()], ignore_links = True, ignore_images = True):
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = webdriver.Chrome(options=chrome_options)

    result = {}
    for url in urls:
        print("Fetching:", url)
        driver.get(url)
        result[url] = h.handle(driver.page_source)

    # Kill driver
    driver.quit()
    display.stop()

    return result