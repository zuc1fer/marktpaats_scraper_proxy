
"""
scraper_v2.py
"""

USE_PROXY = True
THREADS_COUNT = 150
PROXY_FILE_PATH = "proxies.txt"

import argparse
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Dict, Any, List, Set
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.marktplaats.nl"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

SKIP_PATTERNS = [
    r'\bop voorraad\b', r'\bleverbaar\b', r'\brefurbished\b', r'\bgarantie\b',
    r'\bshowroom\b', r'\bmontage\b', r'\binstallatie\b', r'\blegservice\b',
    r'\btickets\b', r'\bverhuur\b', r'\bte huur\b', r'\bdeal prijs\b',
    r'\bincl\.?\b', r'\binclusief\b', r'\bstuks\b', r'\bpartijen\b',
    r'\bpartijkoop\b', r'\bpartijverkoop\b', r'\bautomaat\b', r'\bwaardebonnen\b',
    r'\blegbordstelling\b', r'\bvitrine\b', r'\bwinkelkast\b', r'\bhoreca\b',
    r'\bmeubelrestauratie\b', r'\bgevraagd\b', r'\bgezocht\b', r'\brenovatie\b',
    r'\bvloer\b', r'\btrap\b', r'\bairco\b', r'\bvakantie\b', r'\bchalet\b',
    r'\bbed and breakfast\b', r'\bb&b\b', r'\bkantoor\b', r'\bbureau\b',
    r'\bgratis verzenden\b', r'\btotaal overzicht\b', r'\baanbieding\b',
    r'\bkoopje\b', r'\bop=op\b', r'\breparatie\b', r'\bverkoop\b',
    r'\bshop\b', r'\bstore\b', r'\bjuwelier\b', r'\bbv\b', r'\bvof\b',
    r'\bgroup\b', r'\bgroep\b', r'\bservice\b', r'\bhandel\b',
    r'\bgroothandel\b', r'\batelier\b', r'\bonderneming\b', r'\bspecialist\b',
    r'\bmodelbouw\b', r'\bbikesland\b',
    r'\.nl\b', r'\.com\b', r'\.be\b', r'\.eu\b', r'\.org\b',
    r'\bwww\.\b', r'\bhttp\b', r'\bwebsite\b', r'\bwebshop\b',
    r'\bonline\b', r'\be-commerce\b', r'\bgrote aantallen\b',
    r'\bwholesale\b', r'\bretail\b', r'\bbedrijf\b', r'\bcompany\b',
    r'\bltd\b', r'\blimited\b', r'\bcorp\b', r'\bcorporation\b',
    r'\bfabrikant\b', r'\bimporteur\b', r'\bdistributeur\b',
    r'\bvoordeel\b', r'\bactie\b', r'\bkorting\b', r'\bsale\b',
    r'\bpakket\b', r'\bset van\b', r'\bbulk\b', r'\bvoorraad\b',
    r'\blevertijd\b', r'\blevering\b', r'\bmagazijn\b', r'\bopslag\b',
    r'\bvakman\b', r'\binstallateur\b', r'\bmonteur\b', r'\btechniek\b',
    r'\bverhuurservice\b', r'\brentals?\b', r'\blease\b', r'\bleasing\b',
    r'\breclame\b', r'\bpromotie\b', r'\bsponsoring\b',
    r'\bzoekt\b', r'\bwil kopen\b', r'\bgroot aantal\b',
    r'\bper stuk\b', r'\bper set\b', r'\bminimum afname\b',
    r'\bcertificaat\b', r'\bgediplomeerd\b', r'\berkend\b',
    r'\ball-in\b', r'\bpakket deal\b', r'\bcombinatie\b',
    r'\btweedehands zaak\b', r'\bkringloop\b', r'\bopkoper\b',
]

SKIP_REGEX = re.compile('|'.join(SKIP_PATTERNS), re.IGNORECASE)


def parse_proxy_string(proxy_string: str) -> Optional[Dict[str, Any]]:
    if not proxy_string:
        return None
    try:
        parts = proxy_string.split(':')
        if len(parts) != 4:
            return None
        hostname, port, username, password = parts
        try:
            port_int = int(port)
        except ValueError:
            return None
        return {
            'hostname': hostname.strip(),
            'port': port_int,
            'username': username.strip(),
            'password': password.strip()
        }
    except:
        return None


def load_proxies_from_file(path: str) -> List[Dict[str, Any]]:
    proxies: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return proxies
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            cfg = parse_proxy_string(raw)
            if cfg:
                proxies.append(cfg)
    if proxies:
        print(f"Loaded {len(proxies)} proxies from file.")
    return proxies


def create_session(user_agent: str = DEFAULT_USER_AGENT, proxy_config: Optional[Dict[str, Any]] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": user_agent,
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    })
    if proxy_config:
        proxy_url = f"http://{proxy_config['username']}:{proxy_config['password']}@{proxy_config['hostname']}:{proxy_config['port']}"
        s.proxies = {'http': proxy_url, 'https': proxy_url}
        s.timeout = 20
    else:
        s.timeout = 15
    return s


def _extract_braced_object(text: str, start_pos: int) -> Optional[str]:
    i = start_pos
    n = len(text)
    stack = []
    in_str = False
    str_char = None
    escape = False
    while i < n:
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == str_char:
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
            elif ch == "{":
                stack.append("{")
            elif ch == "}":
                if not stack:
                    return text[start_pos:i + 1]
                stack.pop()
                if not stack:
                    return text[start_pos:i + 1]
        i += 1
    return None


def find_config_object(text: str) -> Optional[Dict[str, Any]]:
    m = re.search(r'window\.__CONFIG__\s*=\s*{', text) or re.search(r'__CONFIG__\s*=\s*{', text)
    if not m:
        return None
    obj_start = text.find("{", m.end() - 1)
    if obj_start == -1:
        return None
    obj_text = _extract_braced_object(text, obj_start)
    if not obj_text:
        return None
    obj_text = obj_text.rstrip()
    if obj_text.endswith(";"):
        obj_text = obj_text[:-1]
    try:
        return json.loads(obj_text)
    except:
        cleaned = re.sub(r',\s*([}\]])', r'\1', obj_text)
        try:
            return json.loads(cleaned)
        except:
            return None


def normalize_phone(phone_raw: Optional[str]) -> str:
    if not phone_raw:
        return ""
    return re.sub(r"[^\d+]", "", phone_raw)


def parse_price_text(price_text: str) -> Optional[float]:
    if not price_text:
        return None
    txt = re.sub(r"[^\d\.,\-]", "", price_text.strip())
    if not txt:
        return None
    if "." in txt and "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    else:
        if "." in txt and "," not in txt:
            txt = txt.replace(".", "")
        if "," in txt and "." not in txt:
            txt = txt.replace(",", ".")
    try:
        return float(txt)
    except:
        return None


def extract_price_from_soup(soup: BeautifulSoup) -> Optional[float]:
    el = soup.select_one("div.ListingHeader-price") or soup.find(attrs={"class": re.compile(r"ListingHeader-price")})
    if el:
        raw = el.get_text(separator=" ", strip=True)
        return parse_price_text(raw)
    return None


def extract_ld_breadcrumb_name(soup: BeautifulSoup) -> Optional[str]:
    scripts = soup.find_all("script", {"type": "application/ld+json"})
    for s in scripts:
        raw = s.string or "".join(t for t in s.contents if isinstance(t, str)).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except:
            try:
                first, last = raw.find("{"), raw.rfind("}")
                if first != -1 and last != -1 and last > first:
                    parsed = json.loads(raw[first:last+1])
                else:
                    continue
            except:
                continue
        items = parsed if isinstance(parsed, list) else [parsed] if isinstance(parsed, dict) else []
        for obj in items:
            if isinstance(obj, dict):
                if isinstance(obj.get("itemListElement"), list) and obj["itemListElement"]:
                    name = obj["itemListElement"][-1].get("name")
                    if name:
                        return name
                if isinstance(obj.get("@graph"), list):
                    for node in obj["@graph"]:
                        ile = node.get("itemListElement")
                        if isinstance(ile, list) and ile:
                            name = ile[-1].get("name")
                            if name:
                                return name
    return None


def listing_has_website_button(soup: BeautifulSoup) -> bool:
    if soup.select_one("i.hz-SvgIconWebsite"):
        return True
    for a in soup.select('a.SellerContactOptions-link'):
        text = a.get_text(separator=" ", strip=True).lower()
        if "website" in text:
            return True
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("https://admarkt.marktplaats.nl/bside/url/"):
            return True
    return False


def is_business_seller(seller_name: Optional[str]) -> bool:
    if not seller_name:
        return False
    
    if SKIP_REGEX.search(seller_name):
        return True
    
    name_lower = seller_name.lower()
    
    capitals = sum(1 for c in seller_name if c.isupper())
    if capitals > 5 and len(seller_name) > 10:
        return True
    
    if any(x in name_lower for x in ['bv ', ' bv', 'b.v.', 'vof ', ' vof', 'v.o.f.']):
        return True
    
    if re.search(r'\d{3,}', seller_name) or '@' in seller_name:
        return True
    
    if len(seller_name) > 8 and seller_name.isupper():
        return True
    
    return False


def extract_listing_from_html(html: str, url: str) -> Dict[str, Optional[Any]]:
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "url": url,
        "listing_name": None,
        "seller_name": None,
        "location": None,
        "phone": None,
        "price": None,
    }

    listing_name = extract_ld_breadcrumb_name(soup)
    if listing_name:
        result["listing_name"] = listing_name

    cfg = find_config_object(html)
    if cfg:
        listing = cfg.get("listing", {}) or {}
        seller = listing.get("seller", {}) or {}

        result["seller_name"] = seller.get("name") or (
            listing.get("customDimensions") and next((d.get("value") for d in listing.get("customDimensions", []) if d.get("index") == "seller_name"), None)
        )

        loc = seller.get("location")
        if isinstance(loc, dict):
            result["location"] = loc.get("cityName") or loc.get("city") or None

        phone_raw = seller.get("phoneNumber") or seller.get("phone") or None
        if phone_raw:
            result["phone"] = normalize_phone(phone_raw)

        price_info = listing.get("priceInfo") or {}
        price_cents = price_info.get("priceCents")
        if price_cents is not None:
            try:
                result["price"] = int(price_cents) / 100.0
            except:
                pass

        if not result["listing_name"]:
            title = listing.get("title")
            if title:
                result["listing_name"] = title

    if not result["seller_name"]:
        el = soup.select_one("div.PhoneDialog-name")
        if el:
            result["seller_name"] = el.get_text(strip=True)

    if not result["location"]:
        el = soup.select_one("div.PhoneDialog-location")
        if el:
            loctxt = el.get_text(separator=" ", strip=True)
            loctxt = re.sub(r"^\W+", "", loctxt)
            parts = loctxt.split()
            result["location"] = parts[-1] if parts else loctxt

    if not result["phone"]:
        el = soup.select_one("div.PhoneDialog-phone")
        if el:
            pr = el.get_text(strip=True)
            result["phone"] = normalize_phone(pr)

    if not result["price"]:
        price_numeric = extract_price_from_soup(soup)
        if price_numeric:
            result["price"] = price_numeric

    if not result["listing_name"]:
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            result["listing_name"] = h1.get_text(strip=True)
        else:
            meta = soup.find("meta", {"property": "og:title"}) or soup.find("meta", {"name": "twitter:title"})
            if meta and meta.get("content"):
                result["listing_name"] = meta.get("content")

    skip_reasons = []
    
    if listing_has_website_button(soup):
        skip_reasons.append("website_button")
    
    if is_business_seller(result.get("seller_name")):
        skip_reasons.append("business_seller")
    
    if skip_reasons:
        result["_skip"] = skip_reasons
        return result

    return result


def extract_listing_links_from_search(html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("a.hz-Link.hz-Link--block.hz-Listing-coverLink")
    links = []
    for a in anchors:
        href = a.get("href")
        if not href:
            continue
        full = urljoin(BASE, href)
        if full not in links:
            links.append(full)
    return links


def get_total_pages_for_keyword(session: requests.Session, keyword: str) -> Optional[int]:
    token = make_keyword_token(keyword)
    search_url = f"{BASE}/q/{token}/"
    
    try:
        html = fetch_url(session, search_url, delay=0.0, max_retries=2)
        if not html:
            return None
        
        soup = BeautifulSoup(html, "html.parser")
        pagination_span = soup.select_one("span.hz-PaginationControls-pagination-amountOfPages")
        if not pagination_span:
            return None
        
        text = pagination_span.get_text(strip=True)
        match = re.search(r'van\s+(\d+)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        return None
    except Exception:
        return None


def fetch_url(session: requests.Session, url: str, delay: float = 0.0, max_retries: int = 3) -> Optional[str]:
    for attempt in range(max_retries):
        try:
            if delay:
                time.sleep(delay)
            r = session.get(url, timeout=session.timeout)
            r.raise_for_status()
            return r.text
        except:
            if attempt == max_retries - 1:
                return None
            time.sleep(1)
    return None


def is_dutch_mobile(phone_number):
    if not phone_number:
        return False
    phone_str = str(phone_number)
    if 'e+' in phone_str.lower():
        try:
            phone_str = str(int(float(phone_str)))
        except:
            return False
    clean_number = re.sub(r'[\s\-\(\)]', '', phone_str)
    return bool(
        re.match(r'^06\d{8}$', clean_number) or
        re.match(r'^\+316\d{8}$', clean_number) or
        re.match(r'^316\d{8}$', clean_number)
    )


def normalize_phone_number(phone_number):
    if not phone_number:
        return None
    phone_str = str(phone_number)
    if 'e+' in phone_str.lower():
        try:
            phone_str = str(int(float(phone_str)))
        except:
            return None
    clean_number = re.sub(r'[\s\-\(\)]', '', phone_str)
    if re.match(r'^06\d{8}$', clean_number):
        return '+31' + clean_number[1:]
    if re.match(r'^\+316\d{8}$', clean_number):
        return clean_number
    if re.match(r'^316\d{8}$', clean_number):
        return '+' + clean_number
    return clean_number


def create_whatsapp_link(phone: str) -> Optional[str]:
    if not phone:
        return None
    clean = re.sub(r'[^\d+]', '', phone)
    if clean.startswith('+'):
        clean = clean[1:]
    elif clean.startswith('0'):
        clean = '31' + clean[1:]
    return f"https://wa.me/{clean}"


def gather_listing_links_parallel(session_template: requests.Session, keyword: str, pages: int, 
                                   max_links: int, delay: float, workers: int,
                                   proxy_pool: Optional[List[Dict[str, Any]]]) -> List[str]:
    token = make_keyword_token(keyword)
    collected: List[str] = []
    seen: Set[str] = set()
    
    search_urls = []
    for page in range(1, pages + 1):
        search_url = f"{BASE}/q/{token}/" if page == 1 else f"{BASE}/q/{token}/p/{page}/"
        search_urls.append(search_url)
    
    print(f"  Fetching {len(search_urls)} search pages in parallel...")
    
    def pick_proxy(i: int) -> Optional[Dict[str, Any]]:
        if not proxy_pool:
            return None
        return proxy_pool[i % len(proxy_pool)]
    
    with ThreadPoolExecutor(max_workers=min(workers, len(search_urls))) as ex:
        futures = {}
        for idx, url in enumerate(search_urls):
            sess = create_session(session_template.headers.get('User-Agent'), pick_proxy(idx))
            futures[ex.submit(fetch_url, sess, url, delay)] = url
        
        for fut in as_completed(futures):
            url = futures[fut]
            html = None
            try:
                html = fut.result()
            except:
                pass
            
            if not html:
                continue
            
            links = extract_listing_links_from_search(html)
            for l in links:
                if l not in seen:
                    seen.add(l)
                    collected.append(l)
                    if len(collected) >= max_links:
                        return collected
    
    print(f"   Found {len(collected)} unique listing links")
    return collected


def run_single_keyword(keyword: str, pages: int, max_links: int, workers: int, delay: float, 
                       user_agent: str, proxy_pool: Optional[List[Dict[str, Any]]] = None,
                       global_seen_phones: Set[str] = None,
                       global_seen_urls: Set[str] = None) -> Dict[str, List]:
    if global_seen_phones is None:
        global_seen_phones = set()
    if global_seen_urls is None:
        global_seen_urls = set()
        
    base_session = create_session(user_agent, proxy_pool[0] if proxy_pool else None)
    
    print(f"\n--- SEARCHING FOR: '{keyword}' ---")
    print(f"Gathering listing links for '{keyword}' from {pages} page(s) (max {max_links} links)...")
    
    listing_urls = gather_listing_links_parallel(base_session, keyword, pages, max_links, delay, workers, proxy_pool)
    
    if not listing_urls:
        print(f"No listing links collected for '{keyword}'.")
        return {"full": [], "phones": [], "links": [], "stats": {"skipped": {"website_button": 0, "business_seller": 0, "no_phone": 0, "duplicate": 0}}}

    print(f"Scraping {len(listing_urls)} listings with {workers} workers...")

    results_full: List[Dict[str, Any]] = []
    results_phones: List[str] = []
    results_links: List[str] = []
    
    skipped = {"website_button": 0, "business_seller": 0, "no_phone": 0, "duplicate": 0}

    def pick_proxy(i: int) -> Optional[Dict[str, Any]]:
        if not proxy_pool:
            return None
        return proxy_pool[i % len(proxy_pool)]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        for idx, url in enumerate(listing_urls):
            sess = create_session(user_agent, pick_proxy(idx))
            futures[ex.submit(fetch_url, sess, url, delay * 0.5)] = url

        done = 0
        for fut in as_completed(futures):
            url = futures[fut]
            done += 1
            html = None
            try:
                html = fut.result()
            except:
                pass

            if not html:
                continue

            data = extract_listing_from_html(html, url)

            if isinstance(data, dict) and data.get("_skip"):
                skip_reasons = data["_skip"]
                for reason in skip_reasons:
                    skipped[reason] = skipped.get(reason, 0) + 1
                continue

            phone = data.get("phone")
            
            if not phone or not is_dutch_mobile(phone):
                skipped["no_phone"] = skipped.get("no_phone", 0) + 1
                continue
            
            normalized_phone = normalize_phone_number(phone)
            if not normalized_phone:
                skipped["no_phone"] = skipped.get("no_phone", 0) + 1
                continue
            
            if normalized_phone in global_seen_phones or url in global_seen_urls:
                skipped["duplicate"] += 1
                continue
            
            global_seen_phones.add(normalized_phone)
            global_seen_urls.add(url)
            
            results_phones.append(normalized_phone)
            results_links.append(url)
            
            whatsapp_link = create_whatsapp_link(normalized_phone)
            listing_name = data.get('listing_name', '')
            if listing_name and len(listing_name) > 80:
                listing_name = listing_name[:80] + '...'
            
            full_entry = {
                'listing_name': listing_name,
                'seller_name': data.get('seller_name'),
                'location': data.get('location'),
                'phone': normalized_phone,
                'price': data.get('price'),
                'whatsapp': whatsapp_link,
                'url': url
            }
            results_full.append(full_entry)
            
            if done % 20 == 0 or done == len(listing_urls):
                print(f"  [{done}/{len(listing_urls)}] Valid: {len(results_full)} | "
                      f"Skip: web={skipped['website_button']} biz={skipped['business_seller']} "
                      f"dup={skipped['duplicate']} no_phone={skipped['no_phone']}")

    print(f"\nCompleted '{keyword}': {len(results_full)} new valid listings")
    
    return {
        "full": results_full,
        "phones": results_phones,
        "links": results_links,
        "stats": {"skipped": skipped}
    }


def make_keyword_token(keyword: str) -> str:
    return quote_plus(keyword)


def parse_keywords(keyword_string: str) -> List[str]:
    if '||' in keyword_string:
        parts = keyword_string.split('||')
        return [part.strip() for part in parts if part.strip()]
    
    if '|' in keyword_string:
        parts = keyword_string.split('|')
        return [part.strip() for part in parts if part.strip()]
    
    return [keyword_string.strip()]


def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_pages_for_keywords_parallel(keywords: List[str], user_agent: str, 
                                    proxy_pool: Optional[List[Dict[str, Any]]]) -> Dict[str, int]:
    print("\nDetecting available pages for all keywords in parallel...")
    
    keyword_pages = {}
    
    def detect_pages(keyword: str, idx: int) -> tuple:
        proxy = proxy_pool[idx % len(proxy_pool)] if proxy_pool else None
        sess = create_session(user_agent, proxy)
        total = get_total_pages_for_keyword(sess, keyword)
        return (keyword, total)
    
    with ThreadPoolExecutor(max_workers=min(10, len(keywords))) as ex:
        futures = {ex.submit(detect_pages, kw, i): kw for i, kw in enumerate(keywords)}
        
        for fut in as_completed(futures):
            kw = futures[fut]
            try:
                keyword, total = fut.result()
                keyword_pages[keyword] = total
                if total:
                    print(f"  '{keyword}': {total} pages available")
                else:
                    print(f"  '{keyword}': Unable to detect pages")
            except:
                keyword_pages[kw] = None
                print(f"  '{keyword}': Failed to detect pages")
    
    return keyword_pages


def main():
    p = argparse.ArgumentParser(
        description="High-performance Marktplaats scraper with intelligent filtering",
        epilog="""
Examples:
  Single keyword:       python script.py --keyword "guitars"
  Multi-word keyword:   python script.py --keyword "album covers"
  Multiple keywords:    python script.py --keyword "guitars | drums | keyboards"
                        python script.py --keyword "album covers || vintage toys"
        """
    )
    p.add_argument("--keyword", "-k", required=False, 
                   help="Search keyword(s). Use '|' or '||' to separate multiple keywords. Spaces within keywords are preserved.")
    p.add_argument("--pages", "-p", type=int, default=None, 
                   help="Number of search pages (applies to all keywords if multiple)")
    p.add_argument("--max", "-m", type=int, default=1000, help="Max listings to scrape per keyword")
    p.add_argument("--workers", type=int, default=THREADS_COUNT, help="Parallel workers")
    p.add_argument("--delay", type=float, default=0.2, help="Delay between requests (seconds)")
    p.add_argument("--phones-output", default="phones.json", help="Phone numbers only output file")
    p.add_argument("--links-output", default="links.json", help="Listing links only output file")
    p.add_argument("--full-output", default="all_info.json", help="Full data output file")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header")
    p.add_argument("--use-proxy", dest="use_proxy", action="store_true", help="Enable proxy usage")
    p.add_argument("--no-proxy", dest="use_proxy", action="store_false", help="Disable proxy usage")
    p.set_defaults(use_proxy=USE_PROXY)
    p.add_argument("--proxies-file", default=PROXY_FILE_PATH, help="Proxy file path")

    args = p.parse_args()

    proxy_pool: Optional[List[Dict[str, Any]]] = None
    if args.use_proxy:
        proxy_pool = load_proxies_from_file(args.proxies_file)
        if not proxy_pool:
            print("No valid proxies loaded; using direct connection.")
            proxy_pool = None
    else:
        print("Using direct connection (no proxies).")

    keyword_string = args.keyword
    if not keyword_string:
        print("\n" + "="*70)
        print("KEYWORD INPUT")
        print("="*70)
        print("Enter your search keyword(s):")
        print("  - Single keyword: guitars")
        print("  - Multi-word keyword: album covers")
        print("  - Multiple keywords: guitars | drums | keyboards")
        print("  - Alternative separator: guitars || drums || keyboards")
        print("="*70)
        keyword_string = input("\nEnter keyword(s): ").strip()
        if not keyword_string:
            print("No keyword provided. Exiting.")
            return

    keywords = parse_keywords(keyword_string)
    
    if len(keywords) > 1:
        print(f"\n{'='*70}")
        print(f"Detected {len(keywords)} separate keywords:")
        for i, kw in enumerate(keywords, 1):
            print(f"  {i}. '{kw}'")
        print(f"{'='*70}")
    
    pages_input = args.pages
    keyword_pages_map = {}
    
    if pages_input is None:
        keyword_pages_info = get_pages_for_keywords_parallel(keywords, args.user_agent, proxy_pool)
        
        print("\n" + "="*70)
        for kw in keywords:
            total = keyword_pages_info.get(kw)
            if total:
                while True:
                    try:
                        raw = input(f"Pages for '{kw}' (1-{total}, default 1): ").strip()
                        if not raw:
                            keyword_pages_map[kw] = 1
                            break
                        pages_val = int(raw)
                        if 1 <= pages_val <= total:
                            keyword_pages_map[kw] = pages_val
                            break
                        else:
                            print(f"  Enter a number between 1 and {total}")
                    except ValueError:
                        print("  Enter a valid number")
            else:
                try:
                    raw = input(f"Pages for '{kw}' (default 1): ").strip()
                    keyword_pages_map[kw] = int(raw) if raw else 1
                except:
                    keyword_pages_map[kw] = 1
    else:
        for kw in keywords:
            keyword_pages_map[kw] = pages_input
    
    print(f"\n{'='*70}")
    print(f"TURBO SCRAPER INITIALIZED")
    print(f"{'='*70}")
    print(f"Keywords: {len(keywords)} total")
    for kw in keywords:
        pg = keyword_pages_map[kw]
        url_token = make_keyword_token(kw)
        print(f"  • '{kw}' → {pg} page(s)")
        print(f"    URL: {BASE}/q/{url_token}/")
    print(f"Max listings per keyword: {args.max}")
    print(f"Workers: {args.workers}")
    print(f"Delay: {args.delay}s")
    if proxy_pool:
        print(f"Proxies: {len(proxy_pool)} loaded")
    else:
        print("Proxies: Direct connection")
    print(f"{'='*70}\n")

    all_phones: List[str] = []
    all_links: List[str] = []
    all_full: List[Dict[str, Any]] = []
    
    global_seen_phones: Set[str] = set()
    global_seen_urls: Set[str] = set()
    
    total_stats = {
        "website_button": 0,
        "business_seller": 0,
        "no_phone": 0,
        "duplicate": 0
    }

    start_time = time.time()

    for i, keyword in enumerate(keywords, 1):
        print(f"\n{'='*70}")
        print(f"KEYWORD {i}/{len(keywords)}: '{keyword}'")
        print(f"{'='*70}")
        
        keyword_start = time.time()
        pages_for_kw = keyword_pages_map.get(keyword, 1)
        
        results = run_single_keyword(
            keyword=keyword.strip(),
            pages=pages_for_kw,
            max_links=args.max,
            workers=args.workers,
            delay=args.delay,
            user_agent=args.user_agent,
            proxy_pool=proxy_pool,
            global_seen_phones=global_seen_phones,
            global_seen_urls=global_seen_urls
        )
        
        keyword_time = time.time() - keyword_start
        
        all_phones.extend(results["phones"])
        all_links.extend(results["links"])
        all_full.extend(results["full"])
        
        kw_stats = results["stats"]["skipped"]
        for key in total_stats:
            total_stats[key] += kw_stats.get(key, 0)
        
        print(f"\nKeyword '{keyword}' completed in {keyword_time:.2f}s")
        print(f"  New valid listings: {len(results['full'])}")

    total_time = time.time() - start_time

    print(f"\n{'='*70}")
    print(f"WRITING RESULTS TO FILES")
    print(f"{'='*70}")

    if all_phones:
        print(f"Writing {len(all_phones)} phone numbers to {args.phones_output}")
        write_json(args.phones_output, all_phones)
    else:
        print("No phone numbers to write.")

    if all_links:
        print(f"Writing {len(all_links)} listing links to {args.links_output}")
        write_json(args.links_output, all_links)
    else:
        print("No links to write.")

    if all_full:
        print(f"Writing {len(all_full)} full entries to {args.full_output}")
        write_json(args.full_output, all_full)
    else:
        print("No full data to write.")

    print(f"\n{'='*70}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*70}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Total unique valid listings: {len(all_full)}")
    print(f"Total unique phone numbers: {len(all_phones)}")
    print(f"Total unique links: {len(all_links)}")
    if all_full:
        print(f"Average time per listing: {total_time/len(all_full):.2f}s")
    print(f"\nFiltering Statistics:")
    print(f"  Skipped (website button): {total_stats['website_button']}")
    print(f"  Skipped (business seller): {total_stats['business_seller']}")
    print(f"  Skipped (no valid phone): {total_stats['no_phone']}")
    print(f"  Skipped (duplicate): {total_stats['duplicate']}")
    print(f"\nOutput Files:")
    print(f"  {args.phones_output} - Phone numbers only")
    print(f"  {args.links_output} - Listing URLs only")
    print(f"  {args.full_output} - Complete data with WhatsApp links")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()