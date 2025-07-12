import requests
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0"
}

def scrape_generic(url):
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # Try Open Graph first
        title = (soup.find("meta", property="og:title") or {}).get("content")
        price = (soup.find("meta", property="product:price:amount") or {}).get("content")

        # Fallbacks
        if not title and soup.title:
            title = soup.title.get_text(strip=True)
        if not price:
            price_tag = soup.find("span", class_="price") or soup.find("span", class_="sale-price")
            price = price_tag.get_text(strip=True) if price_tag else "N/A"

        return {
            "title": title or "Unknown Product",
            "price": price or "N/A"
        }

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return {
            "title": "Unknown Product",
            "price": "N/A"
        }

def scrape(url):
    return scrape_generic(url)
