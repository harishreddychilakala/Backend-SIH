"""
BIS SmartAI — Official BIS Government Portal Web Searcher
Fetches live information from official BIS government websites (bis.gov.in, manakonline.in, services.bis.gov.in)
when local indexed RAG document chunks do not contain the answer.
"""
import logging
import urllib.parse
import re
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 (BIS-SmartAI-Assistant/1.0)"
)


class BISWebSearcher:
    """
    Searches official Bureau of Indian Standards government domains
    (bis.gov.in, manakonline.in, services.bis.gov.in, standards.bis.gov.in)
    for live regulatory information, QCO notifications, and standards.
    """

    @staticmethod
    def search_bis_portal(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search official BIS portals for the query.
        Returns a list of search result dicts with title, snippet, url, domain, source_type.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # Target official BIS and Ministry domains
        search_term = f"site:bis.gov.in OR site:manakonline.in {clean_query}"
        
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        results: List[Dict[str, Any]] = []

        try:
            with httpx.Client(timeout=8.0, follow_redirects=True) as client:
                resp = client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": search_term},
                    headers=headers,
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for r in soup.select(".result"):
                        title_elem = r.select_one(".result__title")
                        snippet_elem = r.select_one(".result__snippet")
                        
                        if title_elem and snippet_elem:
                            title = title_elem.get_text(strip=True)
                            snippet = snippet_elem.get_text(strip=True)
                            link = title_elem.find("a")
                            raw_href = link["href"] if link and "href" in link.attrs else ""

                            # Extract destination URL from DuckDuckGo redirect wrapper
                            actual_url = raw_href
                            if "uddg=" in raw_href:
                                match = re.search(r'uddg=([^&]+)', raw_href)
                                if match:
                                    actual_url = urllib.parse.unquote(match.group(1))

                            # Clean up title if it repeats
                            title = title.replace("\n", " ").strip()

                            # Determine primary government domain
                            domain = "bis.gov.in"
                            if "manakonline.in" in actual_url:
                                domain = "manakonline.in"
                            elif "standards.bis.gov.in" in actual_url:
                                domain = "standards.bis.gov.in"
                            elif "services.bis.gov.in" in actual_url:
                                domain = "services.bis.gov.in"

                            results.append({
                                "title": title,
                                "snippet": snippet,
                                "url": actual_url,
                                "domain": domain,
                                "source_type": "Official BIS Government Portal",
                                "relevance": f"Live official information from {domain}",
                            })

                            if len(results) >= max_results:
                                break

            logger.info(f"🌐 Live BIS Government search returned {len(results)} sources for: '{query[:60]}...'")
        except Exception as e:
            logger.warning(f"Live BIS web search error: {e}")

        # Fallback default official references if web search is blocked
        if not results:
            results = [
                {
                    "title": "Bureau of Indian Standards — Official Portal",
                    "snippet": f"National Standards Body of India portal containing Indian Standards, QCOs, and certification schemes related to '{query}'.",
                    "url": f"https://www.bis.gov.in/?s={urllib.parse.quote(clean_query)}",
                    "domain": "bis.gov.in",
                    "source_type": "Official BIS Government Portal",
                    "relevance": "Official National Standards Body of India Portal",
                },
                {
                    "title": "BIS Manakonline — Conformity Assessment Portal",
                    "snippet": "Online portal for BIS Product Certification Scheme (Scheme-I / ISI Mark), laboratory recognition, and application processing.",
                    "url": "https://www.manakonline.in/MANAK/knowYourStandards",
                    "domain": "manakonline.in",
                    "source_type": "Official BIS Government Portal",
                    "relevance": "Official BIS Certification & Standards Database",
                }
            ]

        return results


bis_web_searcher = BISWebSearcher()
