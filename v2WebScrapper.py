import random
import re
import time
import argparse
import json
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from typing import List, Dict, Optional
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import requests
from bs4 import BeautifulSoup

# Optional selenium path
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
}

Min_sleep = 10
Max_sleep = 30  # be polite
results = []
listing_links = []
searching_links = []
existed_data = []
mainText = "start text \n"
# Helper regexes
NUM_RE = re.compile(r"[\d,\u0660-\u0669]+")
PERSIAN_DIGITS_MAP = {ord(c): ord('0') + i for i, c in enumerate('۰۱۲۳۴۵۶۷۸۹')}

districts_url = "https://raw.githubusercontent.com/rferdosi/tehran-districts/main/districts.json"
districts = gpd.read_file(districts_url)



def Read_Existing_house_File() -> list:
    with open("C:\\Users\\Zephuris\\Desktop\\divar_ads_scrap.json","r") as file:
        data = json.load(file)
        existed_data = data
    print(f"existing houses read successfully and count is : {len(existed_data)}")
    return existed_data
def Get_links():
    global searching_links
    with open("F:\\Notepad++\\divar links.txt","r") as file:
            for line in file:
                clean = line.strip().strip('"')
                searching_links.append(clean)
    print(f"links  read successfully and count is : {len(searching_links)}")

def random_sleep():
    secs = random.uniform(Min_sleep, Max_sleep)
    time.sleep(secs) 

def persian_to_english_numbers(s: str) -> str:
    return s.translate(PERSIAN_DIGITS_MAP)


def parse_number_from_text(s: str) -> Optional[int]:
    """Extract first integer-like number from text, handle Persian digits and commas."""
    if not s:
        return None
    s2 = persian_to_english_numbers(s)
    m = NUM_RE.search(s2)
    if not m:
        return None
    num = m.group(0).replace(',', '')
    try:
        return int(num)
    except Exception:
        return None


def extract_from_ad_html(html: str,link : str) -> Dict[str, Optional[int]]:
    
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(separator=' ', strip=True)
  
    area_match = re.search(r'(\d{1,3})\s*(?:متر|متری)', text)
    year_match = re.search(r"(\d{4})", text)
    room_match = re.search(r'متراژ[\s\u200c]*ساخت[\s\u200c]*اتاق[\s\u200c]*[۰-۹0-9]+[\s\u200c]+[۰-۹0-9]{4}[\s\u200c]+([۰-۹0-9]+)', text)
    price_match = re.search(r'قیمت کل\s*[^\d]*([\d،]+)', text)
    price_per_m_match = re.search(r"قیمت هر متر\s*[^\d]*([\d،]+)", text)
    floor_match = re.search(r"طبقه\s*(\d+)", text)
    geometric = re.findall(r'"latitude"\s*:\s*"([^"]+)"[^}]*?"longitude"\s*:\s*"([^"]+)"',html)
    latitude = re.search(r'"latitude"\s*:\s*"([^"]+)"',html).group(1)
    longitude = re.search(r'"longitude"\s*:\s*"([^"]+)"',html).group(1)
    has_parking = bool(re.search(r"(پارکینگ|پاركينگ)", text))
    has_storage = bool(re.search(r"(انباری|انبار|انبـاری)",text))
    has_elevator = bool(re.search(r"(آسانسور|اسانسور|آسانسور)",text))
    houseDistrinct = getDistrinct(latitude,longitude)
    current_house = {
        "area": area_match.group(1).strip() if area_match else None,
        "year": year_match.group(1) if year_match else None,
        "rooms": room_match.group(1) if room_match else None,
        "price_total": price_match.group(1).replace("،", "") if price_match else None,
        "price_per_m": price_per_m_match.group(1).replace("،", "") if price_per_m_match else None,
        "floor": floor_match.group(1) if floor_match else None,
        "hasParking":has_parking,
        "haStorage":has_storage,
        "has_elevator":has_elevator,
        "distrinct" : houseDistrinct,
        "link":link,
    }
    current_house['mainKey'] = "".join(str(int(v)) if isinstance(v, bool) 
                                       else str(v)
                                        for v in current_house.values())
    isExisted = any(house.get("mainKey") == current_house.get("mainKey") for house in existed_data)

    if(not isExisted):
        results.append(current_house)
        with open("C:\\Users\\Zephuris\\Desktop\\divar_ads_scrap.json", "a", encoding="utf-8") as f:
            json.dump(current_house, f, ensure_ascii=False, indent=4)
            print(f"house extracted\n {len(results)}")
    else:
        print(f"existed")
def get_listing_links_from_search_page(html: str) -> List[str]:
    soup = BeautifulSoup(html, 'html.parser')
    global listing_links
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('/v/') or '/?i=' in href or '/ad/' in href or '/post/' in href:
            full = requests.compat.urljoin('https://divar.ir', href)
            listing_links.append(full)
    print(f"count listing links : {len(listing_links)}")


def getDistrinct(latitude,longtitude):
    points_df = {
    'latitude':[latitude],
    'longitude' : [longtitude]
    } 
    geometry = [Point(xy) for xy in zip(points_df['longitude'], points_df['latitude'])]
    points_gdf = gpd.GeoDataFrame(points_df, geometry=geometry, crs="EPSG:4326")


    joined = gpd.sjoin(points_gdf, districts, how="left", predicate="within")
    result = joined[['latitude','longitude','index_right','name']]  
    return re.findall(r'\d+',result.at[0,'name'])[0]


def scrape_divar_search(city: str = 'tehran', pages: int = 1) -> List[Dict]:
    results = []
    session = requests.Session()
    session.headers.update(HEADERS)

    for page in range(1, pages + 1):
        html_pages = []
        page_html = None
        for index,url in enumerate(searching_links):
            try:
                random_sleep()
                r = session.get(url, timeout=30)
                print(f"link requested successfully{index}")
                if r.status_code == 200 and len(r.text) > 1000:
                    page_html = r.text
                    html_pages.append(page_html)
            except Exception:
                continue
        if not page_html:
            print(f"Warning: could not fetch search page {page} for city {city}")
            continue
        for page in html_pages:
            get_listing_links_from_search_page(page)
        print(f"Found {len(listing_links)} candidate ads")

        for adlink in listing_links:
            try:
                random_sleep()
                r = session.get(adlink, timeout=15)
                if r.status_code != 200:
                    continue
                extract_from_ad_html(r.text,adlink)

            except Exception as e:
                print('Error fetching ad', adlink, e)
    return results


def scrape_with_selenium(search_url: str, max_ads: int = 50) -> List[Dict]:
    if not SELENIUM_AVAILABLE:
        raise RuntimeError('Selenium not available. Install selenium and webdriver-manager.')

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument("disable-blink-features")
    options.add_argument("disable-blink-features=AutomationControlled")
    services = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service= services , options=options)

    driver.get(search_url)
    time.sleep(2)
    last_height = driver.execute_script("return document.body.scrollHeight")
    scrolls = 0
    max_scrolls = 100
    scroll_pause_time = 2
    max_no_change=3
    heights = driver.execute_script(
            "return {body: document.body.scrollHeight, doc: document.documentElement.scrollHeight};"
    )
    print("initial heights:", heights)

    # Find the most scrollable candidate element (body/documentElement or a large div)
    scrollable = driver.execute_script("""
        var els = Array.from(document.querySelectorAll('body, html, div, section, main, ul, [role=\"main\"]'));
        var candidates = els.map(e => ({el: e, diff: e.scrollHeight - e.clientHeight}));
        candidates = candidates.filter(c => c.diff>0).sort((a,b)=>b.diff - a.diff);
        return (candidates.length ? candidates[0].el : document.documentElement);
    """)
    # Print info about chosen element for debugging
    info = driver.execute_script(
        "return {overflow: window.getComputedStyle(arguments[0]).overflowY, scrollHeight: arguments[0].scrollHeight, clientHeight: arguments[0].clientHeight};",
        scrollable
    )
    print("chosen scrollable element info:", info)

    prev_count = -1
    no_change = 0
    scrolls = 0

    while no_change < max_no_change and scrolls < max_scrolls:
        for _ in range(3):
            driver.execute_script("arguments[0].scrollTop += Math.max(300, arguments[0].clientHeight/2);", scrollable)
            driver.execute_script("var last = arguments[0].querySelector('a:last-of-type'); if(last) last.scrollIntoView();", scrollable)
            time.sleep(0.2)

        time.sleep(3)  
        anchors = driver.find_elements(By.TAG_NAME, "a")
        hrefs = [a.get_attribute("href") for a in anchors if a.get_attribute("href")]
        curr_count = len(hrefs)
        print(f"scroll {scrolls}: link_count = {curr_count}")

        if curr_count == prev_count:
            no_change += 1
        else:
            prev_count = curr_count
            no_change = 0

        scrolls += 1

    if no_change >= max_no_change:
        print("no further change detected with container scroll — trying window scroll and PAGE_DOWN fallback")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        body = driver.find_element(By.TAG_NAME, "body")
        for _ in range(10):
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.5)

    time.sleep(1)  

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    get_listing_links_from_search_page(str(soup))
    results = []
    count = 0
    for link in listing_links:
        if count >= max_ads:
            break
        try:
            driver.get(link)
            time.sleep(1.2)
            html = driver.page_source
            data = extract_from_ad_html(html,link)
            results.append(data)
            count += 1
        except Exception as e:
            print('selenium ad error', e)
    driver.quit()
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--city', default='tehran')
    parser.add_argument('--pages', type=int, default=20000)
    parser.add_argument('--use-selenium', action='store_true')
    args = parser.parse_args()
    Read_Existing_house_File()
    Get_links()
    if args.use_selenium:
        search_url = f'https://divar.ir/s/tehran/buy-residential'
        print('Using selenium to scrape', search_url)
        out = scrape_with_selenium(search_url, max_ads=20000)
    else:
        out = scrape_divar_search(args.city, pages=args.pages)

    print("Added Successfully!")
