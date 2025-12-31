# Dead Link Checker & OG Image Checker

GitHub Action workflows that check websites for broken links and missing Open Graph images, automatically creating issues when problems are found.

## Features

### Dead Link Checker
- 🔍 Crawls entire websites to discover all pages
- 🔗 Checks all links on each page for broken links (404, 500, etc.)
- 📝 Automatically creates GitHub issues for pages with broken links
- ✅ Passes if no broken links are found
- ❌ Fails if broken links are detected

### OG Image Checker
- 🔍 Crawls entire websites to discover all pages
- 🖼️ Checks for Open Graph image tags on each page
- 📝 Automatically creates GitHub issues for pages missing OG images
- ✅ Passes if all pages have OG images
- ❌ Fails if pages without OG images are detected

## Usage

### Dead Link Checker

#### Running the Workflow

1. Go to the "Actions" tab in your repository
2. Select "Check Dead Links" workflow
3. Click "Run workflow"
4. Enter the website URL (e.g., `https://example.com`)
5. Click "Run workflow"

The workflow will:
- Crawl the specified website
- Check all links found on the site
- Create a GitHub issue for each page containing broken links
- Pass (green) if no broken links are found
- Fail (red) if broken links are detected

#### Example

Input: `https://example.com`

The checker will:
1. Start at `https://example.com`
2. Find all links on the homepage
3. Visit each page on the same domain
4. Check every link on every page
5. Report any broken links

### OG Image Checker

#### Running the Workflow

1. Go to the "Actions" tab in your repository
2. Select "Check OG Images" workflow
3. Click "Run workflow"
4. Enter the website URL (e.g., `https://example.com`)
5. Click "Run workflow"

The workflow will:
- Crawl the specified website
- Check for Open Graph image tags on each page
- Create a GitHub issue listing all pages without OG images
- Pass (green) if all pages have OG images
- Fail (red) if pages without OG images are detected

#### Example

Input: `https://example.com`

The checker will:
1. Start at `https://example.com`
2. Check for `<meta property="og:image" content="..." />` tag
3. Visit each page on the same domain
4. Check every page for OG image tags
5. Report any pages missing OG images

## How It Works

### Dead Link Checker

The workflow uses a Python script that:
1. Crawls the website starting from the provided URL
2. Extracts all links from each page
3. Checks each link's HTTP status code
4. Identifies links with 4xx or 5xx status codes as broken
5. Creates a GitHub issue for each page with broken links
6. Issues include the page URL and all broken links found

### OG Image Checker

The workflow uses a Python script that:
1. Crawls the website starting from the provided URL
2. Checks each page for the `<meta property="og:image">` tag
3. Identifies pages missing this tag
4. Creates a GitHub issue listing all pages without OG images
5. The issue includes a summary of pages checked and pages missing OG images

## Requirements

- Python 3.11+
- Dependencies listed in `requirements.txt`:
  - requests
  - beautifulsoup4
  - urllib3

## Configuration

Both workflows have these default settings:
- Maximum pages to crawl: 100 (prevents infinite crawling)
- Request timeout: 10 seconds
- Delay between requests: 0.1 seconds (respectful crawling)

To modify these, edit the constants in the respective Python scripts:
- `scripts/check_links.py` for dead link checking
- `scripts/check_og_images.py` for OG image checking

## Permissions

Both workflows require:
- `contents: read` - to checkout the repository
- `issues: write` - to create issues for broken links or missing OG images

## License

See [LICENSE](LICENSE) file for details.