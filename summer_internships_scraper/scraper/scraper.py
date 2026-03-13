import asyncio
import logging
import typing as t

import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Tag
from tenacity import retry, retry_if_exception, wait_fixed

from summer_internships_scraper.models.offers import JobOffer
from summer_internships_scraper.utils import HEADERS
from summer_internships_scraper.utils.exceptions import (
    ParsingError,
    RateLimitError,
    ScrapingError,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LinkedInScraper:
    def __init__(self, host: str, logger: logging.Logger = logger) -> None:
        self.host = host
        self.logger = logger

    async def fetch_jobs(
        self,
        location: t.Tuple[str, str],
        keywords: str,  # TODO: make this dynamic by letting the user input whatever he wants  # noqa: E501
        full_time: bool,
        session: aiohttp.ClientSession = None,
        max_pages: int = 3,
    ) -> t.Optional[t.List[JobOffer]]:
        """
        Retrieves jobs, parses them, and returns a list containing offers.

        :param location: A tuple containing the location ID and country name used by LinkedIn  # noqa: E501
        :param keywords: Keywords needed for the job search
        :param full_time: Whether it is a full-time job or an internship
        :param session: aiohttp client session
        :param max_pages: Maximum number of pages to scrape. Assume that 3rd page is the last revelant page.
        """
        geo_id, country = location
        keywords = self._format_keywords(keywords)
        step = 25
        sem = asyncio.Semaphore(3)

        async def fetch_throttled(url):
            async with sem:
                return await self._get_page(url, session)

        urls = [
            f"{self.host}/?keywords={keywords}&geoId={geo_id}&start={i * step}"
            for i in range(max_pages)
        ]
        pages = await asyncio.gather(*[fetch_throttled(url) for url in urls])

        jobs, filtered = [], 0
        for content in pages:
            soup = BeautifulSoup(content, "html.parser")
            cards = soup.find_all("div", class_="job-search-card")

            if not cards:
                continue

            for card in cards:
                if not self._filter_cards(card, full_time):
                    filtered += 1
                    continue
                try:
                    jobs.append(self._parse_job_card(card, full_time))
                except Exception as err:
                    raise ParsingError("Error while parsing job card") from err

        self.logger.info(
            f"Retrieved {len(jobs) + filtered} jobs for {country}. Filtered out {filtered}."
        )
        return jobs

    @retry(
        retry=retry_if_exception(lambda e: isinstance(e, RateLimitError)),
        wait=wait_fixed(3),
    )
    async def _get_page(self, url: str, session: aiohttp.ClientSession) -> str:
        async with session.get(
            url,
            headers=HEADERS,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status == 429:
                self.logger.error(
                    f"Got rate limited on {url}, will try again in a few moments"
                )
                raise RateLimitError(f"Got rate limited on {url}")
            if response.status != 200:
                self.logger.error(
                    f"Scraping failed due to {response.status} on: {url}"
                )
                raise ScrapingError(f"Error while requesting {url}")

            return await response.text(encoding="utf-8")

    def _format_keywords(self, keywords: str) -> str:
        return keywords.replace(" ", "%20")

    def _parse_job_card(self, card: Tag, full_time: bool) -> JobOffer:
        title = (
            card.find("h3", class_="base-search-card__title").text.strip() or None
        )
        name = card.find("h4", class_="base-search-card__subtitle").text.strip()
        location = (
            card.find("span", class_="job-search-card__location").text.strip()
            or None
        )
        link = card.find("a", class_="base-card__full-link")
        url = link.get("href") if link else None
        datetime_element = card.find("time")
        posted_date = datetime_element.get("datetime") if datetime_element else None

        return JobOffer(
            title=title,
            company_name=name,
            location=location,
            url=url,
            posted_date=posted_date,
            description=None,  # TODO: retrieve dev-related keywords in description
            full_time=full_time,
        )

    def _filter_cards(self, card: Tag, full_time) -> bool:
        title = card.find("h3", class_="base-search-card__title")
        if not title:
            return False

        title_text = title.text.strip().lower()

        senior_keywords = {
            "senior",
            "sr",
            "staff",
            "principal",
            "lead",
            "manager",
            "head",
            "intermediate",
            "mid",
            "mid-level",
        }

        excluded_keywords = {
            "marketing",
            "sales",
            "business",
            "finance",
            "accounting",
            "hr",
            "human resources",
            "recruiter",
            "customer",
            "support",
            "service",
            "content",
            "design",
            "product manager",
            "project manager",
            "operations",
            "director",
            "commercial",
            "president",
            "consultant",
            "administrator",
            "head",
            "frontend",
        }

        included_keywords = {
            "backend",
            "cloud",
            "devops",
            "platform engineer",
            "infrastructure engineer",
            "systems",
            "site reliability",
            "software",
            "developer",
        }

        if full_time is False and not any(
            x in title_text for x in ("intern", "internship")
        ):
            return False

        # Must double check the job title.
        # It ensures that only expected jobs are added to the list.
        if (
            not any(level in title_text for level in senior_keywords)
            and not any(k in title_text for k in excluded_keywords)
            and any(k in title_text for k in included_keywords)
        ):
            return True

        return False
