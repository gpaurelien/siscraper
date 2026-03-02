import asyncio
import logging
import typing as t

import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Tag
from tenacity import retry, retry_if_exception, wait_exponential

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

    @retry(
        retry=retry_if_exception(lambda e: isinstance(e, RateLimitError)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
    )
    async def fetch_jobs(
        self,
        location: t.Tuple[str, str],
        keywords: str,  # TODO: make this dynamic by letting the user input whatever he wants  # noqa: E501
        full_time: bool,
        session: aiohttp.ClientSession = None,
    ) -> t.Optional[t.List[JobOffer]]:
        """
        Retrieves jobs, parses them, and returns a list containing offers.

        :param location: A tuple containing the location ID and country name used by LinkedIn  # noqa: E501
        :param keywords: Keywords needed for the job search
        """
        geo_id, country = location
        if not all(isinstance(x, str) for x in (geo_id, country, keywords)):
            raise TypeError("'location' and 'keywords' have to be str")

        self.logger.info(
            "Fetching jobs at %s with following pattern: '%s'" % (country, keywords)
        )

        keywords = self._format_keywords(keywords)
        url = f"{self.host}/?keywords={keywords}&geoId={geo_id}"

        async with session.get(
            url,
            headers=HEADERS,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status == 429:
                await asyncio.sleep(5)
                raise RateLimitError(
                    f"Got rate limited on {url}, will try again in a few moments"
                )

            if response.status != 200:
                raise ScrapingError(f"Error while requesting: {url}")

            content = await response.text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")
            cards = soup.find_all("div", class_="job-search-card")

            jobs = []
            filtered, total = 0, len(cards)

        for card in cards:
            selected = self._filter_cards(card, full_time)
            if not selected:
                filtered += 1
                continue

            try:
                job = self._parse_job_card(card, full_time)
                jobs.append(job)
            except Exception as err:
                raise ParsingError("Error while parsing job card") from err

        self.logger.info(
            f"Found {len(jobs)} dev jobs out of {total} total jobs "
            f"(filtered out {filtered})"
        )

        return jobs

    def _format_keywords(self, keywords: str) -> str:
        return keywords.replace(" ", "%20")

    def _parse_job_card(self, card: Tag, full_time: bool) -> JobOffer:
        """Extracts information from a job card"""
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
        """
        Filter card according to whether it is an internship or a full-time job
        """
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
        }

        included_keywords = {
            "backend",
            "cloud",
            "devops",
            "engineering",
            "platform engineer",
            "infrastructure engineer",
            "systems",
            "site reliability",
            "software",
            "developer",
        }

        # Must double check the job title.
        # It ensures that only expected jobs are added to the list.
        if (
            not any(level in title_text for level in senior_keywords)
            and not any(k in title_text for k in excluded_keywords)
            and any(k in title_text for k in included_keywords)
        ):
            return True

        return False
