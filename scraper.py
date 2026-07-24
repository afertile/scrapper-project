from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


CONTACT_WORDS = (
    "contact",
    "contacts",
    "kontakty",
    "kontakt",
    "about",
    "company",
    "o-kompanii",
    "kontaktnaya-informaciya",
    "svyaz",
    "requisites",
    "rekvizity",
    "адрес",
    "контакт",
    "контакты",
    "о компании",
    "реквизиты",
)

SOCIAL_DOMAINS = (
    "instagram.com",
    "vk.com",
    "t.me",
    "telegram.me",
    "wa.me",
    "whatsapp.com",
    "facebook.com",
    "youtube.com",
    "rutube.ru",
    "ok.ru",
)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
PHONE_RE = re.compile(
    r"(?:\+?\d[\s().-]*){10,18}"
)


@dataclass
class ScrapeResult:
    input_url: str
    final_url: str = ""
    company_name: str = ""
    emails: set[str] = field(default_factory=set)
    phones: set[str] = field(default_factory=set)
    social_links: set[str] = field(default_factory=set)
    contact_pages: set[str] = field(default_factory=set)
    status: str = "ok"
    error: str = ""


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


def read_sites(path: str) -> list[str]:
    sites: list[str] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        sample = file.read(2048)
        file.seek(0)
        if "," in sample:
            reader = csv.DictReader(file)
            if reader.fieldnames and "url" in reader.fieldnames:
                sites = [row["url"] for row in reader if row.get("url")]
            else:
                file.seek(0)
                sites = [row[0] for row in csv.reader(file) if row]
        else:
            sites = [line.strip() for line in file if line.strip()]
    return [normalize_url(site) for site in sites if site.strip()]


def fetch(session: requests.Session, url: str, timeout: int) -> requests.Response:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; ContactScraperMVP/1.0; "
            "+https://example.local/b2b-crm)"
        )
    }
    response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response


def clean_phone(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .,-;:()")
    digits = re.sub(r"\D", "", value)
    if len(digits) < 10 or len(digits) > 15:
        return ""
    return value


def same_domain(url: str, candidate: str) -> bool:
    source_host = urlparse(url).netloc.lower().removeprefix("www.")
    candidate_host = urlparse(candidate).netloc.lower().removeprefix("www.")
    return source_host == candidate_host


def extract_company_name(soup: BeautifulSoup) -> str:
    og_title = soup.find("meta", property="og:site_name")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    title = soup.find("title")
    if title and title.get_text(strip=True):
        raw_title = unescape(title.get_text(" ", strip=True))
        return re.split(r"\s+[|–—-]\s+", raw_title)[0].strip()

    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) if h1 else ""


def extract_from_html(result: ScrapeResult, html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    if not result.company_name:
        result.company_name = extract_company_name(soup)

    result.emails.update(email.lower() for email in EMAIL_RE.findall(html + " " + text))

    for match in PHONE_RE.findall(text):
        phone = clean_phone(match)
        if phone:
            result.phones.add(phone)

    possible_contact_pages: list[str] = []
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        absolute = urljoin(page_url, href)
        label = link.get_text(" ", strip=True).lower()
        href_lower = href.lower()

        if any(domain in absolute.lower() for domain in SOCIAL_DOMAINS):
            result.social_links.add(absolute.split("#")[0])

        if href_lower.startswith("mailto:"):
            result.emails.update(email.lower() for email in EMAIL_RE.findall(href))

        if href_lower.startswith("tel:"):
            phone = clean_phone(href[4:])
            if phone:
                result.phones.add(phone)

        is_contact_link = any(word in href_lower or word in label for word in CONTACT_WORDS)
        if is_contact_link and same_domain(page_url, absolute):
            clean_url = absolute.split("#")[0]
            possible_contact_pages.append(clean_url)
            result.contact_pages.add(clean_url)

    return possible_contact_pages


def scrape_site(url: str, timeout: int, max_pages: int) -> ScrapeResult:
    result = ScrapeResult(input_url=url)
    session = requests.Session()

    try:
        response = fetch(session, url, timeout)
        result.final_url = response.url
        pages_to_try = extract_from_html(result, response.text, response.url)

        visited = {response.url.split("#")[0]}
        for page_url in pages_to_try[:max_pages]:
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                page_response = fetch(session, page_url, timeout)
                extract_from_html(result, page_response.text, page_response.url)
            except requests.RequestException:
                continue
    except requests.RequestException as exc:
        result.status = "error"
        result.error = str(exc)

    return result


def sorted_join(values: Iterable[str]) -> str:
    return "; ".join(sorted(value for value in values if value))


def write_results(path: str, results: list[ScrapeResult]) -> None:
    fieldnames = [
        "input_url",
        "final_url",
        "company_name",
        "emails",
        "phones",
        "social_links",
        "contact_pages",
        "status",
        "error",
    ]
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            writer.writerow(
                {
                    "input_url": item.input_url,
                    "final_url": item.final_url,
                    "company_name": item.company_name,
                    "emails": sorted_join(item.emails),
                    "phones": sorted_join(item.phones),
                    "social_links": sorted_join(item.social_links),
                    "contact_pages": sorted_join(item.contact_pages),
                    "status": item.status,
                    "error": item.error,
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find company contacts on a list of websites."
    )
    parser.add_argument("--input", default="sites.txt", help="Path to TXT or CSV with sites.")
    parser.add_argument("--output", default="results.csv", help="Path for CSV results.")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds.")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Maximum number of contact-like pages to visit per site.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sites = read_sites(args.input)
    if not sites:
        print(f"No sites found in {args.input}", file=sys.stderr)
        return 1

    results: list[ScrapeResult] = []
    for index, site in enumerate(sites, start=1):
        print(f"[{index}/{len(sites)}] Scraping {site}")
        results.append(scrape_site(site, args.timeout, args.max_pages))

    write_results(args.output, results)
    print(f"Done. Results saved to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
