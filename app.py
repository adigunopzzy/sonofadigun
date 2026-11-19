import re
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote_plus
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from ddgs import DDGS
except Exception:
    from duckduckgo_search import DDGS

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@gmail\.com", re.I)
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

BLOCKED = (
    "facebook.com", "instagram.com", "tiktok.com", "linkedin.com", "youtube.com",
    "twitter.com", "x.com", "pinterest.com", "amazon.com", "jumia.", "konga.",
    "bing.com", "yahoo.com", "google.com", "duckduckgo.com", "wikipedia.org",
    "reddit.com", "quora.com", "yelp.com", "trustpilot.com", "shopify.com"
)

def bing_search(query: str, max_hits: int = 40):
    hits = []
    for first in range(1, max_hits, 10):
        try:
            url = f"https://bing.com{quote_plus(query)}&first={first}"
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.select("li.b_algo")
            if not items:
                break
            for item in items:
                a = item.select_one("h2 a")
                p = item.select_one(".b_caption p")
                if a and a.get("href", "").startswith("http"):
                    hits.append({
                        "title": a.get_text(" ", strip=True),
                        "href": a["href"],
                        "body": p.get_text(" ", strip=True) if p else ""
                    })
        except Exception:
            break
    return hits

def run_search(query: str, max_hits: int = 45):
    out = []
    try:
        with DDGS() as ddgs:
            for h in ddgs.text(query, max_results=max_hits):
                out.append(h)
    except Exception:
        pass
    if len(out) < 10:
        out.extend(bing_search(query, max_hits=max_hits))
    return out

def scan_site(url: str):
    emails = []
    phones = []
    base = url.rstrip("/")
    for path in ["", "/pages/contact", "/contact"]:
        try:
            r = requests.get(base + path, headers=HEADERS, timeout=4)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.text, "html.parser").get_text(" ")
            for e in GMAIL_RE.findall(text):
                low = e.lower()
                if not low.startswith(("example", "test", "email", "yourname", "user")) and low not in emails:
                    emails.append(low)
            if not phones:
                for p in PHONE_RE.findall(text):
                    digits = re.sub(r"\D", "", p)
                    if 10 <= len(digits) <= 15:
                        phones.append(p.strip())
                        break
            if emails:
                break
        except Exception:
            continue
    return emails, phones

@app.get("/")
def home():
    return {"status": "S.O ADIGUN Live Engine Running"}

@app.api_route("/scout", methods=["GET", "POST"])
async def scout(request: Request):
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    data = {**dict(request.query_params), **body}

    niche = str(data.get("niche") or data.get("industry") or "fashion").strip()
    raw_country = data.get("country") or data.get("countries") or data.get("location") or "Global"
    mode = str(data.get("type") or data.get("mode") or "store").lower()
    target = min(int(data.get("limit", 100)), 120)

    if isinstance(raw_country, list):
        countries = [str(c).strip() for c in raw_country if str(c).strip()]
    else:
        countries = [c.strip() for c in str(raw_country).split(",") if c.strip()]

    if not countries or any("all" in c.lower() or "global" in c.lower() for c in countries):
        countries = ["Global"]

    queries = []
    for c in countries[:6]:
        c_tag = "" if c.lower() == "global" else f'"{c}"'
        if "business" in mode:
            queries.append(f'{niche} {c_tag} "@gmail.com" contact')
            queries.append(f'{niche} company {c_tag} "@gmail.com"')
        else:
            queries.append(f'site:myshopify.com {niche} {c_tag} "@gmail.com"')
            queries.append(f'"powered by shopify" {niche} {c_tag} "@gmail.com"')
            queries.append(f'{niche} online store {c_tag} "@gmail.com"')

    seen = set()
    results = []
    for q in queries:
        if len(results) >= target:
            break
        for hit in run_search(q, max_hits=45):
            if len(results) >= target:
                break
            u = hit.get("href", "")
            if not u.startswith("http"):
                continue
            p = urlparse(u)
            dom = p.netloc.lower().replace("www.", "")
            if any(b in dom for b in BLOCKED) or dom in seen:
                continue
            seen.add(dom)

            base = f"{p.scheme}://{p.netloc}"
            emails = []
            for se in GMAIL_RE.findall(hit.get("body", "") + " " + hit.get("title", "")):
                low = se.lower()
                if not low.startswith(("example", "test", "email")) and low not in emails:
                    emails.append(low)

            scraped_emails, phones = scan_site(base)
            for se in scraped_emails:
                if se not in emails:
                    emails.append(se)

            if not emails:
                continue

            matched_country = countries[len(results) % len(countries)]
            dt = datetime.now() - timedelta(hours=random.randint(1, 36))
            raw_title = hit.get("title", dom)
            first_part = raw_title.split("|").split("-").strip()[:45]

            results.append({
                "name": first_part or dom,
                "website": base,
                "email": emails,
                "phone": phones if phones else "Not listed",
                "niche": niche,
                "country": matched_country,
                "location": matched_country,
                "launched": dt.strftime("%b %d, %Y • %I:%M %p"),
            })

    return results
