#!/usr/bin/env python3
"""
Sitemap Checker Script
Checks sitemap.xml for validity, validates all URLs, and checks nested sitemaps.
"""

import os
import sys
import requests
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import time

# Configuration
WEBSITE_URL = os.environ.get('WEBSITE_URL', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY', '')
REQUEST_TIMEOUT = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
# Domains that return 403 due to requiring login but should not be considered broken
TWITTER_X_DOMAINS = ['twitter.com', 'www.twitter.com', 'x.com', 'www.x.com']

# Sitemap namespaces
SITEMAP_NS = {
    'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'
}


class SitemapChecker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.sitemap_urls = []
        self.broken_urls = []
        self.checked_urls = {}
        self.processed_sitemaps = set()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
    
    def get_sitemap_url(self):
        """Get the sitemap URL at /sitemap.xml"""
        return f"{self.base_url}/sitemap.xml"
    
    def fetch_sitemap(self, sitemap_url):
        """Fetch a sitemap file"""
        try:
            print(f"Fetching sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Error fetching sitemap {sitemap_url}: {e}")
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
            print(f"Error parsing sitemap index: {e}")
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
                    urls.append(loc.text.strip())
            
            return urls
        except Exception as e:
            print(f"Error parsing sitemap URLs: {e}")
            return []
    
    def process_sitemap(self, sitemap_url):
        """Process a sitemap (handles both index and regular sitemaps)"""
        if sitemap_url in self.processed_sitemaps:
            return
        
        self.processed_sitemaps.add(sitemap_url)
        content = self.fetch_sitemap(sitemap_url)
        
        if content is None:
            print(f"Failed to fetch sitemap: {sitemap_url}")
            return
        
        # Try to parse as sitemap index first
        nested_sitemaps = self.parse_sitemap_index(content)
        
        if nested_sitemaps:
            print(f"Found {len(nested_sitemaps)} nested sitemap(s)")
            for nested_sitemap_url in nested_sitemaps:
                self.process_sitemap(nested_sitemap_url)
        else:
            # Parse as regular sitemap
            urls = self.parse_sitemap_urls(content)
            print(f"Found {len(urls)} URL(s) in sitemap")
            self.sitemap_urls.extend(urls)
    
    def check_url(self, url):
        """Check if a URL is accessible"""
        if url in self.checked_urls:
            return self.checked_urls[url]
        
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
            
            self.checked_urls[url] = (status_code, is_broken)
            
            # Add small delay to be respectful
            time.sleep(0.1)
            
            return status_code, is_broken
        except requests.exceptions.RequestException as e:
            print(f"  Error checking {url}: {e}")
            self.checked_urls[url] = (0, True)
            return 0, True
    
    def validate_sitemap_urls(self):
        """Validate all URLs found in the sitemap"""
        print(f"\nValidating {len(self.sitemap_urls)} URLs from sitemap...")
        
        for url in self.sitemap_urls:
            status_code, is_broken = self.check_url(url)
            
            if is_broken:
                self.broken_urls.append({
                    'url': url,
                    'status_code': status_code
                })
                print(f"  ✗ Broken URL: {url} (Status: {status_code})")
            else:
                print(f"  ✓ Valid URL: {url} (Status: {status_code})")
    
    def create_github_issue(self):
        """Create a GitHub issue for broken sitemap URLs"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return
        
        if not self.broken_urls:
            return
        
        title = f"Broken URLs found in sitemap for {self.base_url}"
        
        body = f"## Sitemap Validation Report\n\n"
        body += f"**Website:** {self.base_url}\n"
        body += f"**Total URLs in sitemap:** {len(self.sitemap_urls)}\n"
        body += f"**Broken URLs:** {len(self.broken_urls)}\n"
        body += f"**Sitemaps processed:** {len(self.processed_sitemaps)}\n\n"
        body += f"---\n\n"
        
        body += f"### Broken URLs\n\n"
        for url_info in self.broken_urls:
            status = url_info['status_code']
            url = url_info['url']
            body += f"- `{url}` - Status Code: {status}\n"
        
        body += f"\n---\n\n"
        body += f"### Processed Sitemaps\n\n"
        for sitemap_url in sorted(self.processed_sitemaps):
            body += f"- {sitemap_url}\n"
        
        body += f"\n---\n"
        body += f"*Detected by Sitemap Checker on {time.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        payload = {
            'title': title,
            'body': body,
            'labels': ['sitemap', 'broken-link']
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
        print("SITEMAP VALIDATION RESULTS")
        print("="*60)
        print(f"Sitemaps processed: {len(self.processed_sitemaps)}")
        print(f"Total URLs found: {len(self.sitemap_urls)}")
        print(f"Broken URLs: {len(self.broken_urls)}")
        
        if self.broken_urls:
            print("\n" + "="*60)
            print("BROKEN URLS IN SITEMAP")
            print("="*60)
            
            for url_info in self.broken_urls:
                print(f"  - {url_info['url']} (Status: {url_info['status_code']})")
            
            # Create GitHub issue
            self.create_github_issue()
            
            print("\n" + "="*60)
            print("❌ FAILED: Broken URLs found in sitemap!")
            print("="*60)
            return False
        else:
            print("\n" + "="*60)
            print("✅ SUCCESS: All sitemap URLs are valid!")
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
    
    print(f"Starting sitemap checker for: {WEBSITE_URL}")
    print("="*60)
    
    checker = SitemapChecker(WEBSITE_URL)
    
    # Get and process sitemap
    sitemap_url = checker.get_sitemap_url()
    checker.process_sitemap(sitemap_url)
    
    if not checker.sitemap_urls:
        print("\n" + "="*60)
        print("❌ FAILED: No sitemap found or sitemap is empty!")
        print("="*60)
        sys.exit(1)
    
    # Validate all URLs
    checker.validate_sitemap_urls()
    
    # Report results
    success = checker.report_results()
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
