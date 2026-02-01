# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
HTML Report Generator for RAG Evaluation

Generates a comprehensive HTML report with:
- Executive summary with pass rate
- Metrics dashboard with gauge charts
- Latency statistics
- Language and category breakdowns
- Detailed results table with expandable rows
- Failure analysis

Usage:
    from scripts.eval.report import generate_html_report

    generate_html_report(results, summary, "test_results.html")
"""

import json
import logging
from pathlib import Path
from typing import List
from datetime import datetime

from .models import EvaluationResult, EvaluationSummary

logger = logging.getLogger(__name__)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hotel RAG Evaluation Report</title>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --warning: #ca8a04;
            --danger: #dc2626;
            --bg-primary: #ffffff;
            --bg-secondary: #f8fafc;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --border: #e2e8f0;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        header {
            background: linear-gradient(135deg, var(--primary) 0%, #1d4ed8 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }

        header h1 {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }

        header .subtitle {
            opacity: 0.9;
            font-size: 1rem;
        }

        .card {
            background: var(--bg-primary);
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 1.5rem;
            overflow: hidden;
        }

        .card-header {
            padding: 1rem 1.5rem;
            border-bottom: 1px solid var(--border);
            font-weight: 600;
            font-size: 1.1rem;
        }

        .card-body {
            padding: 1.5rem;
        }

        /* Summary Grid */
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }

        .summary-item {
            text-align: center;
            padding: 1.5rem;
            background: var(--bg-secondary);
            border-radius: 8px;
        }

        .summary-item .value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
        }

        .summary-item .label {
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }

        .summary-item.success .value { color: var(--success); }
        .summary-item.danger .value { color: var(--danger); }
        .summary-item.warning .value { color: var(--warning); }

        /* Metrics Grid */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
        }

        .metric-card {
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 1.5rem;
        }

        .metric-card .name {
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .metric-bar {
            height: 8px;
            background: var(--border);
            border-radius: 4px;
            overflow: hidden;
            margin: 0.5rem 0;
        }

        .metric-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }

        .metric-bar-fill.success { background: var(--success); }
        .metric-bar-fill.warning { background: var(--warning); }
        .metric-bar-fill.danger { background: var(--danger); }

        .metric-score {
            font-size: 1.5rem;
            font-weight: 700;
        }

        /* Results Table */
        .results-table {
            width: 100%;
            border-collapse: collapse;
        }

        .results-table th {
            background: var(--bg-secondary);
            padding: 1rem;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid var(--border);
        }

        .results-table td {
            padding: 1rem;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
        }

        .results-table tr:hover {
            background: var(--bg-secondary);
        }

        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }

        .badge-pass {
            background: #dcfce7;
            color: var(--success);
        }

        .badge-fail {
            background: #fee2e2;
            color: var(--danger);
        }

        .badge-en {
            background: #dbeafe;
            color: var(--primary);
        }

        .badge-th {
            background: #fef3c7;
            color: #92400e;
        }

        /* Expandable Details */
        .details-row {
            display: none;
            background: var(--bg-secondary);
        }

        .details-row.show {
            display: table-row;
        }

        .details-content {
            padding: 1.5rem;
        }

        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }

        .details-section h4 {
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
            text-transform: uppercase;
        }

        .details-section pre {
            background: white;
            padding: 1rem;
            border-radius: 6px;
            font-size: 0.875rem;
            overflow-x: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }

        .expand-btn {
            background: none;
            border: none;
            color: var(--primary);
            cursor: pointer;
            font-size: 0.875rem;
        }

        .expand-btn:hover {
            text-decoration: underline;
        }

        /* Language/Category Stats */
        .stats-row {
            display: flex;
            justify-content: space-between;
            padding: 0.75rem 0;
            border-bottom: 1px solid var(--border);
        }

        .stats-row:last-child {
            border-bottom: none;
        }

        .stats-label {
            color: var(--text-secondary);
        }

        .stats-value {
            font-weight: 600;
        }

        /* Score indicators */
        .score-high { color: var(--success); }
        .score-medium { color: var(--warning); }
        .score-low { color: var(--danger); }

        /* Failure Analysis */
        .failure-item {
            padding: 1rem;
            background: #fff5f5;
            border-left: 4px solid var(--danger);
            margin-bottom: 1rem;
            border-radius: 0 6px 6px 0;
        }

        .failure-item .question {
            font-weight: 500;
            margin-bottom: 0.5rem;
        }

        .failure-item .reasons {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .details-grid {
                grid-template-columns: 1fr;
            }

            .container {
                padding: 1rem;
            }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>Hotel RAG Evaluation Report</h1>
            <div class="subtitle">Generated on {{ generated_at }}</div>
        </div>
    </header>

    <div class="container">
        <!-- Executive Summary -->
        <div class="card">
            <div class="card-header">Executive Summary</div>
            <div class="card-body">
                <div class="summary-grid">
                    <div class="summary-item">
                        <div class="value">{{ summary.total_tests }}</div>
                        <div class="label">Total Tests</div>
                    </div>
                    <div class="summary-item success">
                        <div class="value">{{ summary.passed_tests }}</div>
                        <div class="label">Passed</div>
                    </div>
                    <div class="summary-item danger">
                        <div class="value">{{ summary.failed_tests }}</div>
                        <div class="label">Failed</div>
                    </div>
                    <div class="summary-item {{ 'success' if summary.pass_rate >= 80 else 'warning' if summary.pass_rate >= 60 else 'danger' }}">
                        <div class="value">{{ "%.1f"|format(summary.pass_rate) }}%</div>
                        <div class="label">Pass Rate</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Metrics Dashboard -->
        <div class="card">
            <div class="card-header">Metrics Dashboard</div>
            <div class="card-body">
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="name">Faithfulness</div>
                        <div class="metric-score {{ get_score_class(summary.avg_faithfulness) }}">
                            {{ "%.2f"|format(summary.avg_faithfulness) }}
                        </div>
                        <div class="metric-bar">
                            <div class="metric-bar-fill {{ get_bar_class(summary.avg_faithfulness) }}"
                                 style="width: {{ summary.avg_faithfulness * 100 }}%"></div>
                        </div>
                        <small>Does the answer follow retrieved context?</small>
                    </div>
                    <div class="metric-card">
                        <div class="name">Context Recall</div>
                        <div class="metric-score {{ get_score_class(summary.avg_context_recall) }}">
                            {{ "%.2f"|format(summary.avg_context_recall) }}
                        </div>
                        <div class="metric-bar">
                            <div class="metric-bar-fill {{ get_bar_class(summary.avg_context_recall) }}"
                                 style="width: {{ summary.avg_context_recall * 100 }}%"></div>
                        </div>
                        <small>Did retrieval find the right documents?</small>
                    </div>
                    <div class="metric-card">
                        <div class="name">Answer Relevancy</div>
                        <div class="metric-score {{ get_score_class(summary.avg_answer_relevancy) }}">
                            {{ "%.2f"|format(summary.avg_answer_relevancy) }}
                        </div>
                        <div class="metric-bar">
                            <div class="metric-bar-fill {{ get_bar_class(summary.avg_answer_relevancy) }}"
                                 style="width: {{ summary.avg_answer_relevancy * 100 }}%"></div>
                        </div>
                        <small>Is the answer helpful to the user?</small>
                    </div>
                    <div class="metric-card">
                        <div class="name">Bilingual Helpfulness</div>
                        <div class="metric-score {{ get_score_class(summary.avg_helpfulness) }}">
                            {{ "%.2f"|format(summary.avg_helpfulness) }}
                        </div>
                        <div class="metric-bar">
                            <div class="metric-bar-fill {{ get_bar_class(summary.avg_helpfulness) }}"
                                 style="width: {{ summary.avg_helpfulness * 100 }}%"></div>
                        </div>
                        <small>Overall quality for Thai/English responses</small>
                    </div>
                </div>
            </div>
        </div>

        <!-- Latency & Breakdown -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
            <div class="card">
                <div class="card-header">Latency Statistics</div>
                <div class="card-body">
                    <div class="stats-row">
                        <span class="stats-label">Average</span>
                        <span class="stats-value">{{ "%.0f"|format(summary.avg_latency_ms) }} ms</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">P95</span>
                        <span class="stats-value">{{ "%.0f"|format(summary.p95_latency_ms) }} ms</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Min</span>
                        <span class="stats-value">{{ "%.0f"|format(summary.min_latency_ms) }} ms</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Max</span>
                        <span class="stats-value">{{ "%.0f"|format(summary.max_latency_ms) }} ms</span>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">Language Breakdown</div>
                <div class="card-body">
                    <div class="stats-row">
                        <span class="stats-label">English Pass Rate</span>
                        <span class="stats-value {{ 'score-high' if summary.english_pass_rate >= 80 else 'score-medium' if summary.english_pass_rate >= 60 else 'score-low' }}">
                            {{ "%.1f"|format(summary.english_pass_rate) }}%
                        </span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Thai Pass Rate</span>
                        <span class="stats-value {{ 'score-high' if summary.thai_pass_rate >= 80 else 'score-medium' if summary.thai_pass_rate >= 60 else 'score-low' }}">
                            {{ "%.1f"|format(summary.thai_pass_rate) }}%
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Category Breakdown -->
        <div class="card">
            <div class="card-header">Category Breakdown</div>
            <div class="card-body">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem;">
                    {% for category, rate in summary.category_pass_rates.items() %}
                    <div class="stats-row" style="background: var(--bg-secondary); padding: 1rem; border-radius: 8px; border-bottom: none;">
                        <span class="stats-label">{{ category|title }}</span>
                        <span class="stats-value {{ 'score-high' if rate >= 80 else 'score-medium' if rate >= 60 else 'score-low' }}">
                            {{ "%.1f"|format(rate) }}%
                        </span>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>

        <!-- Detailed Results -->
        <div class="card">
            <div class="card-header">Detailed Results</div>
            <div class="card-body" style="padding: 0;">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Question</th>
                            <th>Language</th>
                            <th>Category</th>
                            <th>Status</th>
                            <th>Scores</th>
                            <th>Latency</th>
                            <th></th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for result in results %}
                        <tr>
                            <td>{{ result.question_id }}</td>
                            <td style="max-width: 300px;">{{ result.question[:80] }}{% if result.question|length > 80 %}...{% endif %}</td>
                            <td><span class="badge badge-{{ result.language.value }}">{{ result.language.value|upper }}</span></td>
                            <td>{{ result.category.value|title }}</td>
                            <td><span class="badge badge-{{ 'pass' if result.passed else 'fail' }}">{{ 'Pass' if result.passed else 'Fail' }}</span></td>
                            <td>
                                <small>
                                    F: {{ "%.2f"|format(result.faithfulness_score) }} |
                                    C: {{ "%.2f"|format(result.context_recall_score) }} |
                                    A: {{ "%.2f"|format(result.answer_relevancy_score) }} |
                                    H: {{ "%.2f"|format(result.helpfulness_score) }}
                                </small>
                            </td>
                            <td>{{ "%.0f"|format(result.latency_ms) }} ms</td>
                            <td>
                                <button class="expand-btn" onclick="toggleDetails('{{ result.question_id }}')">
                                    Details
                                </button>
                            </td>
                        </tr>
                        <tr class="details-row" id="details-{{ result.question_id }}">
                            <td colspan="8">
                                <div class="details-content">
                                    <div class="details-grid">
                                        <div class="details-section">
                                            <h4>Actual Response</h4>
                                            <pre>{{ result.actual_output }}</pre>
                                        </div>
                                        <div class="details-section">
                                            <h4>Expected Response</h4>
                                            <pre>{{ result.expected_output }}</pre>
                                        </div>
                                    </div>
                                    {% if result.failure_reasons %}
                                    <div class="details-section" style="margin-top: 1rem;">
                                        <h4>Failure Reasons</h4>
                                        <ul>
                                            {% for reason in result.failure_reasons %}
                                            <li>{{ reason }}</li>
                                            {% endfor %}
                                        </ul>
                                    </div>
                                    {% endif %}
                                    <div class="details-section" style="margin-top: 1rem;">
                                        <h4>Retrieval Context</h4>
                                        <pre>{{ result.retrieval_context|join(', ') if result.retrieval_context else 'No sources retrieved' }}</pre>
                                    </div>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Failure Analysis -->
        {% if failed_results %}
        <div class="card">
            <div class="card-header">Failure Analysis</div>
            <div class="card-body">
                {% for result in failed_results %}
                <div class="failure-item">
                    <div class="question">{{ result.question_id }}: {{ result.question }}</div>
                    <div class="reasons">
                        {% for reason in result.failure_reasons %}
                        <div>{{ reason }}</div>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        {% endif %}
    </div>

    <script>
        function toggleDetails(id) {
            const row = document.getElementById('details-' + id);
            row.classList.toggle('show');
        }
    </script>
</body>
</html>
"""


def get_score_class(score: float) -> str:
    """Get CSS class based on score."""
    if score >= 0.8:
        return "score-high"
    elif score >= 0.6:
        return "score-medium"
    else:
        return "score-low"


def get_bar_class(score: float) -> str:
    """Get CSS class for progress bar based on score."""
    if score >= 0.7:
        return "success"
    elif score >= 0.5:
        return "warning"
    else:
        return "danger"


def generate_html_report(
    results: List[EvaluationResult],
    summary: EvaluationSummary,
    output_path: str = "test_results.html",
) -> str:
    """
    Generate HTML report from evaluation results.

    Args:
        results: List of evaluation results
        summary: Evaluation summary statistics
        output_path: Path to save HTML report

    Returns:
        Path to generated report
    """
    try:
        from jinja2 import Template
    except ImportError:
        logger.error("jinja2 is required for HTML report generation")
        raise ImportError("pip install jinja2")

    # Create template
    template = Template(HTML_TEMPLATE)

    # Get failed results for failure analysis
    failed_results = [r for r in results if not r.passed]

    # Render HTML
    html = template.render(
        summary=summary,
        results=results,
        failed_results=failed_results,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        get_score_class=get_score_class,
        get_bar_class=get_bar_class,
    )

    # Write to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"Report saved to: {output_path}")
    return str(output_file.absolute())


def generate_json_report(
    results: List[EvaluationResult],
    summary: EvaluationSummary,
    output_path: str = "test_results.json",
) -> str:
    """
    Generate JSON report from evaluation results.

    Args:
        results: List of evaluation results
        summary: Evaluation summary statistics
        output_path: Path to save JSON report

    Returns:
        Path to generated report
    """
    report_data = {
        "summary": summary.model_dump(),
        "results": [r.model_dump() for r in results],
        "generated_at": datetime.now().isoformat(),
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"JSON report saved to: {output_path}")
    return str(output_file.absolute())


if __name__ == "__main__":
    # Test template rendering with sample data
    from .models import Language, Category

    sample_results = [
        EvaluationResult(
            question_id="test_01",
            question="What time is breakfast?",
            language=Language.ENGLISH,
            category=Category.DINING,
            actual_output="Breakfast is served from 6:30 AM to 10:30 AM.",
            expected_output="Breakfast is served at The Grand Dining Room from 6:30 AM to 10:30 AM.",
            retrieval_context=["dining_services.md"],
            expected_context=["dining_services.md"],
            latency_ms=450.0,
            faithfulness_score=0.85,
            context_recall_score=0.90,
            answer_relevancy_score=0.88,
            helpfulness_score=0.82,
            passed=True,
            failure_reasons=[],
        ),
    ]

    sample_summary = EvaluationSummary(
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        pass_rate=100.0,
        avg_faithfulness=0.85,
        avg_context_recall=0.90,
        avg_answer_relevancy=0.88,
        avg_helpfulness=0.82,
        avg_latency_ms=450.0,
        p95_latency_ms=450.0,
        min_latency_ms=450.0,
        max_latency_ms=450.0,
        english_pass_rate=100.0,
        thai_pass_rate=0.0,
        category_pass_rates={"dining": 100.0},
    )

    generate_html_report(sample_results, sample_summary, "test_sample_report.html")
    print("Sample report generated: test_sample_report.html")
