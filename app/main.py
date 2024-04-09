from fastapi import FastAPI, Query
from selenium import webdriver
import html2text
from pyvirtualdisplay import Display
from typing import Annotated, Optional
from openai import OpenAI
from pydantic import BaseModel
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException, TimeoutException
import re
import time
from urllib.parse import urlparse, urljoin

app = FastAPI()
openai_client = OpenAI()

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-dev-shm-usage')

def scrape_url_recursive(driver, starttime, timeout, url, domain, internal_links_content, outgoing_links, visited_links, current_depth=0, max_depth=3):
  
    if current_depth > max_depth:
        return

    driver.get(url)
    html_content = driver.page_source
    soup = BeautifulSoup(html_content, 'html.parser')

    if url not in visited_links:  # Ensure we haven't visited this URL yet
        print(f"Visiting {url}")
        visited_links.add(url)

        # Store the content of the internal URL
        internal_links_content[url] = html_content

        all_a = soup.find_all('a', href=True)

        links = []

        for a in all_a:
            link = a.attrs['href']
            joined_link = urljoin(url, link)

            parsed_url = urlparse(joined_link)
            if parsed_url.netloc == domain:
                internal_links_content[joined_link] = None
                links.append(joined_link)
            elif joined_link not in visited_links:
                outgoing_links.add(joined_link)


        for href in links:
            if timeout == -1 or time.time() < starttime + timeout:
                try:
                    scrape_url_recursive(driver, starttime, timeout, href, domain, internal_links_content, outgoing_links, visited_links, current_depth+1, max_depth)
                except (WebDriverException, TimeoutException) as e:
                    print(f"Fetching {href} resulted in Exception: {str(e)}")
                    

class Body(BaseModel):
    body: str

@app.get("/scrape_urls")
def scrape_urls(urls: Annotated[list[str], Query()], ignore_links = 1, ignore_images = 1, timeout = 30):
    ignore_links = False if int(ignore_links) == 0 else True
    ignore_images = False if int(ignore_images) == 0 else True

    # HTML2TEXT
    h = html2text.HTML2Text()
    h.ignore_links = ignore_links
    h.ignore_images = ignore_images
    
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(timeout)

    result = {}
    for url in urls:
        try:
            print("Fetching:", url)
            driver.get(url)
            result[url] = h.handle(driver.page_source)
        except TimeoutException:
            result[url] = "The contents of this page could not be extracted because it took more than {timeout} seconds to load."


    # Kill driver
    driver.close()
    display.stop()

    return result

@app.get("/crawl")
def crawl(url: str, timeout: int = 60, max_depth: int = 3):
    # HTML2TEXT
    h = html2text.HTML2Text()
    h.ignore_links = 1
    h.ignore_images = 1
    
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(10)

    # Scrape the website
    parsed_start_url = urlparse(url)
    start_domain = parsed_start_url.netloc

    internal_links_content = {}
    outgoing_links = set()
    visited_links = set()

    scrape_url_recursive(driver, time.time(), timeout, url, start_domain, internal_links_content, outgoing_links, visited_links, max_depth=max_depth)

    # Restart driver
    driver.close()
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(5)

    # Get remaining empty contents + convert to markdown
    for url, content in internal_links_content.items():
        try:
            if content is None:
                print(f"Separately fetching: {url}")
                driver.get(url)
                internal_links_content[url] = driver.page_source
        except (WebDriverException, TimeoutException) as e:
            print("Exception when fetching", url)


    # Stop driver
    driver.close()
    display.stop()

    return internal_links_content



@app.post("/extract_article")
def extract_article(body: Body):
    print(body)
    prompt = f"""I have the contents of a webpage (converted with html2text package to Markdown). This webpage contains a blog post. You need to isolate the blog post and return as a fully marked-up article, with ATX style headings.
Note that the markup in the original article below may be illogical. Apply ATX style heading markup where you this it makes sense, if the article doesn't provide any.

Exclude metadata such as date, author, related articles, et cetera. Start with the title, end with the last paragraph of the blog post.

Start with the article title as H1-level heading: # Title

Web page contents:

{body}"""

    response = openai_client.chat.completions.create(
        model='gpt-3.5-turbo-16k',
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': prompt}
        ]
    )

    return response.choices[0].message.content

