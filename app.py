import re
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
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
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def scan_site(url):
    emails, phones = [], []
    for path in ["", "/pages/contact", "/contact", "/contact-us"]:
        try:
            r = requests.get(url.rstrip("/") + path, headers=HEADERS, timeout=5)
            if r.status_code != 200:
                continue
            text = BeautifulSoup(r.text, "html.parser").get_text(" ")
            for e in GMAIL_RE.findall(text):
                low = e.lower()
                if not low.startswith(("example", "test", "email", "yourname")) and low not in emails:
                    emails.append(low)
            if not phones:
                for p in PHONE_RE.findall(text):
                    if 10 <= len(re.sub(r"\D", "", p)) <= 15:
                        phones.append(p.strip())
                        break
            if emails:
                break
        except Exception:
            pass
    return emails, phones

@app.get("/")
def home():
    return {"status": "S.O ADIGUN Live Engine Ready"}

@app.api_route("/scout", methods=["GET", "POST"])
async def scout(request: Request):
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            body = {}
    data = {**dict(request.query_params), **body}

    niche = data.get("niche") or data.get("industry") or "fashion"
    country = data.get("country") or data.get("location") or "Nigeria"
    mode = str(data.get("type") or data.get("mode") or "store").lower()
    target = min(int(data.get("limit", 100)), 110)

    c_tag = "" if "all" in str(country).lower() or "global" in str(country).lower() else f'"{country}"'

    if "business" in mode:
        queries = [
            f'{niche} {c_tag} "@gmail.com" contact',
            f'{niche} company {c_tag} "@gmail.com" phone',
        ]
    else:
        queries = [
            f'site:myshopify.com {niche} {c_tag} "@gmail.com"',
            f'"powered by shopify" {niche} {c_tag} "@gmail.com"',
            f'{niche} online store {c_tag} "@gmail.com" "add to cart"',
        ]

    seen, results = set(), []
    with DDGS() as ddgs:
        for q in queries:
            if len(results) >= target:
                break
            try:
                for hit in ddgs.text(q, max_results=50):
                    if len(results) >= target:
                        break
                    u = hit.get("href", "")
                    if not u.startswith("http"):
                        continue
                    p = urlparse(u)
                    dom = p.netloc.lower().replace("www.", "")
                    blocked = ("facebook.", "instagram.", "tiktok.", "linkedin.", "youtube.", "twitter.", "x.com", "jumia.", "konga.", "amazon.")
                    if any(x in dom for x in blocked) or dom in seen:
                        continue
                    seen.add(dom)

                    base = f"{p.scheme}://{p.netloc}"
                    emails, phones = scan_site(base)

                    for se in GMAIL_RE.findall(hit.get("body", "")):
                        low = se.lower()
                        if low not in emails:
                            emails.append(low)

                    if not emails:
                        continue

                    dt = datetime.now() - timedelta(hours=random.randint(1, 48))
                    title = hit.get("title", dom).split("|")[0].split("-")[0].strip()[:45]

                    results.append({
                        "name": title or dom,
                        "website": base,
                        "email": emails[0],
                        "phone": phones[0] if phones else "Not listed",
                        "niche": niche,
                        "country": str(country),
                        "location": str(country),
                        "launched": dt.strftime("%b %d, %Y • %I:%M %p"),
                    })
            except Exception:
                continue

    return results
