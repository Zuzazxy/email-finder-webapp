from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import urllib.parse
import requests
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Jinja2 Templates for HTML rendering
templates = Jinja2Templates(directory="templates")

# Hunter API Key
HUNTER_API_KEY = "HUNTER_API_KEY_email_finder"

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

@app.get("/")
async def get_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/mcp/email_guess_v3")
async def email_lookup_v3(data: MCPInput, request: Request):
    name = data.name
    domain = data.domain
    company = data.company

    # check email (Hunter)
    hunter_result = search_email_hunter(domain, name)

    # guessing
    guessed_emails = generate_possible_emails(name, domain)

    # LinkedIn links searching
    linkedin = generate_linkedin_search_url(name, company)

    # preparing rows for Excel
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
    file_path = "email_results.xlsx"
    df = pd.DataFrame(rows)
    df.to_excel(file_path, index=False)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "has_result": True,
        "verified_email": hunter_result.get("email") if hunter_result else None,
        "hunter_score": hunter_result.get("score") if hunter_result else None,
        "guessed_emails": guessed_emails,
        "linkedin_link": linkedin,
        "export_file": "/download/excel"
    })

@app.get("/download/excel")
async def download_excel():
    file_path = "email_results.xlsx"
    return StreamingResponse(open(file_path, mode="rb"), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=email_results.xlsx"})
