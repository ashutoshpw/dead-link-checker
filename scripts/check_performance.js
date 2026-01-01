#!/usr/bin/env node
/**
 * Performance Metric Tracker Script
 * Loads a webpage using Puppeteer and analyzes performance metrics.
 * Creates a GitHub issue with the performance report.
 */

const puppeteer = require('puppeteer');
const https = require('https');
const http = require('http');
const { URL } = require('url');

// Configuration
const WEBSITE_URL = process.env.WEBSITE_URL || '';
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || '';
const GITHUB_REPOSITORY = process.env.GITHUB_REPOSITORY || '';
const REQUEST_TIMEOUT = 60000; // 60 seconds for page load
const NETWORK_IDLE_DELAY = 2000; // 2 seconds to wait after network idle
const OBSERVER_TIMEOUT = 500; // Timeout for Performance Observer collection

/**
 * Performance Metric Tracker class
 */
class PerformanceTracker {
    constructor(url) {
        this.url = url;
        this.browser = null;
        this.page = null;
        this.resources = [];
        this.metrics = {};
        this.issues = [];
        this.grade = 'A';
    }

    /**
     * Initialize the browser and page
     */
    async init() {
        this.browser = await puppeteer.launch({
            headless: true,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        });
        this.page = await this.browser.newPage();

        // Set viewport
        await this.page.setViewport({ width: 1920, height: 1080 });

        // Enable request interception to capture all resources
        await this.page.setRequestInterception(true);

        // Store request start times
        const requestStartTimes = new Map();

        this.page.on('request', (request) => {
            requestStartTimes.set(request.url(), {
                startTime: Date.now(),
                resourceType: request.resourceType(),
                method: request.method()
            });
            request.continue();
        });

        this.page.on('response', async (response) => {
            const url = response.url();
            const requestData = requestStartTimes.get(url);

            if (requestData) {
                const endTime = Date.now();
                const headers = response.headers();

                let size = 0;
                try {
                    const buffer = await response.buffer();
                    size = buffer.length;
                } catch {
                    // Some responses may not have a body
                    size = parseInt(headers['content-length'] || '0', 10);
                }

                this.resources.push({
                    url,
                    resourceType: requestData.resourceType,
                    method: requestData.method,
                    status: response.status(),
                    startTime: requestData.startTime,
                    endTime,
                    duration: endTime - requestData.startTime,
                    size,
                    contentType: headers['content-type'] || 'unknown',
                    cacheControl: headers['cache-control'] || '',
                    contentEncoding: headers['content-encoding'] || 'none',
                    isThirdParty: this.isThirdParty(url)
                });
            }
        });
    }

    /**
     * Check if a URL is from a third-party domain
     */
    isThirdParty(resourceUrl) {
        try {
            const pageHost = new URL(this.url).host;
            const resourceHost = new URL(resourceUrl).host;
            return pageHost !== resourceHost;
        } catch {
            return false;
        }
    }

    /**
     * Load the page and capture metrics
     */
    async loadPage() {
        console.log(`Loading page: ${this.url}`);
        const startTime = Date.now();

        try {
            await this.page.goto(this.url, {
                waitUntil: 'networkidle2',
                timeout: REQUEST_TIMEOUT
            });

            // Wait a bit more for any late-loading resources
            await new Promise(resolve => setTimeout(resolve, NETWORK_IDLE_DELAY));

            const loadTime = Date.now() - startTime;
            console.log(`Page loaded in ${loadTime}ms`);

            // Collect performance metrics
            await this.collectMetrics();
            await this.analyzePerformance();

        } catch (error) {
            console.error(`Error loading page: ${error.message}`);
            throw error;
        }
    }

    /**
     * Collect Core Web Vitals and other performance metrics
     */
    async collectMetrics() {
        // Get navigation timing data
        const navigationTiming = await this.page.evaluate(() => {
            const timing = performance.getEntriesByType('navigation')[0];
            if (!timing) return null;
            return {
                startTime: timing.startTime,
                redirectTime: timing.redirectEnd - timing.redirectStart,
                dnsLookupTime: timing.domainLookupEnd - timing.domainLookupStart,
                tcpConnectTime: timing.connectEnd - timing.connectStart,
                sslTime: timing.secureConnectionStart > 0 
                    ? timing.connectEnd - timing.secureConnectionStart 
                    : 0,
                ttfb: timing.responseStart - timing.requestStart,
                responseTime: timing.responseEnd - timing.responseStart,
                domInteractive: timing.domInteractive,
                domContentLoaded: timing.domContentLoadedEventEnd,
                loadEventEnd: timing.loadEventEnd,
                transferSize: timing.transferSize || 0,
                encodedBodySize: timing.encodedBodySize || 0,
                decodedBodySize: timing.decodedBodySize || 0
            };
        });

        // Get paint timing (FCP)
        const paintTiming = await this.page.evaluate(() => {
            const entries = performance.getEntriesByType('paint');
            const fcp = entries.find(e => e.name === 'first-contentful-paint');
            const fp = entries.find(e => e.name === 'first-paint');
            return {
                firstPaint: fp ? fp.startTime : null,
                firstContentfulPaint: fcp ? fcp.startTime : null
            };
        });

        // Get LCP using PerformanceObserver
        const lcp = await this.page.evaluate((timeout) => {
            return new Promise((resolve) => {
                let lcpValue = 0;
                const observer = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    for (const entry of entries) {
                        if (entry.startTime > lcpValue) {
                            lcpValue = entry.startTime;
                        }
                    }
                });
                
                try {
                    observer.observe({ type: 'largest-contentful-paint', buffered: true });
                } catch {
                    // LCP not supported
                }
                
                // Give it some time to collect entries
                setTimeout(() => {
                    observer.disconnect();
                    resolve(lcpValue);
                }, timeout);
            });
        }, OBSERVER_TIMEOUT);

        // Get CLS using PerformanceObserver
        const cls = await this.page.evaluate((timeout) => {
            return new Promise((resolve) => {
                let clsValue = 0;
                const observer = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    }
                });
                
                try {
                    observer.observe({ type: 'layout-shift', buffered: true });
                } catch {
                    // CLS not supported
                }
                
                setTimeout(() => {
                    observer.disconnect();
                    resolve(clsValue);
                }, timeout);
            });
        }, OBSERVER_TIMEOUT);

        // Get Long Tasks for TBT calculation
        const longTasks = await this.page.evaluate((timeout) => {
            return new Promise((resolve) => {
                const tasks = [];
                const observer = new PerformanceObserver((list) => {
                    for (const entry of list.getEntries()) {
                        tasks.push({
                            startTime: entry.startTime,
                            duration: entry.duration
                        });
                    }
                });
                
                try {
                    observer.observe({ type: 'longtask', buffered: true });
                } catch {
                    // Long tasks not supported
                }
                
                setTimeout(() => {
                    observer.disconnect();
                    resolve(tasks);
                }, timeout);
            });
        }, OBSERVER_TIMEOUT);

        // Calculate TBT (Total Blocking Time) - sum of blocking time for each long task
        // A task is "blocking" if it takes more than 50ms, and the blocking portion is duration - 50ms
        let tbt = 0;
        for (const task of longTasks) {
            if (task.duration > 50) {
                tbt += task.duration - 50;
            }
        }

        // Estimate TTI (Time to Interactive) - simplified version
        // TTI is typically the time at which the page is fully interactive
        const tti = navigationTiming 
            ? Math.max(
                navigationTiming.domContentLoaded || 0,
                paintTiming.firstContentfulPaint || 0,
                longTasks.length > 0 ? longTasks[longTasks.length - 1].startTime + longTasks[longTasks.length - 1].duration : 0
            )
            : 0;

        // Store metrics
        this.metrics = {
            // Navigation timing
            ttfb: navigationTiming ? Math.round(navigationTiming.ttfb) : 0,
            redirectTime: navigationTiming ? Math.round(navigationTiming.redirectTime) : 0,
            dnsLookupTime: navigationTiming ? Math.round(navigationTiming.dnsLookupTime) : 0,
            tcpConnectTime: navigationTiming ? Math.round(navigationTiming.tcpConnectTime) : 0,
            sslTime: navigationTiming ? Math.round(navigationTiming.sslTime) : 0,
            responseTime: navigationTiming ? Math.round(navigationTiming.responseTime) : 0,
            
            // Paint timing
            firstPaint: paintTiming.firstPaint ? Math.round(paintTiming.firstPaint) : 0,
            firstContentfulPaint: paintTiming.firstContentfulPaint ? Math.round(paintTiming.firstContentfulPaint) : 0,
            
            // Core Web Vitals
            largestContentfulPaint: Math.round(lcp),
            cumulativeLayoutShift: Math.round(cls * 1000) / 1000, // Round to 3 decimal places
            totalBlockingTime: Math.round(tbt),
            
            // Additional timing
            domInteractive: navigationTiming ? Math.round(navigationTiming.domInteractive) : 0,
            domContentLoaded: navigationTiming ? Math.round(navigationTiming.domContentLoaded) : 0,
            loadEventEnd: navigationTiming ? Math.round(navigationTiming.loadEventEnd) : 0,
            timeToInteractive: Math.round(tti),
            
            // Size metrics
            totalTransferSize: navigationTiming ? navigationTiming.transferSize : 0
        };

        console.log('Collected performance metrics');
    }

    /**
     * Analyze performance and identify issues
     */
    async analyzePerformance() {
        // Analyze resources
        const totalSize = this.resources.reduce((sum, r) => sum + r.size, 0);
        const totalRequests = this.resources.length;

        // Count by resource type
        const byType = {};
        for (const resource of this.resources) {
            if (!byType[resource.resourceType]) {
                byType[resource.resourceType] = { count: 0, size: 0 };
            }
            byType[resource.resourceType].count++;
            byType[resource.resourceType].size += resource.size;
        }

        // Count third-party resources
        const thirdPartyResources = this.resources.filter(r => r.isThirdParty);
        const thirdPartySize = thirdPartyResources.reduce((sum, r) => sum + r.size, 0);

        // Analyze caching
        const uncachedResources = this.resources.filter(r => 
            !r.cacheControl || 
            r.cacheControl.includes('no-cache') || 
            r.cacheControl.includes('no-store')
        );

        // Analyze compression
        const uncompressedResources = this.resources.filter(r =>
            r.size > 1000 && // Only for resources > 1KB
            r.contentEncoding === 'none' &&
            (r.contentType.includes('text') || 
             r.contentType.includes('javascript') || 
             r.contentType.includes('json') ||
             r.contentType.includes('css'))
        );

        // Analyze large images
        const largeImages = this.resources.filter(r =>
            r.resourceType === 'image' && r.size > 100000 // > 100KB
        );

        // Store analysis data
        this.analysis = {
            totalSize,
            totalRequests,
            byType,
            thirdPartyCount: thirdPartyResources.length,
            thirdPartySize,
            uncachedCount: uncachedResources.length,
            uncompressedCount: uncompressedResources.length,
            largeImagesCount: largeImages.length,
            largeImages
        };

        // Identify issues and recommendations
        this.identifyIssues();

        // Calculate performance grade
        this.calculateGrade();

        console.log('Analyzed performance data');
    }

    /**
     * Identify performance issues and generate recommendations
     */
    identifyIssues() {
        // Core Web Vitals thresholds (based on Google's recommendations)
        // LCP: Good < 2500ms, Needs Improvement < 4000ms, Poor >= 4000ms
        if (this.metrics.largestContentfulPaint > 4000) {
            this.issues.push({
                severity: 'high',
                category: 'Core Web Vitals',
                title: 'Poor Largest Contentful Paint (LCP)',
                description: `LCP is ${this.metrics.largestContentfulPaint}ms (should be < 2500ms)`,
                recommendation: 'Optimize largest content element, consider lazy loading, compress images, and improve server response time.'
            });
        } else if (this.metrics.largestContentfulPaint > 2500) {
            this.issues.push({
                severity: 'medium',
                category: 'Core Web Vitals',
                title: 'Needs Improvement: Largest Contentful Paint (LCP)',
                description: `LCP is ${this.metrics.largestContentfulPaint}ms (should be < 2500ms)`,
                recommendation: 'Consider optimizing images, reducing render-blocking resources, and improving server response time.'
            });
        }

        // TBT: Good < 200ms, Needs Improvement < 600ms, Poor >= 600ms
        if (this.metrics.totalBlockingTime > 600) {
            this.issues.push({
                severity: 'high',
                category: 'Core Web Vitals',
                title: 'Poor Total Blocking Time (TBT)',
                description: `TBT is ${this.metrics.totalBlockingTime}ms (should be < 200ms)`,
                recommendation: 'Break up long JavaScript tasks, defer non-critical scripts, and minimize main-thread work.'
            });
        } else if (this.metrics.totalBlockingTime > 200) {
            this.issues.push({
                severity: 'medium',
                category: 'Core Web Vitals',
                title: 'Needs Improvement: Total Blocking Time (TBT)',
                description: `TBT is ${this.metrics.totalBlockingTime}ms (should be < 200ms)`,
                recommendation: 'Consider breaking up long JavaScript tasks and deferring non-critical scripts.'
            });
        }

        // CLS: Good < 0.1, Needs Improvement < 0.25, Poor >= 0.25
        if (this.metrics.cumulativeLayoutShift > 0.25) {
            this.issues.push({
                severity: 'high',
                category: 'Core Web Vitals',
                title: 'Poor Cumulative Layout Shift (CLS)',
                description: `CLS is ${this.metrics.cumulativeLayoutShift} (should be < 0.1)`,
                recommendation: 'Add size attributes to images and videos, avoid inserting content above existing content, and use CSS transforms for animations.'
            });
        } else if (this.metrics.cumulativeLayoutShift > 0.1) {
            this.issues.push({
                severity: 'medium',
                category: 'Core Web Vitals',
                title: 'Needs Improvement: Cumulative Layout Shift (CLS)',
                description: `CLS is ${this.metrics.cumulativeLayoutShift} (should be < 0.1)`,
                recommendation: 'Consider adding explicit size attributes to images and videos to prevent layout shifts.'
            });
        }

        // TTFB: Good < 800ms
        if (this.metrics.ttfb > 800) {
            this.issues.push({
                severity: 'medium',
                category: 'Server',
                title: 'Slow Time to First Byte (TTFB)',
                description: `TTFB is ${this.metrics.ttfb}ms (should be < 800ms)`,
                recommendation: 'Optimize server configuration, use a CDN, reduce server-side processing time, and consider caching.'
            });
        }

        // FCP: Good < 1800ms
        if (this.metrics.firstContentfulPaint > 1800) {
            this.issues.push({
                severity: 'medium',
                category: 'Rendering',
                title: 'Slow First Contentful Paint (FCP)',
                description: `FCP is ${this.metrics.firstContentfulPaint}ms (should be < 1800ms)`,
                recommendation: 'Eliminate render-blocking resources, minify CSS, and defer non-critical CSS.'
            });
        }

        // Total page size
        if (this.analysis.totalSize > 5000000) { // > 5MB
            this.issues.push({
                severity: 'high',
                category: 'Resources',
                title: 'Very Large Page Size',
                description: `Total page size is ${this.formatBytes(this.analysis.totalSize)} (should be < 3MB ideally)`,
                recommendation: 'Compress and optimize images, minify CSS/JS, enable text compression, and remove unused code.'
            });
        } else if (this.analysis.totalSize > 3000000) { // > 3MB
            this.issues.push({
                severity: 'medium',
                category: 'Resources',
                title: 'Large Page Size',
                description: `Total page size is ${this.formatBytes(this.analysis.totalSize)} (should be < 3MB ideally)`,
                recommendation: 'Consider optimizing images and minifying resources.'
            });
        }

        // Too many requests
        if (this.analysis.totalRequests > 100) {
            this.issues.push({
                severity: 'medium',
                category: 'Resources',
                title: 'Too Many HTTP Requests',
                description: `${this.analysis.totalRequests} requests (should be < 50 ideally)`,
                recommendation: 'Combine CSS and JavaScript files, use CSS sprites, and lazy load images.'
            });
        }

        // Uncompressed resources
        if (this.analysis.uncompressedCount > 0) {
            this.issues.push({
                severity: 'medium',
                category: 'Compression',
                title: 'Uncompressed Text Resources',
                description: `${this.analysis.uncompressedCount} text-based resources are not compressed`,
                recommendation: 'Enable Gzip or Brotli compression on your server for text-based resources.'
            });
        }

        // Large images
        if (this.analysis.largeImagesCount > 0) {
            this.issues.push({
                severity: 'medium',
                category: 'Images',
                title: 'Large Images Detected',
                description: `${this.analysis.largeImagesCount} images are larger than 100KB`,
                recommendation: 'Compress images, use modern formats (WebP, AVIF), and implement responsive images.'
            });
        }

        // Third-party scripts impact
        if (this.analysis.thirdPartySize > 500000) { // > 500KB
            this.issues.push({
                severity: 'medium',
                category: 'Third-Party',
                title: 'Heavy Third-Party Scripts',
                description: `Third-party resources total ${this.formatBytes(this.analysis.thirdPartySize)} (${this.analysis.thirdPartyCount} requests)`,
                recommendation: 'Audit third-party scripts, lazy load non-critical ones, and consider self-hosting critical assets.'
            });
        }

        // Caching issues
        if (this.analysis.uncachedCount > 10) {
            this.issues.push({
                severity: 'low',
                category: 'Caching',
                title: 'Resources Without Proper Caching',
                description: `${this.analysis.uncachedCount} resources lack proper cache headers`,
                recommendation: 'Set appropriate Cache-Control headers for static resources.'
            });
        }
    }

    /**
     * Calculate overall performance grade
     */
    calculateGrade() {
        let score = 100;

        // Deduct points based on Core Web Vitals
        // LCP scoring
        if (this.metrics.largestContentfulPaint > 4000) {
            score -= 25;
        } else if (this.metrics.largestContentfulPaint > 2500) {
            score -= 10;
        }

        // TBT scoring
        if (this.metrics.totalBlockingTime > 600) {
            score -= 25;
        } else if (this.metrics.totalBlockingTime > 200) {
            score -= 10;
        }

        // CLS scoring
        if (this.metrics.cumulativeLayoutShift > 0.25) {
            score -= 20;
        } else if (this.metrics.cumulativeLayoutShift > 0.1) {
            score -= 8;
        }

        // Page size scoring
        if (this.analysis.totalSize > 5000000) {
            score -= 15;
        } else if (this.analysis.totalSize > 3000000) {
            score -= 8;
        }

        // Request count scoring
        if (this.analysis.totalRequests > 100) {
            score -= 10;
        } else if (this.analysis.totalRequests > 50) {
            score -= 5;
        }

        // TTFB scoring
        if (this.metrics.ttfb > 800) {
            score -= 10;
        }

        // Convert score to grade
        if (score >= 90) {
            this.grade = 'A';
            this.gradeColor = '🟢';
        } else if (score >= 80) {
            this.grade = 'B';
            this.gradeColor = '🟢';
        } else if (score >= 70) {
            this.grade = 'C';
            this.gradeColor = '🟡';
        } else if (score >= 60) {
            this.grade = 'D';
            this.gradeColor = '🟠';
        } else {
            this.grade = 'F';
            this.gradeColor = '🔴';
        }

        this.score = Math.max(0, Math.min(100, score));
    }

    /**
     * Format bytes to human-readable string
     */
    formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Format milliseconds to human-readable string
     */
    formatTime(ms) {
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    }

    /**
     * Generate ASCII waterfall chart
     */
    generateWaterfallChart() {
        if (this.resources.length === 0) return 'No resources captured.';

        // Sort resources by start time
        const sortedResources = [...this.resources].sort((a, b) => a.startTime - b.startTime);
        
        // Find the baseline (first request start time) and max end time
        const baseTime = sortedResources[0].startTime;
        const maxEndTime = Math.max(...sortedResources.map(r => r.endTime));
        const totalDuration = maxEndTime - baseTime;
        
        // Limit to first 30 resources for readability
        const displayResources = sortedResources.slice(0, 30);
        
        const chartWidth = 50;
        let chart = '```\n';
        chart += 'WATERFALL CHART (first 30 resources)\n';
        chart += '═'.repeat(80) + '\n';
        chart += 'Resource'.padEnd(40) + ' │ Timeline\n';
        chart += '─'.repeat(40) + '─┼' + '─'.repeat(chartWidth + 5) + '\n';

        for (const resource of displayResources) {
            // Truncate URL for display
            let displayUrl;
            try {
                const urlObj = new URL(resource.url);
                displayUrl = urlObj.pathname.slice(0, 35) || '/';
                if (displayUrl.length > 35) {
                    displayUrl = displayUrl.slice(0, 32) + '...';
                }
            } catch {
                displayUrl = resource.url.slice(0, 35);
            }
            
            // Calculate bar position and length
            const startOffset = ((resource.startTime - baseTime) / totalDuration) * chartWidth;
            const barLength = Math.max(1, (resource.duration / totalDuration) * chartWidth);
            
            // Choose bar character based on resource type
            let barChar = '█';
            if (resource.resourceType === 'script') barChar = '▓';
            else if (resource.resourceType === 'stylesheet') barChar = '▒';
            else if (resource.resourceType === 'image') barChar = '░';
            else if (resource.resourceType === 'font') barChar = '▄';
            
            const padding = ' '.repeat(Math.round(startOffset));
            const bar = barChar.repeat(Math.max(1, Math.round(barLength)));
            const duration = ` ${resource.duration}ms`;
            
            chart += displayUrl.padEnd(40) + ' │ ' + padding + bar + duration + '\n';
        }

        chart += '═'.repeat(80) + '\n';
        chart += 'Legend: █ Document  ▓ Script  ▒ Stylesheet  ░ Image  ▄ Font\n';
        chart += '```';

        return chart;
    }

    /**
     * Create GitHub issue with performance report
     */
    async createGitHubIssue() {
        if (!GITHUB_TOKEN || !GITHUB_REPOSITORY) {
            console.log('GitHub token or repository not configured, skipping issue creation');
            return;
        }

        const title = `Performance Report: ${this.gradeColor} Grade ${this.grade} - ${this.url}`;
        
        let body = `## 📊 Performance Report\n\n`;
        body += `**URL:** ${this.url}\n`;
        body += `**Performance Grade:** ${this.gradeColor} **${this.grade}** (Score: ${this.score}/100)\n\n`;
        body += `---\n\n`;

        // Core Web Vitals Section
        body += `## 🎯 Core Web Vitals\n\n`;
        body += `| Metric | Value | Status |\n`;
        body += `|--------|-------|--------|\n`;
        
        // LCP
        let lcpStatus = '🟢 Good';
        if (this.metrics.largestContentfulPaint > 4000) lcpStatus = '🔴 Poor';
        else if (this.metrics.largestContentfulPaint > 2500) lcpStatus = '🟡 Needs Improvement';
        body += `| Largest Contentful Paint (LCP) | ${this.formatTime(this.metrics.largestContentfulPaint)} | ${lcpStatus} |\n`;
        
        // TBT
        let tbtStatus = '🟢 Good';
        if (this.metrics.totalBlockingTime > 600) tbtStatus = '🔴 Poor';
        else if (this.metrics.totalBlockingTime > 200) tbtStatus = '🟡 Needs Improvement';
        body += `| Total Blocking Time (TBT) | ${this.formatTime(this.metrics.totalBlockingTime)} | ${tbtStatus} |\n`;
        
        // CLS
        let clsStatus = '🟢 Good';
        if (this.metrics.cumulativeLayoutShift > 0.25) clsStatus = '🔴 Poor';
        else if (this.metrics.cumulativeLayoutShift > 0.1) clsStatus = '🟡 Needs Improvement';
        body += `| Cumulative Layout Shift (CLS) | ${this.metrics.cumulativeLayoutShift} | ${clsStatus} |\n`;
        
        body += `\n`;

        // Additional Timing Metrics
        body += `## ⏱️ Timing Metrics\n\n`;
        body += `| Metric | Value |\n`;
        body += `|--------|-------|\n`;
        body += `| Time to First Byte (TTFB) | ${this.formatTime(this.metrics.ttfb)} |\n`;
        body += `| First Contentful Paint (FCP) | ${this.formatTime(this.metrics.firstContentfulPaint)} |\n`;
        body += `| Time to Interactive (TTI) | ${this.formatTime(this.metrics.timeToInteractive)} |\n`;
        body += `| DOM Content Loaded | ${this.formatTime(this.metrics.domContentLoaded)} |\n`;
        body += `| Fully Loaded | ${this.formatTime(this.metrics.loadEventEnd)} |\n`;
        body += `\n`;

        // Network Overview
        body += `## 🌐 Network Overview\n\n`;
        body += `| Metric | Value |\n`;
        body += `|--------|-------|\n`;
        body += `| Total Page Size | ${this.formatBytes(this.analysis.totalSize)} |\n`;
        body += `| Total Requests | ${this.analysis.totalRequests} |\n`;
        body += `| Third-Party Requests | ${this.analysis.thirdPartyCount} (${this.formatBytes(this.analysis.thirdPartySize)}) |\n`;
        body += `\n`;

        // Resource Breakdown
        body += `### Resource Breakdown\n\n`;
        body += `| Type | Count | Size |\n`;
        body += `|------|-------|------|\n`;
        for (const [type, data] of Object.entries(this.analysis.byType)) {
            body += `| ${type} | ${data.count} | ${this.formatBytes(data.size)} |\n`;
        }
        body += `\n`;

        // Connection Timing
        body += `## 🔌 Connection Timing\n\n`;
        body += `| Phase | Duration |\n`;
        body += `|-------|----------|\n`;
        body += `| DNS Lookup | ${this.formatTime(this.metrics.dnsLookupTime)} |\n`;
        body += `| TCP Connect | ${this.formatTime(this.metrics.tcpConnectTime)} |\n`;
        body += `| SSL/TLS | ${this.formatTime(this.metrics.sslTime)} |\n`;
        body += `| Redirect | ${this.formatTime(this.metrics.redirectTime)} |\n`;
        body += `| Response | ${this.formatTime(this.metrics.responseTime)} |\n`;
        body += `\n`;

        // Waterfall Chart
        body += `## 📈 Waterfall Chart\n\n`;
        body += this.generateWaterfallChart();
        body += `\n\n`;

        // Issues and Recommendations
        if (this.issues.length > 0) {
            body += `## ⚠️ Issues & Recommendations\n\n`;
            
            // Group by severity
            const highIssues = this.issues.filter(i => i.severity === 'high');
            const mediumIssues = this.issues.filter(i => i.severity === 'medium');
            const lowIssues = this.issues.filter(i => i.severity === 'low');
            
            if (highIssues.length > 0) {
                body += `### 🔴 High Priority\n\n`;
                for (const issue of highIssues) {
                    body += `#### ${issue.title}\n`;
                    body += `**Category:** ${issue.category}\n\n`;
                    body += `${issue.description}\n\n`;
                    body += `**Recommendation:** ${issue.recommendation}\n\n`;
                }
            }
            
            if (mediumIssues.length > 0) {
                body += `### 🟡 Medium Priority\n\n`;
                for (const issue of mediumIssues) {
                    body += `#### ${issue.title}\n`;
                    body += `**Category:** ${issue.category}\n\n`;
                    body += `${issue.description}\n\n`;
                    body += `**Recommendation:** ${issue.recommendation}\n\n`;
                }
            }
            
            if (lowIssues.length > 0) {
                body += `### 🟢 Low Priority\n\n`;
                for (const issue of lowIssues) {
                    body += `#### ${issue.title}\n`;
                    body += `**Category:** ${issue.category}\n\n`;
                    body += `${issue.description}\n\n`;
                    body += `**Recommendation:** ${issue.recommendation}\n\n`;
                }
            }
        } else {
            body += `## ✅ No Major Issues Found\n\n`;
            body += `Great job! Your page is performing well across all measured metrics.\n\n`;
        }

        body += `---\n`;
        body += `*Generated by Performance Metric Tracker on ${new Date().toISOString().replace('T', ' ').split('.')[0]} UTC*`;

        // Create the issue
        const [owner, repo] = GITHUB_REPOSITORY.split('/');
        const apiUrl = `https://api.github.com/repos/${GITHUB_REPOSITORY}/issues`;
        
        const payload = JSON.stringify({
            title: title,
            body: body,
            labels: ['performance', 'web-vitals']
        });

        return new Promise((resolve, reject) => {
            const options = {
                hostname: 'api.github.com',
                path: `/repos/${GITHUB_REPOSITORY}/issues`,
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${GITHUB_TOKEN}`,
                    'Accept': 'application/vnd.github.v3+json',
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(payload),
                    'User-Agent': 'Performance-Tracker'
                }
            };

            const req = https.request(options, (res) => {
                let data = '';
                res.on('data', chunk => { data += chunk; });
                res.on('end', () => {
                    if (res.statusCode >= 200 && res.statusCode < 300) {
                        const issueData = JSON.parse(data);
                        console.log(`Created issue #${issueData.number}: ${issueData.html_url}`);
                        resolve(issueData);
                    } else {
                        console.error(`Error creating GitHub issue: ${res.statusCode} ${data}`);
                        reject(new Error(`GitHub API error: ${res.statusCode}`));
                    }
                });
            });

            req.on('error', (error) => {
                console.error(`Error creating GitHub issue: ${error.message}`);
                reject(error);
            });

            req.write(payload);
            req.end();
        });
    }

    /**
     * Report results to console
     */
    reportResults() {
        console.log('\n' + '='.repeat(60));
        console.log('PERFORMANCE METRIC RESULTS');
        console.log('='.repeat(60));
        console.log(`URL: ${this.url}`);
        console.log(`Grade: ${this.grade} (Score: ${this.score}/100)`);
        console.log('');
        console.log('Core Web Vitals:');
        console.log(`  LCP: ${this.formatTime(this.metrics.largestContentfulPaint)}`);
        console.log(`  TBT: ${this.formatTime(this.metrics.totalBlockingTime)}`);
        console.log(`  CLS: ${this.metrics.cumulativeLayoutShift}`);
        console.log('');
        console.log('Timing Metrics:');
        console.log(`  TTFB: ${this.formatTime(this.metrics.ttfb)}`);
        console.log(`  FCP: ${this.formatTime(this.metrics.firstContentfulPaint)}`);
        console.log(`  TTI: ${this.formatTime(this.metrics.timeToInteractive)}`);
        console.log(`  Fully Loaded: ${this.formatTime(this.metrics.loadEventEnd)}`);
        console.log('');
        console.log('Network:');
        console.log(`  Total Size: ${this.formatBytes(this.analysis.totalSize)}`);
        console.log(`  Total Requests: ${this.analysis.totalRequests}`);
        console.log(`  Third-Party: ${this.analysis.thirdPartyCount} requests (${this.formatBytes(this.analysis.thirdPartySize)})`);
        console.log('');
        console.log('Issues Found: ' + this.issues.length);
        
        if (this.issues.length > 0) {
            for (const issue of this.issues) {
                const icon = issue.severity === 'high' ? '🔴' : issue.severity === 'medium' ? '🟡' : '🟢';
                console.log(`  ${icon} ${issue.title}`);
            }
        }
        
        console.log('='.repeat(60));
        
        // Return true if grade is C or better
        return this.score >= 70;
    }

    /**
     * Clean up resources
     */
    async close() {
        if (this.browser) {
            await this.browser.close();
        }
    }
}

/**
 * Main function
 */
async function main() {
    if (!WEBSITE_URL) {
        console.error('Error: WEBSITE_URL environment variable is not set');
        process.exit(1);
    }

    // Validate URL format
    if (!WEBSITE_URL.startsWith('http://') && !WEBSITE_URL.startsWith('https://')) {
        console.error('Error: Invalid URL format. URL must start with http:// or https://');
        process.exit(1);
    }

    console.log(`Starting Performance Metric Tracker for: ${WEBSITE_URL}`);
    console.log('='.repeat(60));

    const tracker = new PerformanceTracker(WEBSITE_URL);

    try {
        await tracker.init();
        await tracker.loadPage();
        const success = tracker.reportResults();
        await tracker.createGitHubIssue();
        await tracker.close();

        if (!success) {
            console.log('\n❌ FAILED: Performance issues detected!');
            console.log('='.repeat(60));
            process.exit(1);
        } else {
            console.log('\n✅ SUCCESS: Performance is acceptable!');
            console.log('='.repeat(60));
        }
    } catch (error) {
        console.error(`Error: ${error.message}`);
        await tracker.close();
        process.exit(1);
    }
}

main();
