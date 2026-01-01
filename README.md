# Dead Link Checker & SEO Checker

GitHub Action workflows that check websites for broken links, missing Open Graph images, comprehensive SEO issues, and performance metrics, automatically creating issues when problems are found.

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

### Performance Metric Tracker
- 🚀 Loads webpage in a real Chromium browser via Puppeteer
- 📊 Captures Core Web Vitals (LCP, TBT, CLS)
- ⏱️ Measures timing metrics (TTFB, FCP, TTI, fully loaded time)
- 🌐 Analyzes all network requests and resource loading
- 📈 Generates a waterfall chart showing resource timing
- 🔍 Evaluates performance best practices (compression, caching, image optimization)
- 📝 Creates a comprehensive GitHub issue with performance grade (A-F) and recommendations
- ✅ Passes if performance grade is C or better
- ❌ Fails if performance grade is D or F

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

### Performance Metric Tracker

#### Running the Workflow

1. Go to the "Actions" tab in your repository
2. Select "Check Performance" workflow
3. Click "Run workflow"
4. Enter the website URL (e.g., `https://example.com`)
5. Click "Run workflow"

The workflow will:
- Load the webpage in a headless Chromium browser
- Capture Core Web Vitals (LCP, TBT, CLS)
- Measure timing metrics (TTFB, FCP, TTI, fully loaded time)
- Analyze all network requests for waterfall chart
- Evaluate performance against best practices
- Create a comprehensive GitHub issue with performance grade and recommendations
- Pass (green) if performance grade is C or better
- Fail (red) if performance grade is D or F

#### Example

Input: `https://example.com`

The checker will:
1. Launch a headless Chromium browser
2. Navigate to `https://example.com`
3. Capture all resource requests and their timing
4. Measure Core Web Vitals using Performance Observer API
5. Analyze page size, request count, compression, caching
6. Calculate a performance grade (A-F)
7. Generate a waterfall chart showing resource loading timeline
8. Create a GitHub issue with the complete performance report

#### Metrics Measured

**Core Web Vitals:**
- **Largest Contentful Paint (LCP)** — How quickly the main content becomes visible (Good: < 2.5s)
- **Total Blocking Time (TBT)** — How long the page is unresponsive during load (Good: < 200ms)
- **Cumulative Layout Shift (CLS)** — Visual stability during load (Good: < 0.1)

**Timing Metrics:**
- Time to First Byte (TTFB)
- First Contentful Paint (FCP)
- Time to Interactive (TTI)
- DOM Content Loaded
- Fully Loaded Time

**Analysis:**
- Total page size and request count
- Resource breakdown by type
- Third-party script impact
- Compression (Gzip/Brotli) usage
- Cache header presence
- Large image detection

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

### Performance Metric Tracker

The workflow uses a Node.js script with Puppeteer that:
1. Launches a headless Chromium browser
2. Intercepts all network requests to capture resource timing
3. Navigates to the target URL and waits for network idle
4. Collects Core Web Vitals using the Performance Observer API:
   - LCP (Largest Contentful Paint)
   - TBT (Total Blocking Time) - calculated from Long Tasks
   - CLS (Cumulative Layout Shift)
5. Collects navigation timing data:
   - TTFB, FCP, TTI, DOM events, connection timing
6. Analyzes resources for:
   - Total size and request count
   - Resource type breakdown
   - Third-party script impact
   - Compression and caching
   - Large images
7. Calculates a performance grade (A-F) based on all metrics
8. Generates an ASCII waterfall chart
9. Creates a comprehensive GitHub issue with all findings and recommendations

## Requirements

### Python Scripts (Dead Link, OG Image, Full SEO Checker)
- Python 3.11+
- Dependencies listed in `requirements.txt`:
  - requests
  - beautifulsoup4
  - urllib3

### Node.js Scripts (Performance Metric Tracker)
- Node.js 20+
- Dependencies listed in `package.json`:
  - puppeteer

## Configuration

### Python Scripts

All Python-based workflows have these default settings:
- Maximum pages to crawl: 100 (prevents infinite crawling)
- Request timeout: 10 seconds
- Delay between requests: 0.1 seconds (respectful crawling)

To modify these, edit the constants in the respective Python scripts:
- `scripts/check_links.py` for dead link checking
- `scripts/check_og_images.py` for OG image checking
- `scripts/check_full_seo.py` for full SEO checking

### Performance Metric Tracker

The performance tracker has these default settings:
- Page load timeout: 60 seconds
- Viewport: 1920x1080

Performance grade thresholds (based on Google's recommendations):
- **LCP:** Good < 2500ms, Needs Improvement < 4000ms, Poor >= 4000ms
- **TBT:** Good < 200ms, Needs Improvement < 600ms, Poor >= 600ms
- **CLS:** Good < 0.1, Needs Improvement < 0.25, Poor >= 0.25

To modify these, edit the constants in `scripts/check_performance.js`.

## Permissions

All workflows require:
- `contents: read` - to checkout the repository
- `issues: write` - to create issues for broken links or missing OG images

## License

See [LICENSE](LICENSE) file for details.