import asyncio
import logging

import aiohttp

from summer_internships_scraper.repository.jobs import JobRepository
from summer_internships_scraper.scraper.scraper import LinkedInScraper
from summer_internships_scraper.utils.constants import HOST, LOCATIONS
from summer_internships_scraper.utils.markdown_export import export_to_markdown

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    scraper = LinkedInScraper(HOST)
    repo = JobRepository()

    async with aiohttp.ClientSession() as session:
        tasks = []
        for location, geo_id in LOCATIONS.items():
            logger.info(f"Fetching jobs for {location}")
            tasks.append(
                scraper.fetch_jobs(
                    location=(geo_id, location), keywords="Summer 2026", session=session
                )
            )

        results = await asyncio.gather(*tasks)

        total_new_jobs = 0
        for jobs in results:
            if jobs is not None:
                new_jobs, total_jobs = repo.add_jobs(jobs)
                total_new_jobs += new_jobs
                logger.info(
                    f"Added {new_jobs} new jobs. Total jobs in storage: {total_jobs}"
                )

    all_jobs = repo.get_all_jobs()
    export_to_markdown(all_jobs)
    logger.info(f"Generated markdown file with {len(all_jobs)} jobs")


if __name__ == "__main__":
    asyncio.run(main())
