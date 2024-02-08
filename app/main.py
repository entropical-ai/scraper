from fastapi import FastAPI, Query
from selenium import webdriver
import html2text
from pyvirtualdisplay import Display
from typing import Annotated, Optional
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI()
openai_client = OpenAI()

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--window-size=1920,1080')
chrome_options.add_argument('--headless=new')
chrome_options.add_argument('--disable-gpu')
chrome_options.add_argument('--disable-dev-shm-usage')

class Body(BaseModel):
    body: str

@app.get("/scrape_urls")
def scrape_urls(urls: Annotated[list[str], Query()], ignore_links = 1, ignore_images = 1):
    ignore_links = False if int(ignore_links) == 0 else True
    ignore_images = False if int(ignore_images) == 0 else True

    # HTML2TEXT
    h = html2text.HTML2Text()
    h.ignore_links = ignore_links
    h.ignore_images = ignore_images
    
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = webdriver.Chrome(options=chrome_options)

    result = {}
    for url in urls:
        print("Fetching:", url)
        driver.get(url)
        result[url] = h.handle(driver.page_source)

    # Kill driver
    driver.close()
    display.stop()

    return result

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

