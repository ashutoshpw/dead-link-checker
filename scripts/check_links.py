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
USER_AGENT = 'Mozilla/5.0 (compatible; DeadLinkChecker/1.0)'


class LinkChecker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.visited_pages = set()
        self.checked_links = {}
        self.broken_links = defaultdict(list)
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
    
    def check_link(self, url):
        """Check if a link is broken"""
        if url in self.checked_links:
            return self.checked_links[url]
        
        try:
            # Use HEAD request first for efficiency
            response = self.session.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            status_code = response.status_code
            
            # Some servers don't support HEAD, fallback to GET only for 405
            if status_code == 405:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                status_code = response.status_code
            
            is_broken = status_code >= 400
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
    
    def create_github_issue(self, page_url, broken_links):
        """Create a GitHub issue for broken links on a page"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return
        
        title = f"Broken links found on {page_url}"
        
        body = f"## Broken Links Report\n\n"
        body += f"**Page:** {page_url}\n\n"
        body += f"The following broken links were found on this page:\n\n"
        
        for link_info in broken_links:
            status = link_info['status_code']
            url = link_info['url']
            body += f"- `{url}` - Status Code: {status}\n"
        
        body += f"\n---\n"
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
        
        if self.broken_links:
            print("\n" + "="*60)
            print("BROKEN LINKS SUMMARY")
            print("="*60)
            
            for page_url, broken_links_list in self.broken_links.items():
                print(f"\n{page_url}:")
                for link_info in broken_links_list:
                    print(f"  - {link_info['url']} (Status: {link_info['status_code']})")
                
                # Create GitHub issue for this page
                self.create_github_issue(page_url, broken_links_list)
            
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
