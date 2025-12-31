#!/usr/bin/env python3
"""
Full SEO Checker Script
Crawls a website and performs comprehensive SEO checks including:
- Dead links
- OG images
- Meta titles
- Meta descriptions
- Other on-page SEO elements
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
    
    def create_github_issue(self):
        """Create a comprehensive GitHub issue for all SEO issues found"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return
        
        # Count issues
        pages_with_issues = []
        for url, issues in self.seo_issues.items():
            has_issue = (
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
            if has_issue:
                pages_with_issues.append((url, issues))
        
        total_broken = sum(len(links) for links in self.broken_links.values())
        
        if not pages_with_issues and not self.broken_links:
            return
        
        title = f"SEO Issues Found on {self.base_url}"
        
        body = f"## Full SEO Audit Report\n\n"
        body += f"**Website:** {self.base_url}\n"
        body += f"**Pages checked:** {len(self.visited_pages)}\n"
        body += f"**Pages with SEO issues:** {len(pages_with_issues)}\n"
        body += f"**Total broken links:** {total_broken}\n\n"
        body += f"---\n\n"
        
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
        
        body += f"---\n"
        body += f"*Generated by Full SEO Checker on {time.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        
        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        payload = {
            'title': title,
            'body': body,
            'labels': ['seo', 'full-seo-audit']
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            issue_data = response.json()
            print(f"\nCreated issue #{issue_data['number']}: {issue_data['html_url']}")
        except Exception as e:
            print(f"\nError creating GitHub issue: {e}")
    
    def report_results(self):
        """Report results and create issues if needed"""
        print("\n" + "="*60)
        print("FULL SEO AUDIT RESULTS")
        print("="*60)
        print(f"Pages crawled: {len(self.visited_pages)}")
        print(f"Links checked: {len(self.checked_links)}")
        
        # Count SEO issues
        pages_with_seo_issues = 0
        for url, issues in self.seo_issues.items():
            has_issue = (
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
            if has_issue:
                pages_with_seo_issues += 1
        
        print(f"Pages with SEO issues: {pages_with_seo_issues}")
        print(f"Pages with broken links: {len(self.broken_links)}")
        
        has_issues = False
        
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
        
        # Create GitHub issue
        if has_issues:
            self.create_github_issue()
            
            print("\n" + "="*60)
            print("❌ FAILED: SEO issues or broken links found!")
            print("="*60)
            return False
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
    success = checker.report_results()
    
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
