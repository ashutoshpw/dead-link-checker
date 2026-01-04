# GitHub Copilot Instructions for Dead Link Checker

## Repository Overview

This repository provides GitHub Actions workflows for website quality checking:
- **Dead Link Checker**: Crawls websites and identifies broken links (404, 500, etc.)
- **OG Image Checker**: Verifies Open Graph image tags are present on all pages
- **Sitemap Checker**: Validates sitemap.xml and checks all URLs for accessibility
- **Full SEO Checker**: Comprehensive SEO validation including meta tags, titles, descriptions, and more
- **Performance Tracker**: Measures Core Web Vitals and performance metrics using Playwright

All checkers automatically create GitHub issues with detailed findings when problems are detected.

## Project Structure

```
.
├── .github/
│   └── workflows/          # GitHub Actions workflow definitions
│       ├── check-dead-links.yml
│       ├── check-og-images.yml
│       ├── check-sitemap.yml
│       ├── check-full-seo.yml
│       └── check-performance.yml
├── scripts/                # Python scripts that perform the actual checks
│   ├── check_links.py
│   ├── check_og_images.py
│   ├── check_sitemap.py
│   ├── check_full_seo.py
│   └── check_performance.py
├── requirements.txt        # Python dependencies
└── README.md              # User-facing documentation
```

## Code Conventions

### Python Style
- Use Python 3.11+ features
- Follow PEP 8 style guidelines
- Use docstrings for classes and complex functions (triple-quoted strings)
- Use descriptive variable names (e.g., `base_url`, `visited_pages`)
- Use ALL_CAPS for constants (e.g., `MAX_PAGES`, `REQUEST_TIMEOUT`)
- Prefer f-strings for string formatting
- Use `#!/usr/bin/env python3` shebang in script files

### Class Structure Pattern
All checker scripts follow this pattern:
1. Configuration constants at the top (using environment variables)
2. Main checker class with `__init__` method
3. Helper methods for URL normalization, validation, etc.
4. Main crawling/checking logic
5. GitHub issue creation logic
6. Script execution block at the bottom with `if __name__ == '__main__':`

### Error Handling
- Use try-except blocks for network requests
- Print informative error messages to stdout
- Exit with non-zero status code on failure (causes workflow to fail)
- Use `sys.exit(1)` for errors, `sys.exit(0)` for success

### Common Configuration
All scripts use these standard configurations:
- `MAX_PAGES = 100` - Prevents infinite crawling
- `REQUEST_TIMEOUT = 10` - 10-second timeout for HTTP requests
- `USER_AGENT` - Chrome user agent string
- Environment variables: `WEBSITE_URL`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`

## Dependencies

The project uses these core libraries:
- **requests** (>=2.31.0) - HTTP requests
- **beautifulsoup4** (>=4.12.0) - HTML parsing
- **urllib3** (>=2.6.0) - URL utilities
- **playwright** (>=1.40.0) - Browser automation for performance tracking

When adding new dependencies:
1. Add to `requirements.txt` with version constraint
2. Use `>=` for minimum version constraints (allows updates while ensuring minimum requirements)
3. Consider using `==` for exact versions only when reproducible builds are critical
4. Test that installation works: `pip install -r requirements.txt`

## GitHub Actions Workflows

### Workflow Pattern
All workflows follow this structure:
1. **Trigger**: `workflow_dispatch` with `website_url` input
2. **Permissions**: `contents: read`, `issues: write`
3. **Runner**: `ubuntu-latest`
4. **Steps**:
   - Checkout repository
   - Set up Python 3.11
   - Install dependencies from requirements.txt
   - Run Python script with environment variables (script exits with non-zero status on failure)
   - Display message on failure (using `if: failure()` condition)

### Environment Variables
Scripts receive these environment variables from workflows:
- `WEBSITE_URL`: The website to check (from workflow input)
- `GITHUB_TOKEN`: GitHub token for API access (from secrets)
- `GITHUB_REPOSITORY`: Current repository (from context)

## Testing and Validation

### Manual Testing
Since this is a GitHub Actions-based project without traditional unit tests:
1. Test workflows manually through GitHub UI (Actions → Run workflow)
2. Use test websites with known issues to verify detection
3. Check that GitHub issues are created correctly with proper formatting
4. Verify workflow passes/fails as expected

### Before Making Changes
1. Understand the existing code pattern
2. Check if similar functionality already exists
3. Maintain consistency with existing scripts

### After Making Changes
1. Test the specific workflow that was modified
2. Verify issue creation still works
3. Check that error handling works properly
4. Ensure changes don't break existing functionality

## Common Tasks

### Adding a New Checker
1. Create new Python script in `scripts/` following the class pattern
2. Create corresponding workflow file in `.github/workflows/`
3. Add any new dependencies to `requirements.txt`
4. Update `README.md` with new checker documentation
5. Test manually through GitHub Actions UI

### Modifying Existing Checker
1. Locate the Python script in `scripts/`
2. Make minimal changes maintaining existing patterns
3. Test the modified workflow manually
4. Update README.md if behavior changes

### Updating Dependencies
1. Modify `requirements.txt` with new versions
2. Test that installation works
3. Verify all workflows still function correctly

## Best Practices

### When Making Changes
- **Minimize changes**: Make the smallest possible modification to achieve the goal
- **Preserve patterns**: Follow existing code structure and style
- **Test manually**: Run workflows through GitHub Actions UI
- **Update docs**: If behavior changes, update README.md
- **Don't break working code**: Avoid modifying code that isn't related to the task

### Code Quality
- Keep functions focused on a single responsibility
- Use meaningful variable and function names
- Add comments only when necessary to explain complex logic
- Print informative messages during execution (helps with debugging)
- Handle edge cases (empty responses, timeouts, malformed HTML)

### GitHub Issue Creation
- Use clear, descriptive issue titles
- Group related findings together
- Include URLs and specific details in issue body
- Use markdown formatting for readability
- Close/update existing issues when appropriate

## Resources

- **GitHub API**: Issues are created via GitHub REST API
- **BeautifulSoup**: HTML parsing - use `html.parser` parser
- **Playwright**: For browser-based checks (performance tracker only)
- **URL Handling**: Use `urllib.parse` for URL operations

## Security Considerations

- Never commit secrets or tokens to the repository
- Use GitHub secrets for sensitive data
- Validate and sanitize URLs before processing
- Be respectful with crawling (delays between requests)
- Use reasonable timeouts to prevent hanging

## Notes for Copilot Coding Agent

- This repository doesn't have traditional unit tests; validation is through manual workflow execution
- All scripts are designed to be run in GitHub Actions environment
- Scripts should be idempotent and safe to re-run
- Focus on maintaining consistency with existing patterns
- When in doubt, follow the structure of existing checkers
