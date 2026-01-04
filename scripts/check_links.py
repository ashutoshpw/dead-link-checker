#!/usr/bin/env python3
"""
Dead Link Checker Script
Crawls a website and checks for broken links, creates GitHub issues for broken links.
"""

import os
import sys
import json
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import defaultdict
import time

# Configuration
WEBSITE_URL = os.environ.get('WEBSITE_URL', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY', '')
MAX_PAGES = 100  # Limit to prevent infinite crawling
REQUEST_TIMEOUT = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
# Domains that return 403 due to requiring login but should not be considered broken
TWITTER_X_DOMAINS = ['twitter.com', 'www.twitter.com', 'x.com', 'www.x.com']


class LinkChecker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.visited_pages = set()
        self.checked_links = {}
        self.broken_links = defaultdict(list)
        self.mailto_links = defaultdict(list)
        self.tel_links = defaultdict(list)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def normalize_url(self, url):
        """Normalize URL for comparison"""
        # Remove fragment
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    def is_same_domain(self, url):
        """Check if URL belongs to the same domain"""
        return urlparse(url).netloc == self.domain
    
    def get_links_from_page(self, url):
        """Extract all links from a page"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            for tag in soup.find_all('a', href=True):
                href = tag['href']
                absolute_url = urljoin(url, href)
                links.append(absolute_url)
            
            return links, response.status_code
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return [], None
    
    def should_skip_link(self, url):
        """Check if a link should be skipped from checking"""
        parsed_url = urlparse(url)
        path = parsed_url.path
        scheme = parsed_url.scheme
        
        # Skip CDN-CGI email protection links
        if path.startswith('/cdn-cgi/l/email-protection/'):
            return True
        
        return False
    
    def track_special_link(self, url, page_url):
        """Track mailto: and tel: links separately, returns True if tracked"""
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme
        
        if scheme == 'mailto':
            self.mailto_links[page_url].append(url)
            print(f"  📧 mailto link found: {url}")
            return True
        elif scheme == 'tel':
            self.tel_links[page_url].append(url)
            print(f"  📞 tel link found: {url}")
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
            print(f"Error checking {url}: {e}")
            self.checked_links[url] = (0, True)
            return 0, True
    
    def crawl_website(self):
        """Crawl the website and check all links"""
        pages_to_visit = [self.base_url]
        
        while pages_to_visit and len(self.visited_pages) < MAX_PAGES:
            current_url = pages_to_visit.pop(0)
            normalized_url = self.normalize_url(current_url)
            
            if normalized_url in self.visited_pages:
                continue
            
            print(f"Crawling: {current_url}")
            self.visited_pages.add(normalized_url)
            
            links, status = self.get_links_from_page(current_url)
            if status is None:
                continue
            
            for link in links:
                # Track special links (mailto, tel) separately
                if self.track_special_link(link, current_url):
                    continue
                
                # Check the link
                status_code, is_broken = self.check_link(link)
                
                if is_broken:
                    self.broken_links[current_url].append({
                        'url': link,
                        'status_code': status_code
                    })
                    print(f"  ✗ Broken link found: {link} (Status: {status_code})")
                else:
                    print(f"  ✓ Valid link: {link} (Status: {status_code})")
                
                # Add same-domain pages to crawl queue
                if self.is_same_domain(link):
                    normalized_link = self.normalize_url(link)
                    if normalized_link not in self.visited_pages:
                        pages_to_visit.append(link)
    
    def create_consolidated_github_issue(self):
        """Create a single GitHub issue for all broken links found on the website"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return
        
        # Only create an issue if there are broken links
        # (mailto/tel links are informational and included if broken links exist)
        if not self.broken_links:
            return
        
        # Generate appropriate title based on findings
        title = f"Broken links found on {self.base_url}"
        
        # Count total broken links
        total_broken = sum(len(links) for links in self.broken_links.values())
        total_mailto = sum(len(links) for links in self.mailto_links.values())
        total_tel = sum(len(links) for links in self.tel_links.values())
        
        body = f"## Link Report\n\n"
        body += f"**Website:** {self.base_url}\n"
        body += f"**Total broken links:** {total_broken}\n"
        
        # Only mention mailto/tel if they exist
        if total_mailto > 0:
            body += f"**Total mailto: links:** {total_mailto}\n"
        if total_tel > 0:
            body += f"**Total tel: links:** {total_tel}\n"
        
        body += f"\n---\n\n"
        
        # Show broken links first
        body += f"## Broken Links\n\n"
        body += f"**Pages affected:** {len(self.broken_links)}\n\n"
        
        # Group broken links by page
        for page_url, broken_links_list in sorted(self.broken_links.items()):
            body += f"### Page: {page_url}\n\n"
            body += f"Found {len(broken_links_list)} broken link(s):\n\n"
            
            for link_info in broken_links_list:
                status = link_info['status_code']
                url = link_info['url']
                body += f"- `{url}` - Status Code: {status}\n"
            
            body += f"\n"
        
        body += f"---\n\n"
        
        # Show mailto: links (if any) - informational only
        if self.mailto_links:
            body += f"## mailto: Links on Website\n\n"
            body += f"These email links cannot be validated via HTTP requests, but are listed here for reference.\n\n"
            body += f"**Pages with mailto: links:** {len(self.mailto_links)}\n\n"
            
            for page_url, mailto_links_list in sorted(self.mailto_links.items()):
                body += f"### Page: {page_url}\n\n"
                body += f"Found {len(mailto_links_list)} mailto: link(s):\n\n"
                
                for mailto_link in mailto_links_list:
                    body += f"- `{mailto_link}`\n"
                
                body += f"\n"
            
            body += f"---\n\n"
        
        # Show tel: links (if any) - informational only
        if self.tel_links:
            body += f"## tel: Links on Website\n\n"
            body += f"These telephone links cannot be validated via HTTP requests, but are listed here for reference.\n\n"
            body += f"**Pages with tel: links:** {len(self.tel_links)}\n\n"
            
            for page_url, tel_links_list in sorted(self.tel_links.items()):
                body += f"### Page: {page_url}\n\n"
                body += f"Found {len(tel_links_list)} tel: link(s):\n\n"
                
                for tel_link in tel_links_list:
                    body += f"- `{tel_link}`\n"
                
                body += f"\n"
            
            body += f"---\n\n"
        
        body += f"*Detected by Dead Link Checker on {time.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        payload = {
            'title': title,
            'body': body,
            'labels': ['broken-link']
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            issue_data = response.json()
            print(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        except Exception as e:
            print(f"Error creating GitHub issue: {e}")
    
    def report_results(self):
        """Report results and create issues if needed"""
        print("\n" + "="*60)
        print("LINK CHECKING RESULTS")
        print("="*60)
        print(f"Pages crawled: {len(self.visited_pages)}")
        print(f"Links checked: {len(self.checked_links)}")
        print(f"Pages with broken links: {len(self.broken_links)}")
        print(f"Pages with mailto: links: {len(self.mailto_links)}")
        print(f"Pages with tel: links: {len(self.tel_links)}")
        
        if self.broken_links:
            print("\n" + "="*60)
            print("BROKEN LINKS SUMMARY")
            print("="*60)
            
            for page_url, broken_links_list in self.broken_links.items():
                print(f"\n{page_url}:")
                for link_info in broken_links_list:
                    print(f"  - {link_info['url']} (Status: {link_info['status_code']})")
        
        if self.mailto_links:
            print("\n" + "="*60)
            print("MAILTO: LINKS SUMMARY")
            print("="*60)
            
            for page_url, mailto_links_list in self.mailto_links.items():
                print(f"\n{page_url}:")
                for mailto_link in mailto_links_list:
                    print(f"  - {mailto_link}")
        
        if self.tel_links:
            print("\n" + "="*60)
            print("TEL: LINKS SUMMARY")
            print("="*60)
            
            for page_url, tel_links_list in self.tel_links.items():
                print(f"\n{page_url}:")
                for tel_link in tel_links_list:
                    print(f"  - {tel_link}")
        
        # Create a GitHub issue only if there are broken links
        # (mailto/tel links are included in the report as informational content)
        if self.broken_links:
            self.create_consolidated_github_issue()
        
        if self.broken_links:
            print("\n" + "="*60)
            print("❌ FAILED: Broken links found!")
            print("="*60)
            return False
        else:
            print("\n" + "="*60)
            print("✅ SUCCESS: No broken links found!")
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
    
    print(f"Starting dead link checker for: {WEBSITE_URL}")
    print(f"Maximum pages to crawl: {MAX_PAGES}")
    print("="*60)
    
    checker = LinkChecker(WEBSITE_URL)
    checker.crawl_website()
    success = checker.report_results()
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
