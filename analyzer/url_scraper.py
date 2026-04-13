# import logging
# import requests
# from urllib.parse import urljoin, urlparse
# import re
# from typing import Optional, Dict, List

# logger = logging.getLogger(__name__)


# class URLScraper:
#     def __init__(self, timeout: int = 30):
#         self.timeout = timeout
#         self.headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#             'Accept-Language': 'en-US,en;q=0.5',
#             'Accept-Encoding': 'gzip, deflate',
#             'Connection': 'keep-alive',
#             'Upgrade-Insecure-Requests': '1',
#         }

#     # ------------------------------------------------------
#     # MAIN SCRAPER
#     # ------------------------------------------------------
#     def scrape(self, url: str) -> Dict[str, any]:
#         from bs4 import BeautifulSoup  # ✅ LAZY IMPORT FIX (IMPORTANT)

#         try:
#             if not self._is_valid_url(url):
#                 raise ValueError(f"Invalid URL format: {url}")

#             # Special handling for sources
#             if 'scholar.google' in url.lower():
#                 return self._handle_google_scholar(url)

#             if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
#                 return self._handle_youtube(url)

#             if 'researchgate.net' in url.lower():
#                 return self._handle_researchgate(url)

#             response = requests.get(
#                 url,
#                 headers=self.headers,
#                 timeout=self.timeout,
#                 allow_redirects=True
#             )
#             response.raise_for_status()

#             content_type = response.headers.get('Content-Type', '')

#             supported_types = [
#                 'text/html',
#                 'application/xhtml',
#                 'application/pdf',
#                 'application/json',
#                 'text/plain'
#             ]

#             is_supported = any(stype in content_type for stype in supported_types)

#             if not is_supported and len(response.content) < 1000:
#                 return {
#                     'success': False,
#                     'error': 'Unsupported source. This URL does not contain readable content.',
#                     'url': url
#                 }

#             # ✅ FIXED: safe parser (Render friendly)
#             soup = BeautifulSoup(response.content, 'html.parser')

#             for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
#                 tag.decompose()

#             title = self._extract_title(soup)
#             main_content = self._extract_main_content(soup)
#             text_content = self._clean_text(main_content)

#             if len(text_content) < 100:
#                 text_content = self._fallback_extraction(soup)

#             return {
#                 'success': True,
#                 'url': url,
#                 'title': title,
#                 'content': text_content,
#                 'raw_html': str(soup),
#                 'links': self._extract_links(soup, url),
#                 'metadata': self._extract_metadata(soup),
#             }

#         except requests.exceptions.Timeout:
#             return {'success': False, 'error': 'Request timed out.', 'url': url}

#         except requests.exceptions.ConnectionError:
#             return {'success': False, 'error': 'Connection error.', 'url': url}

#         except requests.exceptions.HTTPError as e:
#             code = e.response.status_code
#             return {'success': False, 'error': f'HTTP Error {code}', 'url': url}

#         except Exception as e:
#             logger.error(f"Error scraping {url}: {e}")
#             return {'success': False, 'error': str(e), 'url': url}

#     # ------------------------------------------------------
#     # HELPERS
#     # ------------------------------------------------------
#     def _is_valid_url(self, url: str) -> bool:
#         try:
#             result = urlparse(url)
#             return all([result.scheme in ['http', 'https'], result.netloc])
#         except:
#             return False

#     def _extract_title(self, soup) -> str:
#         if soup.title and soup.title.string:
#             return soup.title.string.strip()

#         h1 = soup.find('h1')
#         if h1:
#             return h1.get_text().strip()

#         og_title = soup.find('meta', property='og:title')
#         if og_title and og_title.get('content'):
#             return og_title['content'].strip()

#         return ""

#     def _extract_main_content(self, soup) -> str:
#         article = soup.find('article')
#         if article:
#             return article.get_text(separator='\n\n', strip=True)

#         main = soup.find('main')
#         if main:
#             return main.get_text(separator='\n\n', strip=True)

#         content_div = soup.find('div', class_=re.compile(
#             r'content|article|post|entry|main|text|body', re.I
#         ))

#         if content_div:
#             return content_div.get_text(separator='\n\n', strip=True)

#         return soup.get_text(separator='\n\n', strip=True)

#     def _clean_text(self, text: str) -> str:
#         text = re.sub(r'\s+', ' ', text)
#         text = re.sub(r'\n\s*\n', '\n\n', text)
#         text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', text)
#         return text.strip()

#     def _fallback_extraction(self, soup) -> str:
#         paragraphs = soup.find_all('p')
#         text_parts = []

#         for p in paragraphs:
#             text = p.get_text().strip()
#             if len(text) > 50:
#                 text_parts.append(text)

#         return '\n\n'.join(text_parts) if text_parts else soup.get_text()

#     def _extract_links(self, soup, base_url: str) -> List[str]:
#         links = []
#         seen = set()

#         for a_tag in soup.find_all('a', href=True):
#             href = a_tag['href']

#             if href.startswith(('javascript:', 'mailto:', 'tel:')):
#                 continue

#             full_url = urljoin(base_url, href)
#             parsed = urlparse(full_url)

#             clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
#             if parsed.query:
#                 clean_url += f"?{parsed.query}"

#             if clean_url not in seen:
#                 links.append(clean_url)
#                 seen.add(clean_url)

#         return links[:50]

#     def _extract_metadata(self, soup) -> Dict[str, str]:
#         metadata = {}

#         meta_tags = {
#             'description': ['description', 'og:description'],
#             'author': ['author', 'article:author'],
#             'published_time': ['article:published_time'],
#             'keywords': ['keywords'],
#         }

#         for key, names in meta_tags.items():
#             for name in names:
#                 tag = soup.find('meta', attrs={'name': name}) or soup.find(
#                     'meta', attrs={'property': name}
#                 )
#                 if tag and tag.get('content'):
#                     metadata[key] = tag['content'].strip()
#                     break

#         return metadata

#     # ------------------------------------------------------
#     # SPECIAL HANDLERS (UNCHANGED LOGIC)
#     # ------------------------------------------------------
#     def _handle_google_scholar(self, url: str) -> Dict[str, any]:
#         try:
#             scholar_headers = self.headers.copy()
#             scholar_headers['Referer'] = 'https://www.google.com/'

#             response = requests.get(url, headers=scholar_headers, timeout=self.timeout)
#             response.raise_for_status()

#             from bs4 import BeautifulSoup
#             soup = BeautifulSoup(response.content, 'html.parser')

#             results = []
#             for result in soup.find_all('div', class_='gs_ri'):
#                 text = result.get_text()
#                 if len(text) > 20:
#                     results.append(text)

#             content = '\n\n'.join(results[:10]) if results else soup.get_text()

#             return {
#                 'success': True,
#                 'url': url,
#                 'title': 'Google Scholar Results',
#                 'content': content[:5000],
#                 'metadata': {},
#                 'links': [],
#             }

#         except Exception as e:
#             return {'success': False, 'error': str(e), 'url': url}

#     def _handle_researchgate(self, url: str) -> Dict[str, any]:
#         try:
#             response = requests.get(url, headers=self.headers, timeout=self.timeout)
#             response.raise_for_status()

#             from bs4 import BeautifulSoup
#             soup = BeautifulSoup(response.content, 'html.parser')

#             title = self._extract_title(soup)
#             content = soup.get_text(separator='\n', strip=True)[:5000]

#             return {
#                 'success': True,
#                 'url': url,
#                 'title': title,
#                 'content': content,
#                 'metadata': self._extract_metadata(soup),
#                 'links': [],
#             }

#         except Exception as e:
#             return {'success': False, 'error': str(e), 'url': url}

#     def _handle_youtube(self, url: str) -> Dict[str, any]:
#         try:
#             import yt_dlp

#             ydl_opts = {'quiet': True}

#             with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#                 info = ydl.extract_info(url, download=False)

#             return {
#                 'success': True,
#                 'url': url,
#                 'title': info.get('title', ''),
#                 'content': info.get('description', ''),
#                 'metadata': info,
#                 'links': [url],
#             }

#         except Exception as e:
#             return {'success': False, 'error': str(e), 'url': url}

# class URLScraper:
#     def __init__(self, timeout: int = 30):
#         self.timeout = timeout
#         self.headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
#             'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#             'Accept-Language': 'en-US,en;q=0.5',
#             'Accept-Encoding': 'gzip, deflate',
#             'Connection': 'keep-alive',
#             'Upgrade-Insecure-Requests': '1',
#         }

#     # ------------------------------------------------------
#     # MAIN SCRAPER
#     # ------------------------------------------------------
#     def scrape(self, url: str) -> Dict[str, any]:
#         from bs4 import BeautifulSoup  # ✅ LAZY IMPORT FIX (IMPORTANT)

#         try:
#             if not self._is_valid_url(url):
#                 raise ValueError(f"Invalid URL format: {url}")

#             # Special handling for sources
#             if 'scholar.google' in url.lower():
#                 return self._handle_google_scholar(url)

#             if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
#                 return self._handle_youtube(url)

#             if 'researchgate.net' in url.lower():
#                 return self._handle_researchgate(url)

#             response = requests.get(
#                 url,
#                 headers=self.headers,
#                 timeout=self.timeout,
#                 allow_redirects=True
#             )
#             response.raise_for_status()

#             content_type = response.headers.get('Content-Type', '')

#             supported_types = [
#                 'text/html',
#                 'application/xhtml',
#                 'application/pdf',
#                 'application/json',
#                 'text/plain'
#             ]

#             is_supported = any(stype in content_type for stype in supported_types)

#             if not is_supported and len(response.content) < 1000:
#                 return {
#                     'success': False,
#                     'error': 'Unsupported source. This URL does not contain readable content.',
#                     'url': url
#                 }

#             # ✅ FIXED: safe parser (Render friendly)
#             soup = BeautifulSoup(response.content, 'html.parser')

#             for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
#                 tag.decompose()

#             title = self._extract_title(soup)
#             main_content = self._extract_main_content(soup)
#             text_content = self._clean_text(main_content)

#             if len(text_content) < 100:
#                 text_content = self._fallback_extraction(soup)

#             return {
#                 'success': True,
#                 'url': url,
#                 'title': title,
#                 'content': text_content,
#                 'raw_html': str(soup),
#                 'links': self._extract_links(soup, url),
#                 'metadata': self._extract_metadata(soup),
#             }

#         except requests.exceptions.Timeout:
#             return {'success': False, 'error': 'Request timed out.', 'url': url}

#         except requests.exceptions.ConnectionError:
#             return {'success': False, 'error': 'Connection error.', 'url': url}

#         except requests.exceptions.HTTPError as e:
#             code = e.response.status_code
#             return {'success': False, 'error': f'HTTP Error {code}', 'url': url}

#         except Exception as e:
#             logger.error(f"Error scraping {url}: {e}")
#             return {'success': False, 'error': str(e), 'url': url}
#  url_scraper = URLScraper()   # 👈 REQUIRED

# # ❌ REMOVED GLOBAL INSTANCE (IMPORTANT FIX)
# # url_scraper = URLScraper() this is full page code?

import logging
import requests
from urllib.parse import urljoin, urlparse
import re
from typing import Dict, List

logger = logging.getLogger(__name__)


class URLScraper:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    # ---------------- MAIN SCRAPER ----------------
    def scrape(self, url: str) -> Dict[str, any]:
        from bs4 import BeautifulSoup

        try:
            if not self._is_valid_url(url):
                return {'success': False, 'error': 'Invalid URL format', 'url': url}

            if 'scholar.google' in url.lower():
                return self._handle_google_scholar(url)

            if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                return self._handle_youtube(url)

            if 'researchgate.net' in url.lower():
                return self._handle_researchgate(url)

            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()

            content_type = response.headers.get('Content-Type', '')

            supported_types = [
                'text/html',
                'application/xhtml',
                'application/pdf',
                'application/json',
                'text/plain'
            ]

            is_supported = any(stype in content_type for stype in supported_types)

            if not is_supported and len(response.content) < 1000:
                return {
                    'success': False,
                    'error': 'Unsupported or unreadable content',
                    'url': url
                }

            soup = BeautifulSoup(response.content, 'html.parser')

            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            title = self._extract_title(soup)
            main_content = self._extract_main_content(soup)
            text_content = self._clean_text(main_content)

            if len(text_content) < 100:
                text_content = self._fallback_extraction(soup)

            return {
                'success': True,
                'url': url,
                'title': title,
                'content': text_content,
                'raw_html': str(soup),
                'links': self._extract_links(soup, url),
                'metadata': self._extract_metadata(soup),
            }

        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timed out', 'url': url}

        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Connection error', 'url': url}

        except requests.exceptions.HTTPError as e:
            return {'success': False, 'error': f'HTTP Error {e.response.status_code}', 'url': url}

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {'success': False, 'error': str(e), 'url': url}

    # ---------------- HELPERS ----------------
    def _is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except:
            return False

    def _extract_title(self, soup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        og = soup.find('meta', property='og:title')
        if og and og.get('content'):
            return og['content'].strip()

        return ""

    def _extract_main_content(self, soup) -> str:
        article = soup.find('article')
        if article:
            return article.get_text(separator='\n\n', strip=True)

        main = soup.find('main')
        if main:
            return main.get_text(separator='\n\n', strip=True)

        div = soup.find('div', class_=re.compile(r'content|article|post|main|text', re.I))
        if div:
            return div.get_text(separator='\n\n', strip=True)

        return soup.get_text(separator='\n\n', strip=True)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        return text.strip()

    def _fallback_extraction(self, soup) -> str:
        paragraphs = soup.find_all('p')
        text = [p.get_text().strip() for p in paragraphs if len(p.get_text()) > 50]
        return '\n\n'.join(text) if text else soup.get_text()

    def _extract_links(self, soup, base_url: str) -> List[str]:
        links = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            if href.startswith(('javascript:', 'mailto:', 'tel:')):
                continue

            full = urljoin(base_url, href)
            links.add(full)

        return list(links)[:50]

    def _extract_metadata(self, soup) -> Dict[str, str]:
        data = {}

        tags = {
            'description': ['description', 'og:description'],
            'author': ['author'],
            'keywords': ['keywords']
        }

        for key, names in tags.items():
            for name in names:
                meta = soup.find('meta', attrs={'name': name}) or soup.find('meta', property=name)
                if meta and meta.get('content'):
                    data[key] = meta['content']
                    break

        return data

    # ---------------- SPECIAL HANDLERS ----------------
    def _handle_google_scholar(self, url: str):
        return {'success': False, 'error': 'Google Scholar blocked scraping', 'url': url}

    def _handle_researchgate(self, url: str):
        return {'success': False, 'error': 'ResearchGate limited access', 'url': url}

    def _handle_youtube(self, url: str):
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)

            return {
                'success': True,
                'url': url,
                'title': info.get('title', ''),
                'content': info.get('description', ''),
                'metadata': info
            }

        except Exception as e:
            return {'success': False, 'error': str(e), 'url': url}


# ✅ IMPORTANT: SINGLE GLOBAL INSTANCE (BOTTOM OF FILE ONLY)
url_scraper = URLScraper()