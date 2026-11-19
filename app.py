import re
import random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def get_new_domains_from_crt(niche: str, limit: int = 120):
    domains = []
    seen = set()
    keywords = [w.strip().lower() for w in re.split(r"[,/\s]+", niche) if len(w.strip()) >= 3]
    if not keywords:
        keywords = ["shop", "store"]

    # Query newly issued SSL certificates for stores & niche keywords
    patterns = [f"%.myshopify.com"] + [f"%{kw}%.shop" for kw in keywords[:2]] + [f"%{kw}%.store" for kw in keywords[:2]]
    for pat in patterns:
        if len(domains) >= limit * 3:
            break
        try:
            url = f"https://crt.sh{pat}&output=json"
            r = requests.get(url, headers=HEADERS, timeout=12)
            if r.status_code != 200:
                continue
            entries = r.json()
            for item in entries:
                if len(domains) >= limit * 3:
                    break
                name_val = str(item.get("common_name") or item.get("name_value") or "").lower().strip()
                for raw_d in name_val.splitlines():
                    d = raw_d.replace("*.", "").strip()
                    if not d or "." not in d or d in seen:
                        continue
                    if any(skip in d for skip in ("shopify.com", "myshopify.com", "cloudflare", "amazonaws", "staging", "dev.", "test.")):
                        if not d.endswith(".myshopify.com") or d.count(".") != 2:
                            continue
                    seen.add(d)
                    ts = item.get("entry_timestamp") or item.get("not_before") or ""
                    domains.append((d, ts))
        except Exception:
            continue
    return domains

def check_single_store(domain_info, niche: str, country: str):
    domain, ts = domain_info
    base = f"https://{domain}"
    emails = []
    phones = []
    title = domain.split(".")[0].replace("-", " ").title()

    for path in ["", "/pages/contact", "/contact"]:
        try:
            r = requests.get(base + path, headers=HEADERS, timeout=4, allow_redirects=True)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            if path == "" and soup.title and soup.title.string:
                t = soup.title.string.strip()
                if t and len(t) > 2:
                    title = t.split("|")[0].split("-")[0].strip()[:45]

            text = soup.get_text(" ")
            for e in GMAIL_RE.findall(text):
                low = e.lower()
                if not low.startswith(("example", "test", "email", "yourname", "user", "info@example")) and low not in emails:
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

    if not emails:
        return None

    try:
        dt = datetime.fromisoformat(ts.replace("Z", "")) if ts else datetime.now() - timedelta(hours=random.randint(1, 24))
    except Exception:
        dt = datetime.now() - timedelta(hours=random.randint(1, 24))

    return {
        "name": title or domain,
        "website": base,
        "email": emails[0],
        "phone": phones[0] if phones else "Not listed",
        "niche": niche,
        "country": country,
        "location": country,
        "launched": dt.strftime("%b %d, %Y • %I:%M %p"),
    }

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
    target = min(int(data.get("limit", 100)), 110)

    if isinstance(raw_country, list):
        countries = [str(c).strip() for c in raw_country if str(c).strip()]
    else:
        countries = [c.strip() for c in str(raw_country).split(",") if c.strip()]
    if not countries or any("all" in c.lower() or "global" in c.lower() for c in countries):
        countries = ["Global"]

    candidates = get_new_domains_from_crt(niche, limit=target)
    results = []

    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [
            pool.submit(check_single_store, cand, niche, countries[idx % len(countries)])
            for idx, cand in enumerate(candidates[:250])
        ]
        for fut in as_completed(futures):
            lead = fut.result()
            if lead:
                results.append(lead)
                if len(results) >= target:
                    break

    return results
