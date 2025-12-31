# Dead Link Checker & SEO Checker

GitHub Action workflows that check websites for broken links, missing Open Graph images, and comprehensive SEO issues, automatically creating issues when problems are found.

## Features

### Dead Link Checker
- 🔍 Crawls entire websites to discover all pages
- 🔗 Checks all links on each page for broken links (404, 500, etc.)
- 📝 Automatically creates a single GitHub issue listing all broken links found on the website
- ✅ Passes if no broken links are found
- ❌ Fails if broken links are detected

### OG Image Checker
- 🔍 Crawls entire websites to discover all pages
- 🖼️ Checks for Open Graph image tags on each page
- 📝 Automatically creates GitHub issues for pages missing OG images
- ✅ Passes if all pages have OG images
- ❌ Fails if pages without OG images are detected

### Full SEO Checker
- 🔍 Crawls entire websites to discover all pages
- 🔗 Checks all links on each page for broken links (404, 500, etc.)
- 🖼️ Checks for Open Graph image tags
- 📄 Checks for meta title tags (with length validation)
- 📝 Checks for meta description tags (with length validation)
- 🔗 Checks for canonical links
- 🌐 Checks for language attributes
- 📊 Creates a comprehensive GitHub issue with all SEO findings
- ✅ Passes if no issues are found
- ❌ Fails if any SEO issues or broken links are detected

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
- Create a single GitHub issue listing all broken links found, grouped by page
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

### Full SEO Checker

#### Running the Workflow

1. Go to the "Actions" tab in your repository
2. Select "Check Full SEO" workflow
3. Click "Run workflow"
4. Enter the website URL (e.g., `https://example.com`)
5. Click "Run workflow"

The workflow will:
- Crawl the specified website
- Check all links for broken URLs
- Check for Open Graph image tags on each page
- Check for meta title tags and validate their length (30-60 characters recommended)
- Check for meta description tags and validate their length (50-160 characters recommended)
- Check for canonical links
- Check for language attributes in HTML tags
- Create a comprehensive GitHub issue with all SEO findings grouped by category
- Pass (green) if no issues are found
- Fail (red) if any SEO issues or broken links are detected

#### Example

Input: `https://example.com`

The checker will:
1. Start at `https://example.com`
2. Visit each page on the same domain
3. Check every link for broken URLs
4. Check for `<meta property="og:image">` tag
5. Check for `<title>` tag and validate length
6. Check for `<meta name="description">` tag and validate length
7. Check for `<link rel="canonical">` tag
8. Check for `lang` attribute in `<html>` tag
9. Generate a comprehensive report with all findings

## How It Works

### Dead Link Checker

The workflow uses a Python script that:
1. Crawls the website starting from the provided URL
2. Extracts all links from each page
3. Checks each link's HTTP status code
4. Identifies links with 4xx or 5xx status codes as broken
5. Creates a single GitHub issue listing all broken links found
6. The issue groups broken links by the page they were found on

### OG Image Checker

The workflow uses a Python script that:
1. Crawls the website starting from the provided URL
2. Checks each page for the `<meta property="og:image">` tag
3. Identifies pages missing this tag
4. Creates a GitHub issue listing all pages without OG images
5. The issue includes a summary of pages checked and pages missing OG images

### Full SEO Checker

The workflow uses a Python script that:
1. Crawls the website starting from the provided URL
2. Checks all links on each page for broken URLs (4xx or 5xx status codes)
3. Checks each page for the `<meta property="og:image">` tag
4. Checks each page for `<title>` tag and validates length (30-60 characters recommended)
5. Checks each page for `<meta name="description">` tag and validates length (50-160 characters recommended)
6. Checks each page for `<link rel="canonical">` tag
7. Checks each page for `lang` attribute in `<html>` tag
8. Creates a comprehensive GitHub issue with all findings grouped by:
   - SEO issues (missing or improperly sized meta tags)
   - Broken links (grouped by the page they were found on)
9. Includes SEO best practices in the report

## Requirements

- Python 3.11+
- Dependencies listed in `requirements.txt`:
  - requests
  - beautifulsoup4
  - urllib3

## Configuration

All workflows have these default settings:
- Maximum pages to crawl: 100 (prevents infinite crawling)
- Request timeout: 10 seconds
- Delay between requests: 0.1 seconds (respectful crawling)

To modify these, edit the constants in the respective Python scripts:
- `scripts/check_links.py` for dead link checking
- `scripts/check_og_images.py` for OG image checking
- `scripts/check_full_seo.py` for full SEO checking

## Permissions

All workflows require:
- `contents: read` - to checkout the repository
- `issues: write` - to create issues for broken links or missing OG images

## License

See [LICENSE](LICENSE) file for details.