#!/usr/bin/env python3

import os
import sys
import unittest

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scripts.schema_org_utils import analyze_schema_org_from_soup, summarize_schema_results


class SchemaOrgUtilsTests(unittest.TestCase):
    def test_valid_single_json_ld_block(self):
        soup = BeautifulSoup(
            """
            <html><head>
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Organization","name":"Acme"}
            </script>
            </head></html>
            """,
            'html.parser'
        )

        result = analyze_schema_org_from_soup(soup)

        self.assertTrue(result['has_schema'])
        self.assertEqual(result['blocks_found'], 1)
        self.assertEqual(result['valid_blocks'], 1)
        self.assertEqual(result['types_found'], ['Organization'])
        self.assertEqual(result['issues'], [])

    def test_malformed_json_ld_reports_issue(self):
        soup = BeautifulSoup(
            """
            <html><head>
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Organization",
            </script>
            </head></html>
            """,
            'html.parser'
        )

        result = analyze_schema_org_from_soup(soup)

        self.assertTrue(result['has_schema'])
        self.assertEqual(result['valid_blocks'], 0)
        self.assertEqual(result['issues'][0]['type'], 'invalid_json_ld')

    def test_missing_context_and_type_are_reported(self):
        soup = BeautifulSoup(
            """
            <html><head>
            <script type="application/ld+json">
            {"name":"Acme"}
            </script>
            </head></html>
            """,
            'html.parser'
        )

        result = analyze_schema_org_from_soup(soup)
        issue_types = {issue['type'] for issue in result['issues']}

        self.assertEqual(issue_types, {'missing_context', 'missing_type'})

    def test_summary_tracks_missing_schema_informationally(self):
        summary = summarize_schema_results(
            {
                'https://example.com/with-schema': {
                    'has_schema': True,
                    'blocks_found': 1,
                    'valid_blocks': 1,
                    'types_found': ['WebSite'],
                    'issues': []
                },
                'https://example.com/no-schema': {
                    'has_schema': False,
                    'blocks_found': 0,
                    'valid_blocks': 0,
                    'types_found': [],
                    'issues': []
                },
                'https://example.com/invalid-schema': {
                    'has_schema': True,
                    'blocks_found': 1,
                    'valid_blocks': 0,
                    'types_found': [],
                    'issues': [{'type': 'invalid_json_ld', 'message': 'broken'}]
                }
            }
        )

        self.assertEqual(summary['pages_with_schema'], 2)
        self.assertEqual(summary['pages_without_schema'], ['https://example.com/no-schema'])
        self.assertEqual(
            summary['pages_with_issues'],
            ['https://example.com/invalid-schema']
        )
        self.assertEqual(summary['types_found'], ['WebSite'])


if __name__ == '__main__':
    unittest.main()
