"""Career Radar scraper. Runs daily on GitHub Actions, writes jobs.json."""
import json, os, re, urllib.request, urllib.parse, datetime

TITLE_OK = re.compile(r"quantity surveyor|cost (consultant|analyst|manager|estimator|control|planner)|estimator|estimating|project controls?|commercial (analyst|coordinator|manager)|contracts? (administrator|analyst|coordinator)|preconstruction|project (coordinator|manager|analyst)|capital projects?|infrastructure|owner.?s rep|development coordinator|construction management|real estate|financial analyst|business analyst|consultant|strategy|investment analyst|project finance|valuation|transaction advisory|procurement|sourcing|supply chain|operations analyst|asset management|business development", re.I)
TOO_SENIOR = re.compile(r"\b(senior|sr\.?|director|principal|vp|vice president|head of|chief)\b", re.I)
LOC_OK = re.compile(r"toronto|ontario|, on\b|mississauga|markham|vancouver|burnaby|british columbia|, bc\b|calgary|alberta|, ab\b|new york|, ny\b|canada|united states|remote", re.I)

# Company job-board tokens. Not all are verified: the log shows which ones worked.
# To add a company, find its careers page; if the URL contains boards.greenhouse.io/XYZ
# or jobs.lever.co/XYZ, add XYZ here.
GREENHOUSE = ["stantec", "wsp", "altusgroup", "colliersinternational", "brookfield", "linesight", "turnerandtownsend"]
LEVER = ["currieandbrown", "arcadis", "bentallgreenoak"]

ADZUNA_QUERIES = ["quantity surveyor", "cost consultant", "cost analyst", "construction estimator",
  "project controls analyst", "commercial analyst", "contracts administrator", "assistant project manager",
  "project coordinator construction", "capital projects analyst", "infrastructure analyst",
  "real estate analyst", "financial analyst infrastructure", "transaction advisory analyst",
  "procurement analyst construction", "preconstruction analyst"]
ADZUNA_PLACES = [("ca", "Toronto"), ("ca", "Vancouver"), ("ca", "Calgary"), ("us", "New York")]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "career-radar/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"&[a-z]+;", " ", html or ""))).strip()[:4000]

def adzuna():
    out, aid, key = [], os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not aid or not key:
        print("Adzuna: no keys set, skipping"); return out
    for country, city in ADZUNA_PLACES:
        for q in ADZUNA_QUERIES:
            u = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1?" + urllib.parse.urlencode(
                {"app_id": aid, "app_key": key, "results_per_page": 30, "what": q, "where": city,
                 "max_days_old": 30, "content-type": "application/json"})
            try:
                for j in get(u).get("results", []):
                    sal = ""
                    if j.get("salary_min"):
                        sal = f"${int(j['salary_min']):,}-${int(j.get('salary_max') or j['salary_min']):,}"
                    out.append({"title": j.get("title", ""), "company": (j.get("company") or {}).get("display_name", ""),
                        "location": (j.get("location") or {}).get("display_name", city), "salary": sal,
                        "posted": (j.get("created") or "")[:10], "url": j.get("redirect_url", ""),
                        "source": "Adzuna", "description": strip(j.get("description"))})
            except Exception as e:
                print(f"Adzuna {city}/{q}: {e}")
    print("Adzuna jobs:", len(out)); return out

def greenhouse():
    out = []
    for t in GREENHOUSE:
        try:
            data = get(f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true")
            n = 0
            for j in data.get("jobs", []):
                loc = (j.get("location") or {}).get("name", "")
                out.append({"title": j["title"], "company": t, "location": loc, "posted": (j.get("updated_at") or "")[:10],
                    "url": j.get("absolute_url", ""), "source": "Greenhouse (" + t + ")",
                    "description": strip(__import__("html").unescape(j.get("content", "")))}); n += 1
            print(f"Greenhouse {t}: {n} jobs")
        except Exception as e:
            print(f"Greenhouse {t}: not available ({e})")
    return out

def lever():
    out = []
    for t in LEVER:
        try:
            data = get(f"https://api.lever.co/v0/postings/{t}?mode=json")
            for j in data:
                out.append({"title": j.get("text", ""), "company": t, "location": (j.get("categories") or {}).get("location", ""),
                    "posted": datetime.datetime.fromtimestamp(j.get("createdAt", 0) / 1000).strftime("%Y-%m-%d") if j.get("createdAt") else "",
                    "url": j.get("hostedUrl", ""), "source": "Lever (" + t + ")", "description": strip(j.get("descriptionPlain", ""))})
            print(f"Lever {t}: {len(data)} jobs")
        except Exception as e:
            print(f"Lever {t}: not available ({e})")
    return out

def main():
    raw = adzuna() + greenhouse() + lever()
    seen, keep = set(), []
    for j in raw:
        if not j["title"] or not TITLE_OK.search(j["title"]) or TOO_SENIOR.search(j["title"]): continue
        if not LOC_OK.search(j.get("location", "")): continue
        k = j["url"] or (j["title"] + j["company"] + j["location"]).lower()
        if k in seen: continue
        seen.add(k); keep.append(j)
    with open("jobs.json", "w") as f: json.dump(keep, f)
    print("Wrote", len(keep), "jobs to jobs.json")

main()
