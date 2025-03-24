from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel  # ✅ 你需要加上这行！
from typing import List, Optional
import pandas as pd
import urllib.parse
import requests


app = FastAPI()

# 连接模板和静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 👇 这是关键：主页路由（确保写上）
@app.get("/", response_class=HTMLResponse)
async def serve_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# Hunter API
HUNTER_API_KEY = "72abdb0fed137f8113538a1732ad9a583186b927"

class MCPInput(BaseModel):
    name: str
    company: str
    domain: str

def generate_possible_emails(name: str, domain: str) -> List[str]:
    name_parts = name.lower().split()
    first = name_parts[0]
    last = name_parts[-1]
    initials = first[0]

    formats = [
        f"{first}.{last}@{domain}",
        f"{initials}.{last}@{domain}",
        f"{first}@{domain}",
        f"{last}@{domain}",
        f"{initials}{last}@{domain}"
    ]
    return formats

def generate_linkedin_search_url(name: str, company: str) -> str:
    query = urllib.parse.quote(f"{name} {company}")
    return f"https://www.linkedin.com/search/results/people/?keywords={query}"

def search_email_hunter(domain: str, name: str) -> Optional[dict]:
    url = f"https://api.hunter.io/v2/email-finder?domain={domain}&full_name={name}&api_key={HUNTER_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get("data", {})
        if data.get("email"):
            return {
                "email": data.get("email"),
                "score": data.get("score"),
                "sources": data.get("sources", [])
            }
    return None

@app.post("/mcp/email_guess_v3")
async def email_lookup_v3(data: MCPInput):
    name = data.name
    domain = data.domain
    company = data.company

    # check email（Hunter）
    hunter_result = search_email_hunter(domain, name)

    # guussing
    guessed_emails = generate_possible_emails(name, domain)

    # LinkedIn links searching
    linkedin = generate_linkedin_search_url(name, company)

    # importing
    rows = []

    if hunter_result:
        rows.append({
            "Type": "Hunter (Verified)",
            "Email": hunter_result["email"],
            "Score": hunter_result["score"]
        })

    for guess in guessed_emails:
        rows.append({
            "Type": "Guess",
            "Email": guess,
            "Score": ""
        })

    # save the Excel
    df = pd.DataFrame(rows)
    df.to_excel("email_results.xlsx", index=False)

    return {
        "verified_email": hunter_result.get("email") if hunter_result else None,
        "hunter_score": hunter_result.get("score") if hunter_result else None,
        "guessed_emails": guessed_emails,
        "linkedin_link": linkedin,
        "export_file": "/download/excel"
    }

@app.get("/download/excel")
async def download_excel():
    df = pd.read_excel("email_results.xlsx")
    return df.to_dict(orient="records")
