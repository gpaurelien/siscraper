import typing as t


def filter_jobs(
    jobs: t.List[dict],
    keyword: str | None = None,
    company: str | None = None,
) -> t.List[dict]:
    """
    Filter a list of job dicts based on a free-text keyword and/or company name.

    - ``keyword``: matched case-insensitively against title, company_name and location
    - ``company``: matched case-insensitively against company_name
    """

    if not jobs:
        return []

    keyword_norm = keyword.lower().strip() if keyword else None
    company_norm = company.lower().strip() if company else None

    def _match(job: dict) -> bool:
        title = (job.get("title", "") or "").lower()
        company_name = (job.get("company_name", "") or "").lower()

        if keyword_norm:
            if keyword_norm not in title:
                return False

        if company_norm:
            if company_norm not in company_name:
                return False

        return True

    return [job for job in jobs if _match(job)]
