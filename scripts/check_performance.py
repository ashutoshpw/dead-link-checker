#!/usr/bin/env python3
"""
Performance Metric Tracker Script
Loads a webpage using Playwright (Chromium) and analyzes performance metrics.
Creates a GitHub issue with the performance report.
"""

import os
import sys
import json
import time
import math
import requests
from urllib.parse import urlparse
from datetime import datetime

# Configuration
WEBSITE_URL = os.environ.get('WEBSITE_URL', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPOSITORY = os.environ.get('GITHUB_REPOSITORY', '')
REQUEST_TIMEOUT = 60000  # 60 seconds for page load
NETWORK_IDLE_DELAY = 2000  # 2 seconds to wait after network idle
OBSERVER_TIMEOUT = 500  # Timeout for Performance Observer collection


class PerformanceTracker:
    """Performance Metric Tracker class"""
    
    def __init__(self, url):
        self.url = url
        self.browser = None
        self.page = None
        self.context = None
        self.resources = []
        self.metrics = {}
        self.issues = []
        self.grade = 'A'
        self.score = 100
        self.grade_color = '🟢'
        self.analysis = {}
    
    def init(self):
        """Initialize the browser and page"""
        from playwright.sync_api import sync_playwright
        
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        self.page = self.context.new_page()
        
        # Store request start times
        self.request_start_times = {}
        
        # Capture network requests
        self.page.on('request', self._on_request)
        self.page.on('response', self._on_response)
    
    def _on_request(self, request):
        """Handle request event"""
        self.request_start_times[request.url] = {
            'start_time': time.time() * 1000,
            'resource_type': request.resource_type,
            'method': request.method
        }
    
    def _on_response(self, response):
        """Handle response event"""
        url = response.url
        request_data = self.request_start_times.get(url)
        
        if request_data:
            end_time = time.time() * 1000
            headers = response.headers
            
            size = 0
            try:
                body = response.body()
                size = len(body)
            except Exception:
                size = int(headers.get('content-length', 0))
            
            self.resources.append({
                'url': url,
                'resource_type': request_data['resource_type'],
                'method': request_data['method'],
                'status': response.status,
                'start_time': request_data['start_time'],
                'end_time': end_time,
                'duration': end_time - request_data['start_time'],
                'size': size,
                'content_type': headers.get('content-type', 'unknown'),
                'cache_control': headers.get('cache-control', ''),
                'content_encoding': headers.get('content-encoding', 'none'),
                'is_third_party': self._is_third_party(url)
            })
    
    def _is_third_party(self, resource_url):
        """Check if a URL is from a third-party domain"""
        try:
            page_host = urlparse(self.url).netloc
            resource_host = urlparse(resource_url).netloc
            return page_host != resource_host
        except Exception:
            return False
    
    def load_page(self):
        """Load the page and capture metrics"""
        print(f"Loading page: {self.url}")
        start_time = time.time() * 1000
        
        try:
            self.page.goto(self.url, wait_until='networkidle', timeout=REQUEST_TIMEOUT)
            
            # Wait a bit more for any late-loading resources
            self.page.wait_for_timeout(NETWORK_IDLE_DELAY)
            
            load_time = time.time() * 1000 - start_time
            print(f"Page loaded in {int(load_time)}ms")
            
            # Collect performance metrics
            self.collect_metrics()
            self.analyze_performance()
            
        except Exception as e:
            print(f"Error loading page: {e}")
            raise
    
    def collect_metrics(self):
        """Collect Core Web Vitals and other performance metrics"""
        # Get navigation timing data
        navigation_timing = self.page.evaluate('''() => {
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
        }''')
        
        # Get paint timing (FCP)
        paint_timing = self.page.evaluate('''() => {
            const entries = performance.getEntriesByType('paint');
            const fcp = entries.find(e => e.name === 'first-contentful-paint');
            const fp = entries.find(e => e.name === 'first-paint');
            return {
                firstPaint: fp ? fp.startTime : null,
                firstContentfulPaint: fcp ? fcp.startTime : null
            };
        }''')
        
        # Get LCP using PerformanceObserver
        lcp = self.page.evaluate(f'''() => {{
            return new Promise((resolve) => {{
                let lcpValue = 0;
                const observer = new PerformanceObserver((list) => {{
                    const entries = list.getEntries();
                    for (const entry of entries) {{
                        if (entry.startTime > lcpValue) {{
                            lcpValue = entry.startTime;
                        }}
                    }}
                }});
                
                try {{
                    observer.observe({{ type: 'largest-contentful-paint', buffered: true }});
                }} catch {{
                    // LCP not supported
                }}
                
                setTimeout(() => {{
                    observer.disconnect();
                    resolve(lcpValue);
                }}, {OBSERVER_TIMEOUT});
            }});
        }}''')
        
        # Get CLS using PerformanceObserver
        cls = self.page.evaluate(f'''() => {{
            return new Promise((resolve) => {{
                let clsValue = 0;
                const observer = new PerformanceObserver((list) => {{
                    for (const entry of list.getEntries()) {{
                        if (!entry.hadRecentInput) {{
                            clsValue += entry.value;
                        }}
                    }}
                }});
                
                try {{
                    observer.observe({{ type: 'layout-shift', buffered: true }});
                }} catch {{
                    // CLS not supported
                }}
                
                setTimeout(() => {{
                    observer.disconnect();
                    resolve(clsValue);
                }}, {OBSERVER_TIMEOUT});
            }});
        }}''')
        
        # Get Long Tasks for TBT calculation
        long_tasks = self.page.evaluate(f'''() => {{
            return new Promise((resolve) => {{
                const tasks = [];
                const observer = new PerformanceObserver((list) => {{
                    for (const entry of list.getEntries()) {{
                        tasks.push({{
                            startTime: entry.startTime,
                            duration: entry.duration
                        }});
                    }}
                }});
                
                try {{
                    observer.observe({{ type: 'longtask', buffered: true }});
                }} catch {{
                    // Long tasks not supported
                }}
                
                setTimeout(() => {{
                    observer.disconnect();
                    resolve(tasks);
                }}, {OBSERVER_TIMEOUT});
            }});
        }}''')
        
        # Calculate TBT (Total Blocking Time)
        tbt = 0
        for task in long_tasks:
            if task['duration'] > 50:
                tbt += task['duration'] - 50
        
        # Estimate TTI (Time to Interactive)
        tti = 0
        if navigation_timing:
            tti = max(
                navigation_timing.get('domContentLoaded', 0),
                paint_timing.get('firstContentfulPaint', 0) or 0,
                long_tasks[-1]['startTime'] + long_tasks[-1]['duration'] if long_tasks else 0
            )
        
        # Store metrics
        self.metrics = {
            # Navigation timing
            'ttfb': int(navigation_timing.get('ttfb', 0)) if navigation_timing else 0,
            'redirect_time': int(navigation_timing.get('redirectTime', 0)) if navigation_timing else 0,
            'dns_lookup_time': int(navigation_timing.get('dnsLookupTime', 0)) if navigation_timing else 0,
            'tcp_connect_time': int(navigation_timing.get('tcpConnectTime', 0)) if navigation_timing else 0,
            'ssl_time': int(navigation_timing.get('sslTime', 0)) if navigation_timing else 0,
            'response_time': int(navigation_timing.get('responseTime', 0)) if navigation_timing else 0,
            
            # Paint timing
            'first_paint': int(paint_timing.get('firstPaint', 0) or 0),
            'first_contentful_paint': int(paint_timing.get('firstContentfulPaint', 0) or 0),
            
            # Core Web Vitals
            'largest_contentful_paint': int(lcp),
            'cumulative_layout_shift': round(cls, 3),
            'total_blocking_time': int(tbt),
            
            # Additional timing
            'dom_interactive': int(navigation_timing.get('domInteractive', 0)) if navigation_timing else 0,
            'dom_content_loaded': int(navigation_timing.get('domContentLoaded', 0)) if navigation_timing else 0,
            'load_event_end': int(navigation_timing.get('loadEventEnd', 0)) if navigation_timing else 0,
            'time_to_interactive': int(tti),
            
            # Size metrics
            'total_transfer_size': navigation_timing.get('transferSize', 0) if navigation_timing else 0
        }
        
        print('Collected performance metrics')
    
    def analyze_performance(self):
        """Analyze performance and identify issues"""
        # Analyze resources
        total_size = sum(r['size'] for r in self.resources)
        total_requests = len(self.resources)
        
        # Count by resource type
        by_type = {}
        for resource in self.resources:
            rt = resource['resource_type']
            if rt not in by_type:
                by_type[rt] = {'count': 0, 'size': 0}
            by_type[rt]['count'] += 1
            by_type[rt]['size'] += resource['size']
        
        # Count third-party resources
        third_party_resources = [r for r in self.resources if r['is_third_party']]
        third_party_size = sum(r['size'] for r in third_party_resources)
        
        # Analyze caching
        uncached_resources = [r for r in self.resources if 
            not r['cache_control'] or 
            'no-cache' in r['cache_control'] or 
            'no-store' in r['cache_control']
        ]
        
        # Analyze compression
        uncompressed_resources = [r for r in self.resources if
            r['size'] > 1000 and
            r['content_encoding'] == 'none' and
            ('text' in r['content_type'] or 
             'javascript' in r['content_type'] or 
             'json' in r['content_type'] or
             'css' in r['content_type'])
        ]
        
        # Analyze large images
        large_images = [r for r in self.resources if
            r['resource_type'] == 'image' and r['size'] > 100000
        ]
        
        # Store analysis data
        self.analysis = {
            'total_size': total_size,
            'total_requests': total_requests,
            'by_type': by_type,
            'third_party_count': len(third_party_resources),
            'third_party_size': third_party_size,
            'uncached_count': len(uncached_resources),
            'uncompressed_count': len(uncompressed_resources),
            'large_images_count': len(large_images),
            'large_images': large_images
        }
        
        # Identify issues and recommendations
        self._identify_issues()
        
        # Calculate performance grade
        self._calculate_grade()
        
        print('Analyzed performance data')
    
    def _identify_issues(self):
        """Identify performance issues and generate recommendations"""
        # LCP thresholds
        if self.metrics['largest_contentful_paint'] > 4000:
            self.issues.append({
                'severity': 'high',
                'category': 'Core Web Vitals',
                'title': 'Poor Largest Contentful Paint (LCP)',
                'description': f"LCP is {self.metrics['largest_contentful_paint']}ms (should be < 2500ms)",
                'recommendation': 'Optimize largest content element, consider lazy loading, compress images, and improve server response time.'
            })
        elif self.metrics['largest_contentful_paint'] > 2500:
            self.issues.append({
                'severity': 'medium',
                'category': 'Core Web Vitals',
                'title': 'Needs Improvement: Largest Contentful Paint (LCP)',
                'description': f"LCP is {self.metrics['largest_contentful_paint']}ms (should be < 2500ms)",
                'recommendation': 'Consider optimizing images, reducing render-blocking resources, and improving server response time.'
            })
        
        # TBT thresholds
        if self.metrics['total_blocking_time'] > 600:
            self.issues.append({
                'severity': 'high',
                'category': 'Core Web Vitals',
                'title': 'Poor Total Blocking Time (TBT)',
                'description': f"TBT is {self.metrics['total_blocking_time']}ms (should be < 200ms)",
                'recommendation': 'Break up long JavaScript tasks, defer non-critical scripts, and minimize main-thread work.'
            })
        elif self.metrics['total_blocking_time'] > 200:
            self.issues.append({
                'severity': 'medium',
                'category': 'Core Web Vitals',
                'title': 'Needs Improvement: Total Blocking Time (TBT)',
                'description': f"TBT is {self.metrics['total_blocking_time']}ms (should be < 200ms)",
                'recommendation': 'Consider breaking up long JavaScript tasks and deferring non-critical scripts.'
            })
        
        # CLS thresholds
        if self.metrics['cumulative_layout_shift'] > 0.25:
            self.issues.append({
                'severity': 'high',
                'category': 'Core Web Vitals',
                'title': 'Poor Cumulative Layout Shift (CLS)',
                'description': f"CLS is {self.metrics['cumulative_layout_shift']} (should be < 0.1)",
                'recommendation': 'Add size attributes to images and videos, avoid inserting content above existing content, and use CSS transforms for animations.'
            })
        elif self.metrics['cumulative_layout_shift'] > 0.1:
            self.issues.append({
                'severity': 'medium',
                'category': 'Core Web Vitals',
                'title': 'Needs Improvement: Cumulative Layout Shift (CLS)',
                'description': f"CLS is {self.metrics['cumulative_layout_shift']} (should be < 0.1)",
                'recommendation': 'Consider adding explicit size attributes to images and videos to prevent layout shifts.'
            })
        
        # TTFB
        if self.metrics['ttfb'] > 800:
            self.issues.append({
                'severity': 'medium',
                'category': 'Server',
                'title': 'Slow Time to First Byte (TTFB)',
                'description': f"TTFB is {self.metrics['ttfb']}ms (should be < 800ms)",
                'recommendation': 'Optimize server configuration, use a CDN, reduce server-side processing time, and consider caching.'
            })
        
        # FCP
        if self.metrics['first_contentful_paint'] > 1800:
            self.issues.append({
                'severity': 'medium',
                'category': 'Rendering',
                'title': 'Slow First Contentful Paint (FCP)',
                'description': f"FCP is {self.metrics['first_contentful_paint']}ms (should be < 1800ms)",
                'recommendation': 'Eliminate render-blocking resources, minify CSS, and defer non-critical CSS.'
            })
        
        # Total page size
        if self.analysis['total_size'] > 5000000:
            self.issues.append({
                'severity': 'high',
                'category': 'Resources',
                'title': 'Very Large Page Size',
                'description': f"Total page size is {self._format_bytes(self.analysis['total_size'])} (should be < 3MB ideally)",
                'recommendation': 'Compress and optimize images, minify CSS/JS, enable text compression, and remove unused code.'
            })
        elif self.analysis['total_size'] > 3000000:
            self.issues.append({
                'severity': 'medium',
                'category': 'Resources',
                'title': 'Large Page Size',
                'description': f"Total page size is {self._format_bytes(self.analysis['total_size'])} (should be < 3MB ideally)",
                'recommendation': 'Consider optimizing images and minifying resources.'
            })
        
        # Too many requests
        if self.analysis['total_requests'] > 100:
            self.issues.append({
                'severity': 'medium',
                'category': 'Resources',
                'title': 'Too Many HTTP Requests',
                'description': f"{self.analysis['total_requests']} requests (should be < 50 ideally)",
                'recommendation': 'Combine CSS and JavaScript files, use CSS sprites, and lazy load images.'
            })
        
        # Uncompressed resources
        if self.analysis['uncompressed_count'] > 0:
            self.issues.append({
                'severity': 'medium',
                'category': 'Compression',
                'title': 'Uncompressed Text Resources',
                'description': f"{self.analysis['uncompressed_count']} text-based resources are not compressed",
                'recommendation': 'Enable Gzip or Brotli compression on your server for text-based resources.'
            })
        
        # Large images
        if self.analysis['large_images_count'] > 0:
            self.issues.append({
                'severity': 'medium',
                'category': 'Images',
                'title': 'Large Images Detected',
                'description': f"{self.analysis['large_images_count']} images are larger than 100KB",
                'recommendation': 'Compress images, use modern formats (WebP, AVIF), and implement responsive images.'
            })
        
        # Third-party scripts impact
        if self.analysis['third_party_size'] > 500000:
            self.issues.append({
                'severity': 'medium',
                'category': 'Third-Party',
                'title': 'Heavy Third-Party Scripts',
                'description': f"Third-party resources total {self._format_bytes(self.analysis['third_party_size'])} ({self.analysis['third_party_count']} requests)",
                'recommendation': 'Audit third-party scripts, lazy load non-critical ones, and consider self-hosting critical assets.'
            })
        
        # Caching issues
        if self.analysis['uncached_count'] > 10:
            self.issues.append({
                'severity': 'low',
                'category': 'Caching',
                'title': 'Resources Without Proper Caching',
                'description': f"{self.analysis['uncached_count']} resources lack proper cache headers",
                'recommendation': 'Set appropriate Cache-Control headers for static resources.'
            })
    
    def _calculate_grade(self):
        """Calculate overall performance grade"""
        score = 100
        
        # LCP scoring
        if self.metrics['largest_contentful_paint'] > 4000:
            score -= 25
        elif self.metrics['largest_contentful_paint'] > 2500:
            score -= 10
        
        # TBT scoring
        if self.metrics['total_blocking_time'] > 600:
            score -= 25
        elif self.metrics['total_blocking_time'] > 200:
            score -= 10
        
        # CLS scoring
        if self.metrics['cumulative_layout_shift'] > 0.25:
            score -= 20
        elif self.metrics['cumulative_layout_shift'] > 0.1:
            score -= 8
        
        # Page size scoring
        if self.analysis['total_size'] > 5000000:
            score -= 15
        elif self.analysis['total_size'] > 3000000:
            score -= 8
        
        # Request count scoring
        if self.analysis['total_requests'] > 100:
            score -= 10
        elif self.analysis['total_requests'] > 50:
            score -= 5
        
        # TTFB scoring
        if self.metrics['ttfb'] > 800:
            score -= 10
        
        # Convert score to grade
        if score >= 90:
            self.grade = 'A'
            self.grade_color = '🟢'
        elif score >= 80:
            self.grade = 'B'
            self.grade_color = '🟢'
        elif score >= 70:
            self.grade = 'C'
            self.grade_color = '🟡'
        elif score >= 60:
            self.grade = 'D'
            self.grade_color = '🟠'
        else:
            self.grade = 'F'
            self.grade_color = '🔴'
        
        self.score = max(0, min(100, score))
    
    def _format_bytes(self, bytes_val):
        """Format bytes to human-readable string"""
        if bytes_val == 0:
            return '0 Bytes'
        k = 1024
        sizes = ['Bytes', 'KB', 'MB', 'GB']
        i = int(math.floor(math.log(bytes_val) / math.log(k)))
        return f"{round(bytes_val / (k ** i), 2)} {sizes[i]}"
    
    def _format_time(self, ms):
        """Format milliseconds to human-readable string"""
        if ms < 1000:
            return f"{ms}ms"
        return f"{ms / 1000:.2f}s"
    
    def generate_waterfall_chart(self):
        """Generate ASCII waterfall chart"""
        if not self.resources:
            return 'No resources captured.'
        
        # Sort resources by start time
        sorted_resources = sorted(self.resources, key=lambda r: r['start_time'])
        
        # Find the baseline and max end time
        base_time = sorted_resources[0]['start_time']
        max_end_time = max(r['end_time'] for r in sorted_resources)
        total_duration = max_end_time - base_time
        
        # Limit to first 30 resources
        display_resources = sorted_resources[:30]
        
        chart_width = 50
        chart = '```\n'
        chart += 'WATERFALL CHART (first 30 resources)\n'
        chart += '═' * 80 + '\n'
        chart += 'Resource'.ljust(40) + ' │ Timeline\n'
        chart += '─' * 40 + '─┼' + '─' * (chart_width + 5) + '\n'
        
        for resource in display_resources:
            # Truncate URL for display
            try:
                parsed = urlparse(resource['url'])
                display_url = parsed.path[:35] or '/'
                if len(display_url) > 35:
                    display_url = display_url[:32] + '...'
            except Exception:
                display_url = resource['url'][:35]
            
            # Calculate bar position and length
            if total_duration > 0:
                start_offset = ((resource['start_time'] - base_time) / total_duration) * chart_width
                bar_length = max(1, (resource['duration'] / total_duration) * chart_width)
            else:
                start_offset = 0
                bar_length = 1
            
            # Choose bar character based on resource type
            bar_char = '█'
            if resource['resource_type'] == 'script':
                bar_char = '▓'
            elif resource['resource_type'] == 'stylesheet':
                bar_char = '▒'
            elif resource['resource_type'] == 'image':
                bar_char = '░'
            elif resource['resource_type'] == 'font':
                bar_char = '▄'
            
            padding = ' ' * int(round(start_offset))
            bar = bar_char * max(1, int(round(bar_length)))
            duration = f" {int(resource['duration'])}ms"
            
            chart += display_url.ljust(40) + ' │ ' + padding + bar + duration + '\n'
        
        chart += '═' * 80 + '\n'
        chart += 'Legend: █ Document  ▓ Script  ▒ Stylesheet  ░ Image  ▄ Font\n'
        chart += '```'
        
        return chart
    
    def create_github_issue(self):
        """Create GitHub issue with performance report"""
        if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
            print('GitHub token or repository not configured, skipping issue creation')
            return
        
        title = f"Performance Report: {self.grade_color} Grade {self.grade} - {self.url}"
        
        body = f"## 📊 Performance Report\n\n"
        body += f"**URL:** {self.url}\n"
        body += f"**Performance Grade:** {self.grade_color} **{self.grade}** (Score: {self.score}/100)\n\n"
        body += f"---\n\n"
        
        # Core Web Vitals Section
        body += f"## 🎯 Core Web Vitals\n\n"
        body += f"| Metric | Value | Status |\n"
        body += f"|--------|-------|--------|\n"
        
        # LCP
        lcp_status = '🟢 Good'
        if self.metrics['largest_contentful_paint'] > 4000:
            lcp_status = '🔴 Poor'
        elif self.metrics['largest_contentful_paint'] > 2500:
            lcp_status = '🟡 Needs Improvement'
        body += f"| Largest Contentful Paint (LCP) | {self._format_time(self.metrics['largest_contentful_paint'])} | {lcp_status} |\n"
        
        # TBT
        tbt_status = '🟢 Good'
        if self.metrics['total_blocking_time'] > 600:
            tbt_status = '🔴 Poor'
        elif self.metrics['total_blocking_time'] > 200:
            tbt_status = '🟡 Needs Improvement'
        body += f"| Total Blocking Time (TBT) | {self._format_time(self.metrics['total_blocking_time'])} | {tbt_status} |\n"
        
        # CLS
        cls_status = '🟢 Good'
        if self.metrics['cumulative_layout_shift'] > 0.25:
            cls_status = '🔴 Poor'
        elif self.metrics['cumulative_layout_shift'] > 0.1:
            cls_status = '🟡 Needs Improvement'
        body += f"| Cumulative Layout Shift (CLS) | {self.metrics['cumulative_layout_shift']} | {cls_status} |\n"
        
        body += f"\n"
        
        # Additional Timing Metrics
        body += f"## ⏱️ Timing Metrics\n\n"
        body += f"| Metric | Value |\n"
        body += f"|--------|-------|\n"
        body += f"| Time to First Byte (TTFB) | {self._format_time(self.metrics['ttfb'])} |\n"
        body += f"| First Contentful Paint (FCP) | {self._format_time(self.metrics['first_contentful_paint'])} |\n"
        body += f"| Time to Interactive (TTI) | {self._format_time(self.metrics['time_to_interactive'])} |\n"
        body += f"| DOM Content Loaded | {self._format_time(self.metrics['dom_content_loaded'])} |\n"
        body += f"| Fully Loaded | {self._format_time(self.metrics['load_event_end'])} |\n"
        body += f"\n"
        
        # Network Overview
        body += f"## 🌐 Network Overview\n\n"
        body += f"| Metric | Value |\n"
        body += f"|--------|-------|\n"
        body += f"| Total Page Size | {self._format_bytes(self.analysis['total_size'])} |\n"
        body += f"| Total Requests | {self.analysis['total_requests']} |\n"
        body += f"| Third-Party Requests | {self.analysis['third_party_count']} ({self._format_bytes(self.analysis['third_party_size'])}) |\n"
        body += f"\n"
        
        # Resource Breakdown
        body += f"### Resource Breakdown\n\n"
        body += f"| Type | Count | Size |\n"
        body += f"|------|-------|------|\n"
        for rtype, data in self.analysis['by_type'].items():
            body += f"| {rtype} | {data['count']} | {self._format_bytes(data['size'])} |\n"
        body += f"\n"
        
        # Connection Timing
        body += f"## 🔌 Connection Timing\n\n"
        body += f"| Phase | Duration |\n"
        body += f"|-------|----------|\n"
        body += f"| DNS Lookup | {self._format_time(self.metrics['dns_lookup_time'])} |\n"
        body += f"| TCP Connect | {self._format_time(self.metrics['tcp_connect_time'])} |\n"
        body += f"| SSL/TLS | {self._format_time(self.metrics['ssl_time'])} |\n"
        body += f"| Redirect | {self._format_time(self.metrics['redirect_time'])} |\n"
        body += f"| Response | {self._format_time(self.metrics['response_time'])} |\n"
        body += f"\n"
        
        # Waterfall Chart
        body += f"## 📈 Waterfall Chart\n\n"
        body += self.generate_waterfall_chart()
        body += f"\n\n"
        
        # Issues and Recommendations
        if self.issues:
            body += f"## ⚠️ Issues & Recommendations\n\n"
            
            # Group by severity
            high_issues = [i for i in self.issues if i['severity'] == 'high']
            medium_issues = [i for i in self.issues if i['severity'] == 'medium']
            low_issues = [i for i in self.issues if i['severity'] == 'low']
            
            if high_issues:
                body += f"### 🔴 High Priority\n\n"
                for issue in high_issues:
                    body += f"#### {issue['title']}\n"
                    body += f"**Category:** {issue['category']}\n\n"
                    body += f"{issue['description']}\n\n"
                    body += f"**Recommendation:** {issue['recommendation']}\n\n"
            
            if medium_issues:
                body += f"### 🟡 Medium Priority\n\n"
                for issue in medium_issues:
                    body += f"#### {issue['title']}\n"
                    body += f"**Category:** {issue['category']}\n\n"
                    body += f"{issue['description']}\n\n"
                    body += f"**Recommendation:** {issue['recommendation']}\n\n"
            
            if low_issues:
                body += f"### 🟢 Low Priority\n\n"
                for issue in low_issues:
                    body += f"#### {issue['title']}\n"
                    body += f"**Category:** {issue['category']}\n\n"
                    body += f"{issue['description']}\n\n"
                    body += f"**Recommendation:** {issue['recommendation']}\n\n"
        else:
            body += f"## ✅ No Major Issues Found\n\n"
            body += f"Great job! Your page is performing well across all measured metrics.\n\n"
        
        body += f"---\n"
        body += f"*Generated by Performance Metric Tracker on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC*"
        
        # Create the issue
        api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/issues"
        headers = {
            'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'title': title,
            'body': body,
            'labels': ['performance', 'web-vitals']
        }
        
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            issue_data = response.json()
            print(f"Created issue #{issue_data['number']}: {issue_data['html_url']}")
        except Exception as e:
            print(f"Error creating GitHub issue: {e}")
    
    def report_results(self):
        """Report results to console"""
        print('\n' + '=' * 60)
        print('PERFORMANCE METRIC RESULTS')
        print('=' * 60)
        print(f"URL: {self.url}")
        print(f"Grade: {self.grade} (Score: {self.score}/100)")
        print('')
        print('Core Web Vitals:')
        print(f"  LCP: {self._format_time(self.metrics['largest_contentful_paint'])}")
        print(f"  TBT: {self._format_time(self.metrics['total_blocking_time'])}")
        print(f"  CLS: {self.metrics['cumulative_layout_shift']}")
        print('')
        print('Timing Metrics:')
        print(f"  TTFB: {self._format_time(self.metrics['ttfb'])}")
        print(f"  FCP: {self._format_time(self.metrics['first_contentful_paint'])}")
        print(f"  TTI: {self._format_time(self.metrics['time_to_interactive'])}")
        print(f"  Fully Loaded: {self._format_time(self.metrics['load_event_end'])}")
        print('')
        print('Network:')
        print(f"  Total Size: {self._format_bytes(self.analysis['total_size'])}")
        print(f"  Total Requests: {self.analysis['total_requests']}")
        print(f"  Third-Party: {self.analysis['third_party_count']} requests ({self._format_bytes(self.analysis['third_party_size'])})")
        print('')
        print(f"Issues Found: {len(self.issues)}")
        
        if self.issues:
            for issue in self.issues:
                icon = '🔴' if issue['severity'] == 'high' else '🟡' if issue['severity'] == 'medium' else '🟢'
                print(f"  {icon} {issue['title']}")
        
        print('=' * 60)
        
        # Return true if grade is C or better
        return self.score >= 70
    
    def close(self):
        """Clean up resources"""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()


def main():
    if not WEBSITE_URL:
        print('Error: WEBSITE_URL environment variable is not set')
        sys.exit(1)
    
    # Validate URL format
    if not WEBSITE_URL.startswith(('http://', 'https://')):
        print('Error: Invalid URL format. URL must start with http:// or https://')
        sys.exit(1)
    
    print(f"Starting Performance Metric Tracker for: {WEBSITE_URL}")
    print('=' * 60)
    
    tracker = PerformanceTracker(WEBSITE_URL)
    
    try:
        tracker.init()
        tracker.load_page()
        success = tracker.report_results()
        tracker.create_github_issue()
        tracker.close()
        
        if not success:
            print('\n❌ FAILED: Performance issues detected!')
            print('=' * 60)
            sys.exit(1)
        else:
            print('\n✅ SUCCESS: Performance is acceptable!')
            print('=' * 60)
    except Exception as e:
        print(f"Error: {e}")
        tracker.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
