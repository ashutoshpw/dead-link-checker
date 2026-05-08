#!/usr/bin/env python3
"""
Schema.org Checker Script
Crawls a website and validates Schema.org JSON-LD blocks on all routes.
"""

import os
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from schema_org_utils import analyze_schema_org_from_soup, summarize_schema_results

# Configuration
WEBSITE_URL = os.environ.get('WEBSITE_URL', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY', '')
MAX_PAGES = 100
REQUEST_TIMEOUT = 10
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'


class SchemaOrgChecker:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.visited_pages = set()
        self.schema_results = {}
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})

    def normalize_url(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def is_same_domain(self, url):
        return urlparse(url).netloc == self.domain

    def should_skip_page(self, url):
        return urlparse(url).path.startswith('/cdn-cgi/')

    def inspect_page(self, url):
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            self.schema_results[url] = analyze_schema_org_from_soup(soup)

            links = []
            for tag in soup.find_all('a', href=True):
                absolute_url = urljoin(url, tag['href'])
                if self.is_same_domain(absolute_url) and not self.should_skip_page(absolute_url):
                    links.append(absolute_url)

            return links
        except Exception as exc:
            print(f"Error fetching {url}: {exc}")
            return []

    def crawl_website(self):
        pages_to_visit = [self.base_url]

        while pages_to_visit and len(self.visited_pages) < MAX_PAGES:
            current_url = pages_to_visit.pop(0)
            normalized_url = self.normalize_url(current_url)

            if normalized_url in self.visited_pages:
                continue

            if self.should_skip_page(current_url):
                self.visited_pages.add(normalized_url)
                continue

            print(f"Checking: {current_url}")
            self.visited_pages.add(normalized_url)
            links = self.inspect_page(current_url)
            time.sleep(0.1)

            for link in links:
                normalized_link = self.normalize_url(link)
                if normalized_link not in self.visited_pages:
                    pages_to_visit.append(link)

    def create_github_issue(self):
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print("GitHub token or repository not configured, skipping issue creation")
            return

        summary = summarize_schema_results(self.schema_results)
        if not summary['pages_with_issues']:
            return

        title = f"Schema.org issues found on {self.base_url}"
        body = self._format_issue_body(summary)

        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'Bearer {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        payload = {
            'title': title,
            'body': body,
            'labels': ['seo', 'schema-org']
        }

        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            issue_data = response.json()
            print(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        except Exception as exc:
            print(f"Error creating GitHub issue: {exc}")

    def _format_issue_body(self, summary):
        body = "## Schema.org Validation Report\n\n"
        body += f"**Website:** {self.base_url}\n"
        body += f"**Pages checked:** {len(self.visited_pages)}\n"
        body += f"**Pages with structured data:** {summary['pages_with_schema']}\n"
        body += f"**Pages with structured data issues:** {len(summary['pages_with_issues'])}\n"
        body += f"**JSON-LD blocks found:** {summary['total_blocks']}\n"
        body += f"**Valid blocks:** {summary['valid_blocks']}\n\n"

        if summary['types_found']:
            body += f"**Types found:** {', '.join(summary['types_found'])}\n\n"

        body += "### Failing Findings\n\n"
        for url in summary['pages_with_issues']:
            body += f"#### Page: {url}\n\n"
            for issue in self.schema_results[url]['issues']:
                block_text = f" (block {issue['block_index']})" if 'block_index' in issue else ''
                body += f"- **{issue['type']}**{block_text}: {issue['message']}\n"
            body += "\n"

        if summary['pages_without_schema']:
            body += f"### Informational: Pages Without Structured Data ({len(summary['pages_without_schema'])})\n\n"
            body += "These pages do not include Schema.org markup. They are listed for visibility only and do not fail this check.\n\n"
            for url in summary['pages_without_schema']:
                body += f"- {url}\n"
            body += "\n"

        body += "### Notes\n\n"
        body += "- This checker validates JSON-LD only.\n"
        body += "- Missing Schema.org markup does not fail the check.\n"
        body += "- Malformed JSON-LD or missing `@context` / `@type` does fail the check.\n\n"
        body += "---\n"
        body += f"*Detected by Schema.org Checker on {time.strftime('%Y-%m-%d %H:%M:%S UTC')}*"
        return body

    def report_results(self):
        summary = summarize_schema_results(self.schema_results)

        print("\n" + "=" * 60)
        print("SCHEMA.ORG CHECK RESULTS")
        print("=" * 60)
        print(f"Pages crawled: {len(self.visited_pages)}")
        print(f"Pages with Schema.org: {summary['pages_with_schema']}")
        print(f"Pages with Schema.org issues: {len(summary['pages_with_issues'])}")
        print(f"Schema.org blocks found: {summary['total_blocks']}")
        print(f"Valid Schema.org blocks: {summary['valid_blocks']}")

        if summary['types_found']:
            print(f"Types found: {', '.join(summary['types_found'])}")

        if summary['pages_without_schema']:
            print("\nInformational pages without Schema.org:")
            for url in summary['pages_without_schema'][:10]:
                print(f"  - {url}")
            if len(summary['pages_without_schema']) > 10:
                print(f"  ...and {len(summary['pages_without_schema']) - 10} more")

        if summary['pages_with_issues']:
            print("\n" + "=" * 60)
            print("STRUCTURED DATA ISSUES FOUND")
            print("=" * 60)
            for url in summary['pages_with_issues']:
                print(f"\n{url}:")
                for issue in self.schema_results[url]['issues']:
                    block_text = f" (block {issue['block_index']})" if 'block_index' in issue else ''
                    print(f"  - {issue['type']}{block_text}: {issue['message']}")

            self.create_github_issue()
            print("\n" + "=" * 60)
            print("❌ FAILED: Schema.org issues found!")
            print("=" * 60)
            return False

        print("\n" + "=" * 60)
        print("✅ SUCCESS: No Schema.org issues found!")
        print("=" * 60)
        return True


def main():
    if not WEBSITE_URL:
        print("Error: WEBSITE_URL environment variable is not set")
        sys.exit(1)

    if not WEBSITE_URL.startswith(('http://', 'https://')):
        print("Error: Invalid URL format. URL must start with http:// or https://")
        sys.exit(1)

    print(f"Starting Schema.org checker for: {WEBSITE_URL}")
    print(f"Maximum pages to crawl: {MAX_PAGES}")
    print("=" * 60)

    checker = SchemaOrgChecker(WEBSITE_URL)
    checker.crawl_website()
    success = checker.report_results()

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
