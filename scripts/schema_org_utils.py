#!/usr/bin/env python3
"""
Shared helpers for detecting and validating Schema.org structured data.
"""

import json
from collections import Counter


def _empty_page_result():
    return {
        'has_schema': False,
        'blocks_found': 0,
        'valid_blocks': 0,
        'types_found': [],
        'issues': []
    }


def _append_issue(issues, issue_type, message, severity='high', block_index=None):
    issue = {
        'type': issue_type,
        'message': message,
        'severity': severity
    }
    if block_index is not None:
        issue['block_index'] = block_index
    issues.append(issue)


def _iter_schema_items(parsed_block):
    if isinstance(parsed_block, list):
        return parsed_block
    return [parsed_block]


def _extract_types(raw_type):
    if isinstance(raw_type, list):
        return [item for item in raw_type if isinstance(item, str) and item.strip()]
    if isinstance(raw_type, str) and raw_type.strip():
        return [raw_type]
    return []


def analyze_schema_org_from_soup(soup):
    """
    Inspect JSON-LD blocks and return a normalized validation summary.
    """
    result = _empty_page_result()
    schema_scripts = soup.find_all('script', attrs={'type': 'application/ld+json'})

    if not schema_scripts:
        return result

    result['has_schema'] = True
    result['blocks_found'] = len(schema_scripts)

    for index, script in enumerate(schema_scripts, start=1):
        raw_content = script.string if script.string is not None else script.get_text()
        if not raw_content or not raw_content.strip():
            _append_issue(
                result['issues'],
                'empty_json_ld',
                'Schema.org JSON-LD script is empty.',
                block_index=index
            )
            continue

        try:
            parsed_block = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            _append_issue(
                result['issues'],
                'invalid_json_ld',
                f'Invalid JSON-LD: {exc.msg} (line {exc.lineno}, column {exc.colno}).',
                block_index=index
            )
            continue

        if not isinstance(parsed_block, (dict, list)):
            _append_issue(
                result['issues'],
                'invalid_json_ld_shape',
                'Schema.org JSON-LD must be an object or array.',
                block_index=index
            )
            continue

        block_valid = True
        items = _iter_schema_items(parsed_block)
        if not items:
            _append_issue(
                result['issues'],
                'empty_json_ld_array',
                'Schema.org JSON-LD array is empty.',
                block_index=index
            )
            continue

        for item_position, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                block_valid = False
                _append_issue(
                    result['issues'],
                    'invalid_schema_item',
                    f'Item {item_position} in JSON-LD block must be an object.',
                    block_index=index
                )
                continue

            if '@context' not in item or not item.get('@context'):
                block_valid = False
                _append_issue(
                    result['issues'],
                    'missing_context',
                    f'Item {item_position} is missing @context.',
                    block_index=index
                )

            item_types = _extract_types(item.get('@type'))
            if not item_types:
                block_valid = False
                _append_issue(
                    result['issues'],
                    'missing_type',
                    f'Item {item_position} is missing @type.',
                    block_index=index
                )
            else:
                result['types_found'].extend(item_types)

        if block_valid:
            result['valid_blocks'] += 1

    result['types_found'] = sorted(set(result['types_found']))
    return result


def summarize_schema_results(page_results):
    """
    Build run-level summary data from per-page Schema.org results.
    """
    summary = {
        'pages_with_schema': 0,
        'pages_without_schema': [],
        'pages_with_issues': [],
        'total_blocks': 0,
        'valid_blocks': 0,
        'types_found': [],
        'type_counts': {}
    }

    type_counter = Counter()

    for url, result in page_results.items():
        summary['total_blocks'] += result['blocks_found']
        summary['valid_blocks'] += result['valid_blocks']

        if result['has_schema']:
            summary['pages_with_schema'] += 1
        else:
            summary['pages_without_schema'].append(url)

        if result['issues']:
            summary['pages_with_issues'].append(url)

        for schema_type in result['types_found']:
            type_counter[schema_type] += 1

    summary['pages_without_schema'].sort()
    summary['pages_with_issues'].sort()
    summary['types_found'] = sorted(type_counter.keys())
    summary['type_counts'] = dict(sorted(type_counter.items()))
    return summary
