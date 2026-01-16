from urllib.parse import urlparse

def _clean_domain(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    domain = parsed.netloc.lower().strip()
    domain = domain.replace("www.", "")
    return domain

def logo_candidates(company_website: str) -> list[str]:
    domain = _clean_domain(company_website)
    if not domain:
        return []
    return [
        f"https://logo.clearbit.com/{domain}",
        f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
    ]

