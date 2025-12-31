# Dead Link Checker

A GitHub Action workflow that checks websites for broken links and automatically creates issues when dead links are found.

## Features

- 🔍 Crawls entire websites to discover all pages
- 🔗 Checks all links on each page for broken links (404, 500, etc.)
- 📝 Automatically creates a single GitHub issue listing all broken links found on the website
- ✅ Passes if no broken links are found
- ❌ Fails if broken links are detected

## Usage

### Running the Workflow

1. Go to the "Actions" tab in your repository
2. Select "Check Dead Links" workflow
3. Click "Run workflow"
4. Enter the website URL (e.g., `https://example.com`)
5. Click "Run workflow"

The workflow will:
- Crawl the specified website
- Check all links found on the site
- Create a single GitHub issue listing all broken links found, grouped by page
- Pass (green) if no broken links are found
- Fail (red) if broken links are detected

### Example

Input: `https://example.com`

The checker will:
1. Start at `https://example.com`
2. Find all links on the homepage
3. Visit each page on the same domain
4. Check every link on every page
5. Report any broken links

## How It Works

The workflow uses a Python script that:
1. Crawls the website starting from the provided URL
2. Extracts all links from each page
3. Checks each link's HTTP status code
4. Identifies links with 4xx or 5xx status codes as broken
5. Creates a single GitHub issue listing all broken links found
6. The issue groups broken links by the page they were found on

## Requirements

- Python 3.11+
- Dependencies listed in `requirements.txt`:
  - requests
  - beautifulsoup4
  - urllib3

## Configuration

The workflow has these default settings:
- Maximum pages to crawl: 100 (prevents infinite crawling)
- Request timeout: 10 seconds
- Delay between requests: 0.1 seconds (respectful crawling)

To modify these, edit the constants in `scripts/check_links.py`.

## Permissions

The workflow requires:
- `contents: read` - to checkout the repository
- `issues: write` - to create issues for broken links

## License

See [LICENSE](LICENSE) file for details.