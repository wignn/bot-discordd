import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ScrapedArticle:
    url: str
    title: str
    content: str
    author: str | None
    published_at: datetime | None
    image_url: str | None
    tags: list[str]
    content_hash: str
    meta: dict


class GenericScraper:

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=settings.scraper_timeout,
            headers={
                "User-Agent": settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            follow_redirects=True,
        )

    async def close(self):
        await self.client.aclose()

    async def scrape(self, url: str) -> ScrapedArticle | None:
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            author = self._extract_author(soup)
            published_at = self._extract_date(soup)
            image_url = self._extract_image(soup, url)
            tags = self._extract_tags(soup)
            
            if not title or not content:
                logger.warning("Could not extract title or content", url=url)
                return None

            hash_content = f"{title}|{content[:1000]}"
            content_hash = hashlib.sha256(hash_content.encode()).hexdigest()

            return ScrapedArticle(
                url=url,
                title=title,
                content=content,
                author=author,
                published_at=published_at,
                image_url=image_url,
                tags=tags,
                content_hash=content_hash,
                meta={
                    "word_count": len(content.split()),
                    "domain": urlparse(url).netloc,
                },
            )

        except httpx.HTTPError as e:
            logger.error("HTTP error scraping", url=url, error=str(e))
            return None
        except Exception as e:
            logger.error("Error scraping", url=url, error=str(e))
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        selectors = [
            "article h1",
            "h1.article-title",
            "h1.entry-title",
            "h1.post-title",
            ".article-header h1",
            "h1[itemprop='headline']",
            "meta[property='og:title']",
            "title",
        ]
        
        for selector in selectors:
            if selector.startswith("meta"):
                elem = soup.select_one(selector)
                if elem and elem.get("content"):
                    return elem["content"].strip()
            else:
                elem = soup.select_one(selector)
                if elem and elem.text.strip():
                    return elem.text.strip()
        
        return None

    def _extract_content(self, soup: BeautifulSoup) -> str:
        for elem in soup.select("script, style, nav, header, footer, aside, .ad, .advertisement, .social-share"):
            elem.decompose()

        selectors = [
            "article .content",
            "article .entry-content",
            "article .post-content",
            "article .article-body",
            ".article-content",
            ".story-body",
            "[itemprop='articleBody']",
            "article p",
        ]

        for selector in selectors:
            elems = soup.select(selector)
            if elems:
                if selector.endswith(" p"):
                    text = "\n\n".join(p.text.strip() for p in elems if p.text.strip())
                else:
                    text = elems[0].get_text(separator="\n\n", strip=True)
                
                if len(text) > 200:
                    return self._clean_content(text)

        paragraphs = soup.select("p")
        content = "\n\n".join(
            p.text.strip()
            for p in paragraphs
            if len(p.text.strip()) > 50
        )
        
        return self._clean_content(content)

    def _clean_content(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        
        patterns = [
            r"Subscribe to.*?newsletter",
            r"Sign up for.*?alerts",
            r"Follow us on.*?$",
            r"Read more:.*?$",
            r"Related:.*?$",
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
        
        return text.strip()

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        selectors = [
            "[rel='author']",
            ".author-name",
            ".byline",
            "[itemprop='author']",
            "meta[name='author']",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                if selector.startswith("meta"):
                    return elem.get("content")
                return elem.text.strip()
        
        return None

    def _extract_date(self, soup: BeautifulSoup) -> datetime | None:
        from dateutil import parser as date_parser
        
        selectors = [
            "time[datetime]",
            "[itemprop='datePublished']",
            "meta[property='article:published_time']",
            ".publish-date",
            ".post-date",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                date_str = elem.get("datetime") or elem.get("content") or elem.text
                if date_str:
                    try:
                        return date_parser.parse(date_str)
                    except Exception:
                        continue
        
        return None

    def _extract_image(self, soup: BeautifulSoup, base_url: str) -> str | None:
        selectors = [
            "meta[property='og:image']",
            "article img",
            ".article-image img",
            ".featured-image img",
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                img_url = elem.get("content") or elem.get("src")
                if img_url:
                    return urljoin(base_url, img_url)
        
        return None

    def _extract_tags(self, soup: BeautifulSoup) -> list[str]:
        tags = []
        
        meta = soup.select_one("meta[name='keywords']")
        if meta and meta.get("content"):
            tags.extend(k.strip() for k in meta["content"].split(","))
        
        for elem in soup.select(".tags a, .post-tags a, [rel='tag']"):
            if elem.text.strip():
                tags.append(elem.text.strip())
        
        return list(set(tags))[:10]

    async def scrape_batch(
        self,
        urls: list[str],
        delay: float = 1.0,
    ) -> list[ScrapedArticle]:
        results = []
        
        for url in urls:
            article = await self.scrape(url)
            if article:
                results.append(article)
            
            if delay > 0:
                await asyncio.sleep(delay)
        
        return results
