#!/usr/bin/env python3
"""
Full SEO Checker Script
Crawls a website and performs comprehensive SEO checks including:
- Dead links
- OG images
- Meta titles
- Meta descriptions
- Sitemap validation
- Other on-page SEO elements
- Performance metrics (LCP, TBT, CLS, TTFB, FCP)
"""

import os
import sys
import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import defaultdict
import time
import xml.etree.ElementTree as ET

# Configuration
WEBSITE_URL = os.environ.get('WEBSITE_URL', '')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY', '')
MAX_PAGES = 100  # Limit to prevent infinite crawling
REQUEST_TIMEOUT = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
PERFORMANCE_TIMEOUT = 60000  # 60 seconds for page load
NETWORK_IDLE_DELAY = 2000  # 2 seconds to wait after network idle
OBSERVER_TIMEOUT = 500  # Timeout for Performance Observer collection
MAX_URLS_IN_REPORT = 20  # Maximum number of URLs to display in GitHub issue
MAX_URLS_IN_CONSOLE = 10  # Maximum number of URLs to display in console output
# Domains that return 403 due to requiring login but should not be considered broken
TWITTER_X_DOMAINS = ['twitter.com', 'www.twitter.com', 'x.com', 'www.x.com']

# Sitemap namespaces
SITEMAP_NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'
}


class FullSEOChecker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.visited_pages = set()
        self.seo_issues = defaultdict(lambda: {
            'url': '',
            'missing_og_image': False,
            'missing_title': False,
            'missing_description': False,
            'missing_canonical': False,
            'missing_lang': False,
            'title_too_short': False,
            'title_too_long': False,
            'description_too_short': False,
            'description_too_long': False,
            'og_image_url': None,
            'title': None,
            'description': None,
            'canonical': None,
            'lang': None
        })
        self.broken_links = defaultdict(list)
        self.checked_links = {}
        self.sitemap_urls = []
        self.processed_sitemaps = set()
        self.urls_in_sitemap_not_crawled = []
        self.urls_crawled_not_in_sitemap = []
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        # Performance metrics
        self.performance_metrics = {}
        self.performance_grade = 'A'
        self.performance_score = 100
        self.performance_issues = []
    
    def normalize_url(self, url):
        """Normalize URL for comparison"""
        # Remove fragment
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def is_same_domain(self, url):
        """Check if URL belongs to the same domain"""
        return urlparse(url).netloc == self.domain
    
    def check_seo_elements(self, url, soup):
        """Check all SEO elements on a page"""
        issues = self.seo_issues[url]
        issues['url'] = url
        
        # Check OG image
        og_image = soup.find('meta', property='og:image')
        if not og_image or not og_image.get('content'):
            issues['missing_og_image'] = True
        else:
            issues['og_image_url'] = og_image.get('content')
        
        # Check title tag
        title_tag = soup.find('title')
        if not title_tag or not title_tag.string or not title_tag.string.strip():
            issues['missing_title'] = True
        else:
            title_text = title_tag.string.strip()
            issues['title'] = title_text
            if len(title_text) < 30:
                issues['title_too_short'] = True
            elif len(title_text) > 60:
                issues['title_too_long'] = True
        
        # Check meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc or not meta_desc.get('content'):
            issues['missing_description'] = True
        else:
            desc_text = meta_desc.get('content').strip()
            issues['description'] = desc_text
            if len(desc_text) < 50:
                issues['description_too_short'] = True
            elif len(desc_text) > 160:
                issues['description_too_long'] = True
        
        # Check canonical link
        canonical = soup.find('link', rel='canonical')
        if not canonical or not canonical.get('href'):
            issues['missing_canonical'] = True
        else:
            issues['canonical'] = canonical.get('href')
        
        # Check lang attribute in html tag
        html_tag = soup.find('html')
        if not html_tag or not html_tag.get('lang'):
            issues['missing_lang'] = True
        else:
            issues['lang'] = html_tag.get('lang')
    
    def should_skip_link(self, url):
        """Check if a link should be skipped from checking"""
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Skip all CDN-CGI links (Cloudflare features that only work in real browsers)
        if path == '/cdn-cgi' or path.startswith('/cdn-cgi/'):
            return True
        
        return False
    
    def should_skip_url(self, url):
        """Check if a URL should be skipped from checking"""
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        # Skip CDN-CGI paths
        if path.startswith('/cdn-cgi/'):
            return True
        
        return False
    
    def check_link(self, url):
        """Check if a link is broken"""
        if url in self.checked_links:
            return self.checked_links[url]
        
        # Skip links that should not be checked
        if self.should_skip_link(url):
            self.checked_links[url] = (200, False)
            return 200, False
        
        try:
            # Use HEAD request first for efficiency
            response = self.session.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            status_code = response.status_code
            
            # Some servers don't support HEAD, fallback to GET only for 405
            if status_code == 405:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                status_code = response.status_code
            
            # Check if this is a Twitter/X.com link with 403 status
            # These sites return 403 because they require login, but aren't actually broken
            parsed_url = urlparse(url)
            is_twitter_or_x = parsed_url.netloc in TWITTER_X_DOMAINS
            
            is_broken = status_code >= 400
            # Don't consider Twitter/X.com links with 403 as broken
            if is_twitter_or_x and status_code == 403:
                is_broken = False
            
            self.checked_links[url] = (status_code, is_broken)
            
            # Add small delay to be respectful
            time.sleep(0.1)
            
            return status_code, is_broken
        except requests.exceptions.RequestException as e:
            print(f"  Error checking link {url}: {e}")
            self.checked_links[url] = (0, True)
            return 0, True
    
    def get_links_and_check_seo(self, url):
        """Extract all links from a page and check SEO elements"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check SEO elements
            self.check_seo_elements(url, soup)
            
            # Extract links
            links = []
            for tag in soup.find_all('a', href=True):
                href = tag['href']
                absolute_url = urljoin(url, href)
                links.append(absolute_url)
            
            return links, response.status_code
        except Exception as e:
            print(f"  Error fetching {url}: {e}")
            return [], None
    
    def get_sitemap_url(self):
        """Get the sitemap URL (try sitemap.xml)"""
        return f"{self.base_url}/sitemap.xml"
    
    def fetch_sitemap(self, sitemap_url):
        """Fetch a sitemap file"""
        try:
            print(f"  Fetching sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"  Warning: Could not fetch sitemap {sitemap_url}: {e}")
            return None
    
    def parse_sitemap_index(self, content):
        """Parse a sitemap index file and return nested sitemap URLs"""
        try:
            root = ET.fromstring(content)
            sitemap_urls = []
            
            # Check if this is a sitemap index
            for sitemap in root.findall('sm:sitemap', SITEMAP_NS):
                loc = sitemap.find('sm:loc', SITEMAP_NS)
                if loc is not None and loc.text:
                    sitemap_urls.append(loc.text.strip())
            
            return sitemap_urls
        except Exception as e:
            print(f"  Error parsing sitemap index: {e}")
            return []
    
    def parse_sitemap_urls(self, content):
        """Parse a sitemap file and return URLs"""
        try:
            root = ET.fromstring(content)
            urls = []
            
            # Parse regular sitemap URLs
            for url_elem in root.findall('sm:url', SITEMAP_NS):
                loc = url_elem.find('sm:loc', SITEMAP_NS)
                if loc is not None and loc.text:
                    url = loc.text.strip()
                    # Skip URLs that should not be checked
                    if not self.should_skip_url(url):
                        urls.append(url)
                    else:
                        print(f"  Skipping CDN-CGI URL: {url}")
            
            return urls
        except Exception as e:
            print(f"  Error parsing sitemap URLs: {e}")
            return []
    
    def process_sitemap(self, sitemap_url):
        """Process a sitemap (handles both index and regular sitemaps)"""
        if sitemap_url in self.processed_sitemaps:
            return
        
        self.processed_sitemaps.add(sitemap_url)
        content = self.fetch_sitemap(sitemap_url)
        
        if content is None:
            return
        
        # Try to parse as sitemap index first
        nested_sitemaps = self.parse_sitemap_index(content)
        
        if nested_sitemaps:
            print(f"  Found {len(nested_sitemaps)} nested sitemap(s)")
            for nested_sitemap_url in nested_sitemaps:
                self.process_sitemap(nested_sitemap_url)
        else:
            # Parse as regular sitemap
            urls = self.parse_sitemap_urls(content)
            print(f"  Found {len(urls)} URL(s) in sitemap")
            self.sitemap_urls.extend(urls)
    
    def is_sitemap_file(self, url):
        """Check if a URL is a sitemap file"""
        parsed = urlparse(url)
        path = parsed.path.lower()
        # Get the filename using os.path.basename
        filename = os.path.basename(path)
        # Check if it's an XML file that starts with 'sitemap'
        return filename.endswith('.xml') and filename.startswith('sitemap')
    
    def check_sitemap(self):
        """Check sitemap and compare with crawled pages"""
        print("\n" + "="*60)
        print("CHECKING SITEMAP")
        print("="*60)
        
        sitemap_url = self.get_sitemap_url()
        self.process_sitemap(sitemap_url)
        
        if not self.sitemap_urls:
            print("Warning: No sitemap found or sitemap is empty")
            return
        
        print(f"Total URLs found in sitemap: {len(self.sitemap_urls)}")
        
        # Filter out sitemap files from comparison (child sitemaps, sitemap indexes, etc.)
        # Do this once to avoid redundant processing
        content_urls = []
        sitemap_files_filtered = []
        for url in self.sitemap_urls:
            if self.is_sitemap_file(url):
                sitemap_files_filtered.append(url)
            else:
                content_urls.append(url)
        
        if sitemap_files_filtered:
            print(f"Filtering out {len(sitemap_files_filtered)} sitemap file(s) from comparison")
        
        # Normalize content URLs for comparison
        normalized_sitemap_urls = set(self.normalize_url(url) for url in content_urls)
        
        # Find URLs in sitemap but not crawled
        self.urls_in_sitemap_not_crawled = list(normalized_sitemap_urls - self.visited_pages)
        
        # Find URLs crawled but not in sitemap
        self.urls_crawled_not_in_sitemap = list(self.visited_pages - normalized_sitemap_urls)
        
        print(f"URLs in sitemap not crawled: {len(self.urls_in_sitemap_not_crawled)}")
        print(f"URLs crawled not in sitemap: {len(self.urls_crawled_not_in_sitemap)}")
    
    def crawl_website(self):
        """Crawl the website and perform full SEO check"""
        pages_to_visit = [self.base_url]
        
        while pages_to_visit and len(self.visited_pages) < MAX_PAGES:
            current_url = pages_to_visit.pop(0)
            normalized_url = self.normalize_url(current_url)
            
            if normalized_url in self.visited_pages:
                continue
            
            print(f"Checking: {current_url}")
            self.visited_pages.add(normalized_url)
            
            # Get links and check SEO elements
            links, status = self.get_links_and_check_seo(current_url)
            if status is None:
                continue
            
            # Check all links on the page
            for link in links:
                status_code, is_broken = self.check_link(link)
                
                if is_broken:
                    self.broken_links[current_url].append({
                        'url': link,
                        'status_code': status_code
                    })
                    print(f"  ✗ Broken link: {link} (Status: {status_code})")
                
                # Add same-domain pages to crawl queue
                if self.is_same_domain(link):
                    normalized_link = self.normalize_url(link)
                    if normalized_link not in self.visited_pages:
                        pages_to_visit.append(link)
    
    def collect_performance_metrics(self):
        """Collect performance metrics for the homepage using Playwright"""
        from playwright.sync_api import sync_playwright
        
        print(f"\nCollecting performance metrics for: {self.base_url}")
        
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # Load the page
            page.goto(self.base_url, wait_until='networkidle', timeout=PERFORMANCE_TIMEOUT)
            page.wait_for_timeout(NETWORK_IDLE_DELAY)
            
            # Get navigation timing data
            navigation_timing = page.evaluate('''() => {
                const timing = performance.getEntriesByType('navigation')[0];
                if (!timing) return null;
                return {
                    ttfb: timing.responseStart - timing.requestStart,
                    domContentLoaded: timing.domContentLoadedEventEnd,
                    loadEventEnd: timing.loadEventEnd
                };
            }''')
            
            # Get paint timing (FCP)
            paint_timing = page.evaluate('''() => {
                const entries = performance.getEntriesByType('paint');
                const fcp = entries.find(e => e.name === 'first-contentful-paint');
                return {
                    firstContentfulPaint: fcp ? fcp.startTime : null
                };
            }''')
            
            # Get LCP using PerformanceObserver
            lcp = page.evaluate(f'''() => {{
                return new Promise((resolve) => {{
                    let lcpValue = 0;
                    const observer = new PerformanceObserver((list) => {{
                        const entries = list.getEntries();
                        for (const entry of entries) {{
                            if (entry.startTime > lcpValue) {{
                                lcpValue = entry.startTime;
                            }}
                        }}
                    }});
                    try {{
                        observer.observe({{ type: 'largest-contentful-paint', buffered: true }});
                    }} catch {{}}
                    setTimeout(() => {{
                        observer.disconnect();
                        resolve(lcpValue);
                    }}, {OBSERVER_TIMEOUT});
                }});
            }}''')
            
            # Get CLS using PerformanceObserver
            cls = page.evaluate(f'''() => {{
                return new Promise((resolve) => {{
                    let clsValue = 0;
                    const observer = new PerformanceObserver((list) => {{
                        for (const entry of list.getEntries()) {{
                            if (!entry.hadRecentInput) {{
                                clsValue += entry.value;
                            }}
                        }}
                    }});
                    try {{
                        observer.observe({{ type: 'layout-shift', buffered: true }});
                    }} catch {{}}
                    setTimeout(() => {{
                        observer.disconnect();
                        resolve(clsValue);
                    }}, {OBSERVER_TIMEOUT});
                }});
            }}''')
            
            # Get Long Tasks for TBT calculation
            long_tasks = page.evaluate(f'''() => {{
                return new Promise((resolve) => {{
                    const tasks = [];
                    const observer = new PerformanceObserver((list) => {{
                        for (const entry of list.getEntries()) {{
                            tasks.push({{
                                duration: entry.duration
                            }});
                        }}
                    }});
                    try {{
                        observer.observe({{ type: 'longtask', buffered: true }});
                    }} catch {{}}
                    setTimeout(() => {{
                        observer.disconnect();
                        resolve(tasks);
                    }}, {OBSERVER_TIMEOUT});
                }});
            }}''')
            
            # Calculate TBT
            tbt = 0
            for task in long_tasks:
                if task['duration'] > 50:
                    tbt += task['duration'] - 50
            
            # Store metrics
            self.performance_metrics = {
                'ttfb': int(navigation_timing.get('ttfb', 0)) if navigation_timing else 0,
                'fcp': int(paint_timing.get('firstContentfulPaint', 0) or 0),
                'lcp': int(lcp),
                'cls': round(cls, 3),
                'tbt': int(tbt),
                'dom_content_loaded': int(navigation_timing.get('domContentLoaded', 0)) if navigation_timing else 0,
                'load_event_end': int(navigation_timing.get('loadEventEnd', 0)) if navigation_timing else 0
            }
            
            # Calculate performance grade
            self._calculate_performance_grade()
            
            # Close browser with robust error handling
            try:
                page.close()
            except Exception as e:
                print(f"Warning: Failed to close page: {e}")
            try:
                context.close()
            except Exception as e:
                print(f"Warning: Failed to close context: {e}")
            try:
                browser.close()
            except Exception as e:
                print(f"Warning: Failed to close browser: {e}")
            try:
                playwright.stop()
            except Exception as e:
                print(f"Warning: Failed to stop Playwright: {e}")
            
            print(f"Performance metrics collected - Grade: {self.performance_grade} (Score: {self.performance_score}/100)")
            
        except Exception as e:
            print(f"Error collecting performance metrics: {e}")
            self.performance_metrics = {}
            # Attempt cleanup of any initialized resources
            try:
                if 'page' in dir() and page:
                    page.close()
            except Exception:
                pass
            try:
                if 'context' in dir() and context:
                    context.close()
            except Exception:
                pass
            try:
                if 'browser' in dir() and browser:
                    browser.close()
            except Exception:
                pass
            try:
                if 'playwright' in dir() and playwright:
                    playwright.stop()
            except Exception:
                pass
    
    def _calculate_performance_grade(self):
        """Calculate performance grade based on Core Web Vitals"""
        score = 100
        
        # LCP scoring (Good < 2500ms, Needs Improvement < 4000ms, Poor >= 4000ms)
        if self.performance_metrics.get('lcp', 0) > 4000:
            score -= 25
            self.performance_issues.append({
                'severity': 'high',
                'title': 'Poor Largest Contentful Paint (LCP)',
                'description': f"LCP is {self.performance_metrics['lcp']}ms (should be < 2500ms)"
            })
        elif self.performance_metrics.get('lcp', 0) > 2500:
            score -= 10
            self.performance_issues.append({
                'severity': 'medium',
                'title': 'Needs Improvement: LCP',
                'description': f"LCP is {self.performance_metrics['lcp']}ms (should be < 2500ms)"
            })
        
        # TBT scoring (Good < 200ms, Needs Improvement < 600ms, Poor >= 600ms)
        if self.performance_metrics.get('tbt', 0) > 600:
            score -= 25
            self.performance_issues.append({
                'severity': 'high',
                'title': 'Poor Total Blocking Time (TBT)',
                'description': f"TBT is {self.performance_metrics['tbt']}ms (should be < 200ms)"
            })
        elif self.performance_metrics.get('tbt', 0) > 200:
            score -= 10
            self.performance_issues.append({
                'severity': 'medium',
                'title': 'Needs Improvement: TBT',
                'description': f"TBT is {self.performance_metrics['tbt']}ms (should be < 200ms)"
            })
        
        # CLS scoring (Good < 0.1, Needs Improvement < 0.25, Poor >= 0.25)
        if self.performance_metrics.get('cls', 0) > 0.25:
            score -= 20
            self.performance_issues.append({
                'severity': 'high',
                'title': 'Poor Cumulative Layout Shift (CLS)',
                'description': f"CLS is {self.performance_metrics['cls']} (should be < 0.1)"
            })
        elif self.performance_metrics.get('cls', 0) > 0.1:
            score -= 8
            self.performance_issues.append({
                'severity': 'medium',
                'title': 'Needs Improvement: CLS',
                'description': f"CLS is {self.performance_metrics['cls']} (should be < 0.1)"
            })
        
        # TTFB scoring (Good < 800ms)
        if self.performance_metrics.get('ttfb', 0) > 800:
            score -= 10
            self.performance_issues.append({
                'severity': 'medium',
                'title': 'Slow Time to First Byte (TTFB)',
                'description': f"TTFB is {self.performance_metrics['ttfb']}ms (should be < 800ms)"
            })
        
        # Convert score to grade
        if score >= 90:
            self.performance_grade = 'A'
        elif score >= 80:
            self.performance_grade = 'B'
        elif score >= 70:
            self.performance_grade = 'C'
        elif score >= 60:
            self.performance_grade = 'D'
        else:
            self.performance_grade = 'F'
        
        self.performance_score = max(0, min(100, score))
    
    def _format_time(self, ms):
        """Format milliseconds to human-readable string"""
        if ms < 1000:
            return f"{ms}ms"
        return f"{ms / 1000:.2f}s"
    
    def _get_grade_color(self):
        """Get emoji color for performance grade"""
        if self.performance_score >= 80:
            return '🟢'
        elif self.performance_score >= 70:
            return '🟡'
        elif self.performance_score >= 60:
            return '🟠'
        return '🔴'
    
    def _has_seo_issues(self, issues):
        """Check if a page has any SEO issues"""
        return (
            issues['missing_og_image'] or 
            issues['missing_title'] or 
            issues['missing_description'] or
            issues['missing_canonical'] or
            issues['missing_lang'] or
            issues['title_too_short'] or
            issues['title_too_long'] or
            issues['description_too_short'] or
            issues['description_too_long']
        )
    
    def _count_total_broken_links(self):
        """Count total broken links across all pages"""
        return sum(len(links) for links in self.broken_links.values())
    
    def create_github_issue(self):
        """Create a comprehensive GitHub issue for all SEO issues found"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return
        
        # Count issues
        pages_with_issues = []
        for url, issues in self.seo_issues.items():
            if self._has_seo_issues(issues):
                pages_with_issues.append((url, issues))
        
        has_sitemap_issues = (
            len(self.urls_in_sitemap_not_crawled) > 0 or 
            len(self.urls_crawled_not_in_sitemap) > 0
        )
        
        if not pages_with_issues and not self.broken_links and not has_sitemap_issues:
            return
        
        title = f"SEO Issues Found on {self.base_url}"
        body = self._format_github_issue_body(pages_with_issues)
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Add performance label if there are performance issues
        labels = ['seo', 'full-seo-audit']
        if self.performance_issues:
            labels.append('performance')
        
        payload = {
            'title': title,
            'body': body,
            'labels': labels
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            issue_data = response.json()
            print(f"\nCreated issue #{issue_data['number']}: {issue_data['html_url']}")
        except Exception as e:
            print(f"\nError creating GitHub issue: {e}")
    
    def _format_github_issue_body(self, pages_with_issues):
        """Format the GitHub issue body"""
        body = f"## Full SEO Audit Report\n\n"
        body += f"**Website:** {self.base_url}\n"
        body += f"**Pages checked:** {len(self.visited_pages)}\n"
        body += f"**Pages with SEO issues:** {len(pages_with_issues)}\n"
        body += f"**Total broken links:** {self._count_total_broken_links()}\n"
        
        if self.sitemap_urls:
            body += f"**Sitemap URLs found:** {len(self.sitemap_urls)}\n"
            body += f"**Sitemap mismatches:** {len(self.urls_in_sitemap_not_crawled) + len(self.urls_crawled_not_in_sitemap)}\n"
        
        body += f"\n---\n\n"
        
        # Performance Metrics Section
        if self.performance_metrics:
            body += f"## 📊 Performance Metrics (Homepage)\n\n"
            body += f"| Metric | Value | Status |\n"
            body += f"|--------|-------|--------|\n"
            
            # LCP
            lcp_status = '🟢 Good' if self.performance_metrics['lcp'] < 2500 else '🟡 Needs Improvement' if self.performance_metrics['lcp'] < 4000 else '🔴 Poor'
            body += f"| Largest Contentful Paint (LCP) | {self._format_time(self.performance_metrics['lcp'])} | {lcp_status} |\n"
            
            # TBT
            tbt_status = '🟢 Good' if self.performance_metrics['tbt'] < 200 else '🟡 Needs Improvement' if self.performance_metrics['tbt'] < 600 else '🔴 Poor'
            body += f"| Total Blocking Time (TBT) | {self._format_time(self.performance_metrics['tbt'])} | {tbt_status} |\n"
            
            # CLS
            cls_status = '🟢 Good' if self.performance_metrics['cls'] < 0.1 else '🟡 Needs Improvement' if self.performance_metrics['cls'] < 0.25 else '🔴 Poor'
            body += f"| Cumulative Layout Shift (CLS) | {self.performance_metrics['cls']} | {cls_status} |\n"
            
            # TTFB
            ttfb_status = '🟢 Good' if self.performance_metrics['ttfb'] < 800 else '🔴 Slow'
            body += f"| Time to First Byte (TTFB) | {self._format_time(self.performance_metrics['ttfb'])} | {ttfb_status} |\n"
            
            # FCP
            fcp_status = '🟢 Good' if self.performance_metrics['fcp'] < 1800 else '🔴 Slow'
            body += f"| First Contentful Paint (FCP) | {self._format_time(self.performance_metrics['fcp'])} | {fcp_status} |\n"
            
            # Load time
            body += f"| Fully Loaded | {self._format_time(self.performance_metrics['load_event_end'])} | - |\n"
            
            body += f"\n"
            
            # Performance Issues
            if self.performance_issues:
                body += f"### ⚠️ Performance Issues\n\n"
                for issue in self.performance_issues:
                    icon = '🔴' if issue['severity'] == 'high' else '🟡'
                    body += f"- {icon} **{issue['title']}**: {issue['description']}\n"
                body += f"\n"
        
        # SEO Issues Section
        if pages_with_issues:
            body += f"## 🔍 SEO Issues\n\n"
            
            for url, issues in sorted(pages_with_issues):
                body += f"### Page: {url}\n\n"
                
                issue_list = []
                
                if issues['missing_title']:
                    issue_list.append("❌ **Missing Title Tag**")
                elif issues['title_too_short']:
                    issue_list.append(f"⚠️ **Title Too Short** (< 30 chars): `{issues['title']}`")
                elif issues['title_too_long']:
                    issue_list.append(f"⚠️ **Title Too Long** (> 60 chars): `{issues['title']}`")
                
                if issues['missing_description']:
                    issue_list.append("❌ **Missing Meta Description**")
                elif issues['description_too_short']:
                    issue_list.append(f"⚠️ **Meta Description Too Short** (< 50 chars)")
                elif issues['description_too_long']:
                    issue_list.append(f"⚠️ **Meta Description Too Long** (> 160 chars)")
                
                if issues['missing_og_image']:
                    issue_list.append("❌ **Missing OG Image**")
                
                if issues['missing_canonical']:
                    issue_list.append("❌ **Missing Canonical Link**")
                
                if issues['missing_lang']:
                    issue_list.append("❌ **Missing Language Attribute**")
                
                for issue_text in issue_list:
                    body += f"- {issue_text}\n"
                
                body += f"\n"
        
        # Broken Links Section
        if self.broken_links:
            body += f"## 🔗 Broken Links\n\n"
            
            for page_url, broken_links_list in sorted(self.broken_links.items()):
                body += f"### Page: {page_url}\n\n"
                body += f"Found {len(broken_links_list)} broken link(s):\n\n"
                
                for link_info in broken_links_list:
                    status = link_info['status_code']
                    url = link_info['url']
                    body += f"- `{url}` - Status Code: {status}\n"
                
                body += f"\n"
        
        # Sitemap Section
        if self.sitemap_urls:
            body += f"## 🗺️ Sitemap Validation\n\n"
            body += f"**Total URLs in sitemap:** {len(self.sitemap_urls)}\n"
            body += f"**Sitemaps processed:** {len(self.processed_sitemaps)}\n\n"
            
            if self.urls_in_sitemap_not_crawled:
                body += f"### URLs in Sitemap but Not Found During Crawl ({len(self.urls_in_sitemap_not_crawled)})\n\n"
                body += f"These URLs are listed in the sitemap but were not discovered during website crawling:\n\n"
                for url in sorted(self.urls_in_sitemap_not_crawled)[:MAX_URLS_IN_REPORT]:
                    body += f"- {url}\n"
                if len(self.urls_in_sitemap_not_crawled) > MAX_URLS_IN_REPORT:
                    body += f"\n*...and {len(self.urls_in_sitemap_not_crawled) - MAX_URLS_IN_REPORT} more*\n"
                body += f"\n"
            
            if self.urls_crawled_not_in_sitemap:
                body += f"### URLs Crawled but Not in Sitemap ({len(self.urls_crawled_not_in_sitemap)})\n\n"
                body += f"These URLs were found during website crawling but are missing from the sitemap:\n\n"
                for url in sorted(self.urls_crawled_not_in_sitemap)[:MAX_URLS_IN_REPORT]:
                    body += f"- {url}\n"
                if len(self.urls_crawled_not_in_sitemap) > MAX_URLS_IN_REPORT:
                    body += f"\n*...and {len(self.urls_crawled_not_in_sitemap) - MAX_URLS_IN_REPORT} more*\n"
                body += f"\n"
            
            if not self.urls_in_sitemap_not_crawled and not self.urls_crawled_not_in_sitemap:
                body += f"✅ All sitemap URLs match the crawled pages!\n\n"
        
        # SEO Best Practices Section
        body += f"---\n\n"
        body += f"## 📋 SEO Best Practices\n\n"
        body += f"### Title Tags\n"
        body += f"- Should be 30-60 characters long\n"
        body += f"- Must be unique for each page\n"
        body += f"- Should accurately describe the page content\n\n"
        body += f"### Meta Descriptions\n"
        body += f"- Should be 50-160 characters long\n"
        body += f"- Must be unique for each page\n"
        body += f"- Should provide a compelling summary of the page\n\n"
        body += f"### Open Graph Images\n"
        body += f"- Required for social media sharing\n"
        body += f"- Use `<meta property=\"og:image\" content=\"...\" />` tag\n\n"
        body += f"### Canonical Links\n"
        body += f"- Prevents duplicate content issues\n"
        body += f"- Use `<link rel=\"canonical\" href=\"...\" />` tag\n\n"
        body += f"### Language Attribute\n"
        body += f"- Helps search engines understand the page language\n"
        body += f"- Use `<html lang=\"en\">` or appropriate language code\n\n"
        body += f"### Performance\n"
        body += f"- LCP should be under 2.5 seconds\n"
        body += f"- TBT should be under 200ms\n"
        body += f"- CLS should be under 0.1\n\n"
        body += f"### Sitemaps\n"
        body += f"- Should include all important pages on the website\n"
        body += f"- Must be accessible at `/sitemap.xml`\n"
        body += f"- Should match the pages actually available on the site\n"
        body += f"- Can use sitemap index files for large websites\n\n"
        
        body += f"---\n"
        body += f"*Generated by Full SEO Checker on {time.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        
        return body
    
    def prepare_webhook_payload(self):
        """Prepare JSON payload for webhook"""
        # Count issues
        pages_with_issues = []
        seo_issues_list = []
        
        for url, issues in self.seo_issues.items():
            if self._has_seo_issues(issues):
                pages_with_issues.append((url, issues))
                
                # Create detailed issue list for this page
                page_issues = []
                if issues['missing_title']:
                    page_issues.append({'type': 'missing_title', 'severity': 'high'})
                elif issues['title_too_short']:
                    page_issues.append({'type': 'title_too_short', 'severity': 'medium', 'value': issues['title']})
                elif issues['title_too_long']:
                    page_issues.append({'type': 'title_too_long', 'severity': 'medium', 'value': issues['title']})
                
                if issues['missing_description']:
                    page_issues.append({'type': 'missing_description', 'severity': 'high'})
                elif issues['description_too_short']:
                    page_issues.append({'type': 'description_too_short', 'severity': 'medium'})
                elif issues['description_too_long']:
                    page_issues.append({'type': 'description_too_long', 'severity': 'medium'})
                
                if issues['missing_og_image']:
                    page_issues.append({'type': 'missing_og_image', 'severity': 'medium'})
                
                if issues['missing_canonical']:
                    page_issues.append({'type': 'missing_canonical', 'severity': 'medium'})
                
                if issues['missing_lang']:
                    page_issues.append({'type': 'missing_lang', 'severity': 'low'})
                
                seo_issues_list.append({
                    'url': url,
                    'issues': page_issues
                })
        
        # Format broken links
        broken_links_list = []
        for page_url, links in self.broken_links.items():
            for link_info in links:
                broken_links_list.append({
                    'page_url': page_url,
                    'broken_url': link_info['url'],
                    'status_code': link_info['status_code']
                })
        
        # Build payload
        payload = {
            'website_url': self.base_url,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'summary': {
                'pages_checked': len(self.visited_pages),
                'pages_with_seo_issues': len(pages_with_issues),
                'total_broken_links': len(broken_links_list),
                'sitemap_urls_found': len(self.sitemap_urls) if self.sitemap_urls else 0,
                'sitemap_mismatches': len(self.urls_in_sitemap_not_crawled) + len(self.urls_crawled_not_in_sitemap)
            },
            'performance': {
                'grade': self.performance_grade,
                'score': self.performance_score,
                'metrics': self.performance_metrics,
                'issues': self.performance_issues
            } if self.performance_metrics else None,
            'seo_issues': seo_issues_list,
            'broken_links': broken_links_list,
            'sitemap': {
                'total_urls': len(self.sitemap_urls) if self.sitemap_urls else 0,
                'sitemaps_processed': len(self.processed_sitemaps),
                'urls_in_sitemap_not_crawled': self.urls_in_sitemap_not_crawled,
                'urls_crawled_not_in_sitemap': self.urls_crawled_not_in_sitemap
            } if self.sitemap_urls else None
        }
        
        return payload
    
    def send_to_webhook(self):
        """Send results to webhook URL"""
        if not WEBHOOK_URL:
            return False
        
        print(f"\nSending results to webhook: {WEBHOOK_URL}")
        
        try:
            payload = self.prepare_webhook_payload()
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': USER_AGENT
            }
            
            response = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            print(f"✅ Successfully sent results to webhook (Status: {response.status_code})")
            return True
        except Exception as e:
            print(f"❌ Error sending to webhook: {e}")
            return False
    
    def report_results(self):
        """Report results and create issues if needed"""
        print("\n" + "="*60)
        print("FULL SEO AUDIT RESULTS")
        print("="*60)
        print(f"Pages crawled: {len(self.visited_pages)}")
        print(f"Links checked: {len(self.checked_links)}")
        
        # Report performance metrics
        if self.performance_metrics:
            print(f"\nPerformance Grade: {self.performance_grade} (Score: {self.performance_score}/100)")
            print(f"  LCP: {self._format_time(self.performance_metrics['lcp'])}")
            print(f"  TBT: {self._format_time(self.performance_metrics['tbt'])}")
            print(f"  CLS: {self.performance_metrics['cls']}")
            print(f"  TTFB: {self._format_time(self.performance_metrics['ttfb'])}")
            print(f"  FCP: {self._format_time(self.performance_metrics['fcp'])}")
        
        # Count SEO issues
        pages_with_seo_issues = 0
        for url, issues in self.seo_issues.items():
            if self._has_seo_issues(issues):
                pages_with_seo_issues += 1
        
        print(f"\nPages with SEO issues: {pages_with_seo_issues}")
        print(f"Pages with broken links: {len(self.broken_links)}")
        print(f"Performance issues: {len(self.performance_issues)}")
        
        has_issues = False
        
        # Report performance issues
        if self.performance_issues:
            print("\n" + "="*60)
            print("PERFORMANCE ISSUES FOUND")
            print("="*60)
            for issue in self.performance_issues:
                icon = '🔴' if issue['severity'] == 'high' else '🟡'
                print(f"  {icon} {issue['title']}: {issue['description']}")
            has_issues = True
        
        # Report SEO issues
        if pages_with_seo_issues > 0:
            print("\n" + "="*60)
            print("SEO ISSUES FOUND")
            print("="*60)
            
            for url, issues in self.seo_issues.items():
                issue_list = []
                
                if issues['missing_title']:
                    issue_list.append("Missing Title")
                elif issues['title_too_short']:
                    issue_list.append("Title Too Short")
                elif issues['title_too_long']:
                    issue_list.append("Title Too Long")
                
                if issues['missing_description']:
                    issue_list.append("Missing Description")
                elif issues['description_too_short']:
                    issue_list.append("Description Too Short")
                elif issues['description_too_long']:
                    issue_list.append("Description Too Long")
                
                if issues['missing_og_image']:
                    issue_list.append("Missing OG Image")
                
                if issues['missing_canonical']:
                    issue_list.append("Missing Canonical")
                
                if issues['missing_lang']:
                    issue_list.append("Missing Lang Attribute")
                
                if issue_list:
                    print(f"\n{url}:")
                    for issue in issue_list:
                        print(f"  - {issue}")
            
            has_issues = True
        
        # Report broken links
        if self.broken_links:
            print("\n" + "="*60)
            print("BROKEN LINKS FOUND")
            print("="*60)
            
            for page_url, broken_links_list in self.broken_links.items():
                print(f"\n{page_url}:")
                for link_info in broken_links_list:
                    print(f"  - {link_info['url']} (Status: {link_info['status_code']})")
            
            has_issues = True
        
        # Report sitemap issues
        if self.sitemap_urls:
            if self.urls_in_sitemap_not_crawled or self.urls_crawled_not_in_sitemap:
                print("\n" + "="*60)
                print("SITEMAP MISMATCHES FOUND")
                print("="*60)
                
                if self.urls_in_sitemap_not_crawled:
                    print(f"\nURLs in sitemap but not crawled ({len(self.urls_in_sitemap_not_crawled)}):")
                    for url in sorted(self.urls_in_sitemap_not_crawled)[:MAX_URLS_IN_CONSOLE]:
                        print(f"  - {url}")
                    if len(self.urls_in_sitemap_not_crawled) > MAX_URLS_IN_CONSOLE:
                        print(f"  ...and {len(self.urls_in_sitemap_not_crawled) - MAX_URLS_IN_CONSOLE} more")
                
                if self.urls_crawled_not_in_sitemap:
                    print(f"\nURLs crawled but not in sitemap ({len(self.urls_crawled_not_in_sitemap)}):")
                    for url in sorted(self.urls_crawled_not_in_sitemap)[:MAX_URLS_IN_CONSOLE]:
                        print(f"  - {url}")
                    if len(self.urls_crawled_not_in_sitemap) > MAX_URLS_IN_CONSOLE:
                        print(f"  ...and {len(self.urls_crawled_not_in_sitemap) - MAX_URLS_IN_CONSOLE} more")
                
                has_issues = True
        
        # Send results to webhook or create GitHub issue
        if has_issues:
            if WEBHOOK_URL:
                # Send to webhook instead of creating issue
                webhook_success = self.send_to_webhook()
                if webhook_success:
                    print("\n" + "="*60)
                    print("❌ FAILED: SEO issues or broken links found!")
                    print("Results sent to webhook instead of creating GitHub issue.")
                    print("="*60)
                else:
                    print("\n" + "="*60)
                    print("❌ FAILED: SEO issues or broken links found!")
                    print("⚠️  Warning: Failed to send results to webhook.")
                    print("="*60)
            else:
                # Create GitHub issue as usual
                self.create_github_issue()
                
                print("\n" + "="*60)
                print("❌ FAILED: SEO issues or broken links found!")
                print("="*60)
            return False
        else:
            if WEBHOOK_URL:
                # Send success result to webhook
                webhook_success = self.send_to_webhook()
                print("\n" + "="*60)
                print("✅ SUCCESS: No SEO issues or broken links found!")
                if webhook_success:
                    print("Results sent to webhook.")
                else:
                    print("⚠️  Warning: Failed to send results to webhook.")
                print("="*60)
            else:
                print("\n" + "="*60)
                print("✅ SUCCESS: No SEO issues or broken links found!")
                print("="*60)
            return True


def main():
    if not WEBSITE_URL:
        print("Error: WEBSITE_URL environment variable is not set")
        sys.exit(1)
    
    # Validate URL format
    if not WEBSITE_URL.startswith(('http://', 'https://')):
        print(f"Error: Invalid URL format. URL must start with http:// or https://")
        sys.exit(1)
    
    print(f"Starting Full SEO Checker for: {WEBSITE_URL}")
    print(f"Maximum pages to crawl: {MAX_PAGES}")
    print("="*60)
    
    checker = FullSEOChecker(WEBSITE_URL)
    checker.crawl_website()
    checker.collect_performance_metrics()
    checker.check_sitemap()
    success = checker.report_results()
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
