import typing as t


def export_to_markdown(jobs: t.List[dict], output_file: str = "README.md"):
    """Generate a markdown file with job listings, separating internships and full-time."""

    internships: t.List[dict] = []
    full_time_jobs: t.List[dict] = []

    for job in jobs:
        is_full_time = job.get("full_time", False)
        if is_full_time:
            full_time_jobs.append(job)
        else:
            internships.append(job)

    total_offers = len(jobs)
    total_internships = len(internships)
    total_full_time = len(full_time_jobs)

    content = f"""# Summer 2026 opportunities

This list gets updated daily.

Posted on refers to the date when the offer was posted on LinkedIn.

Total: {total_offers} offers  
- Internships / entry-level: {total_internships}  
- Full-time: {total_full_time}

## Internships & entry-level positions ({total_internships} offers)

"""

    for job in sorted(internships, key=lambda x: x["posted_date"], reverse=True):
        content += f"""### {job['company_name']}
- **Position:** {job['title']}
- **Location:** {job['location']}
- **Posted on:** {job["posted_date"]}
- [Apply here]({job['url']})

"""

    content += f"""
## Full-time positions ({total_full_time} offers)

"""

    for job in sorted(full_time_jobs, key=lambda x: x["posted_date"], reverse=True):
        content += f"""### {job['company_name']}
- **Position:** {job['title']}
- **Location:** {job['location']}
- **Posted on:** {job["posted_date"]}
- [Apply here]({job['url']})

"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
