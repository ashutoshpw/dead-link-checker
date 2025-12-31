#!/usr/bin/env python3
"""
OG Image Checker Script
Crawls a website and checks for presence of Open Graph images on all routes.
"""

import os
import sys
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


class OGImageChecker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.visited_pages = set()
        self.pages_without_og_image = []
        self.pages_with_og_image = []
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
    
    def check_og_image(self, url):
        """Check if a page has an OG image tag"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check for og:image meta tag
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                og_image_url = og_image.get('content')
                print(f"  ✓ OG image found: {og_image_url}")
                return True, og_image_url
            else:
                print(f"  ✗ No OG image found")
                return False, None
                
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None, None
    
    def get_links_from_page(self, url):
        """Extract all same-domain links from a page"""
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            links = []
            
            for tag in soup.find_all('a', href=True):
                href = tag['href']
                absolute_url = urljoin(url, href)
                if self.is_same_domain(absolute_url):
                    links.append(absolute_url)
            
            return links
        except Exception as e:
            print(f"Error fetching links from {url}: {e}")
            return []
    
    def crawl_website(self):
        """Crawl the website and check for OG images on all pages"""
        pages_to_visit = [self.base_url]
        
        while pages_to_visit and len(self.visited_pages) < MAX_PAGES:
            current_url = pages_to_visit.pop(0)
            normalized_url = self.normalize_url(current_url)
            
            if normalized_url in self.visited_pages:
                continue
            
            print(f"Checking: {current_url}")
            self.visited_pages.add(normalized_url)
            
            # Check for OG image on this page
            has_og_image, og_image_url = self.check_og_image(current_url)
            
            if has_og_image is None:
                # Error occurred, skip this page
                continue
            elif has_og_image:
                self.pages_with_og_image.append({
                    'url': current_url,
                    'og_image': og_image_url
                })
            else:
                self.pages_without_og_image.append(current_url)
            
            # Get links from this page to continue crawling
            links = self.get_links_from_page(current_url)
            
            # Add small delay to be respectful
            time.sleep(0.1)
            
            for link in links:
                normalized_link = self.normalize_url(link)
                if normalized_link not in self.visited_pages:
                    pages_to_visit.append(link)
    
    def create_github_issue(self):
        """Create a GitHub issue for pages missing OG images"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return
        
        if not self.pages_without_og_image:
            return
        
        title = f"Missing OG images on {len(self.pages_without_og_image)} page(s)"
        
        body = f"## Missing OG Images Report\n\n"
        body += f"**Website:** {self.base_url}\n\n"
        body += f"The following pages are missing Open Graph image tags:\n\n"
        
        for page_url in self.pages_without_og_image:
            body += f"- {page_url}\n"
        
        body += f"\n### What are OG images?\n\n"
        body += f"Open Graph images are used when sharing pages on social media. "
        body += f"They should be defined using the `<meta property=\"og:image\" content=\"...\" />` tag in the HTML head.\n\n"
        body += f"### Summary\n\n"
        body += f"- Total pages checked: {len(self.visited_pages)}\n"
        body += f"- Pages with OG images: {len(self.pages_with_og_image)}\n"
        body += f"- Pages without OG images: {len(self.pages_without_og_image)}\n\n"
        body += f"---\n"
        body += f"*Detected by OG Image Checker on {time.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        payload = {
            'title': title,
            'body': body,
            'labels': ['og-image']
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
        print("OG IMAGE CHECKING RESULTS")
        print("="*60)
        print(f"Pages crawled: {len(self.visited_pages)}")
        print(f"Pages with OG images: {len(self.pages_with_og_image)}")
        print(f"Pages without OG images: {len(self.pages_without_og_image)}")
        
        if self.pages_without_og_image:
            print("\n" + "="*60)
            print("PAGES WITHOUT OG IMAGES")
            print("="*60)
            
            for page_url in self.pages_without_og_image:
                print(f"  - {page_url}")
            
            # Create GitHub issue
            self.create_github_issue()
            
            print("\n" + "="*60)
            print("❌ FAILED: Pages without OG images found!")
            print("="*60)
            return False
        else:
            print("\n" + "="*60)
            print("✅ SUCCESS: All pages have OG images!")
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
    
    print(f"Starting OG image checker for: {WEBSITE_URL}")
    print(f"Maximum pages to crawl: {MAX_PAGES}")
    print("="*60)
    
    checker = OGImageChecker(WEBSITE_URL)
    checker.crawl_website()
    success = checker.report_results()
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
