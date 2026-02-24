import logging
import typing as t

import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Tag

from summer_internships_scraper.models.offers import JobOffer
from summer_internships_scraper.utils import HEADERS
from summer_internships_scraper.utils.exceptions import ParsingError, ScrapingError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LinkedInScraper:
    """Entry point for job offers scraper."""

    def __init__(self, host: str, logger: logging.Logger = logger) -> None:
        self.host = host
        self.logger = logger

    async def fetch_jobs(
        self,
        location: t.Tuple[str, str],
        keywords: str = "Summer 2026",  # TODO: make this dynamic by letting the user input whatever he wants  # noqa: E501
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
            if response.status != 200:
                raise ScrapingError(f"Error while requesting {url}")

            content = await response.text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")
            cards = soup.find_all("div", class_="job-search-card")

            jobs = []
            filtered, total = 0, len(cards)

        for card in cards:
            selected, full_time = self._filter_cards(card)
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
        title = card.find("h3", class_="base-search-card__title").text.strip()
        name = card.find("h4", class_="base-search-card__subtitle").text.strip()
        location = card.find("span", class_="job-search-card__location").text.strip()
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

    def _filter_cards(self, card: Tag) -> t.Tuple[bool, bool]:
        """
        Filter job cards for entry-level development roles based on the title.
        The title must:
        - contain at least one entry-level keyword (intern, junior, etc.)
        - contain at least one tech-related keyword
        - not contain excluded or non-dev keywords
        Returns `True` if the card should be kept, `False` otherwise.
        """
        included_keywords = {
            "backend",
            "cloud",
            "devops",
            "engineering",
            "platform",
            "site reliability",
            "software",
            "developer",
            "engineer",
        }

        senior_keywords = {
            "senior",
            "sr ",
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
        }

        title = card.find("h3", class_="base-search-card__title")
        if not title:
            return False, False

        title_text = title.text.strip().lower()

        entry_level_keywords = (
            "intern",
            "apprentice",
            "internship",
            "junior",
            "entry level",
            "graduate",
            "new grad",
            "early career",
        )

        if not any(p in title_text for p in entry_level_keywords):
            return False, False

        if not any(keyword in title_text for keyword in included_keywords):
            return False, False

        if any(role in title_text for role in excluded_keywords):
            return False, False

        if any(level in title_text for level in senior_keywords):
            return False, False

        # full_time == True when it's not explicitly an internship
        is_full_time = not any(x in title_text for x in ("intern", "internship"))
        return True, is_full_time
