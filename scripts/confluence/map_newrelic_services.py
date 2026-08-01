#!/usr/bin/env python3
"""Map NewRelic APM services to Confluence documentation using page browsing."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from common import bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map NewRelic services to Confluence documentation"
    )
    parser.add_argument(
        "--service-list",
        type=str,
        default="data/newrelic_apm_service_names_1679802.txt",
        help="Path to NewRelic service names file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/confluence_service_knowledge_map.json",
        help="Output JSON file path (local only, not committed)",
    )
    return parser.parse_args()


def build_missing_service_list_message(service_list_path: Path) -> str:
    """Build actionable guidance when the local service list is missing."""
    return (
        f"Service list file not found: {service_list_path}\n"
        "The data/ folder is intentionally excluded from repository sync.\n"
        "Generate local service data before this step:\n"
        "  1) @NewRelic, export current APM service names for account 1679802\n"
        "  2) Save outputs under data/ as:\n"
        "     - newrelic_apm_service_names_1679802.txt\n"
        "     - newrelic_apm_service_names_1679802.csv\n"
        "     - newrelic_apm_services_1679802.json\n"
        "  3) Re-run scripts/confluence/map_newrelic_services.py"
    )


def load_services(service_list_path: str) -> List[str]:
    """Load service names from file."""
    path = Path(service_list_path)
    if not path.exists():
        raise FileNotFoundError(build_missing_service_list_message(path))
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def browse_space_pages(
    client: Any, limit: int = 100
) -> List[Dict[str, Any]]:
    """Browse pages from configured Confluence spaces."""
    all_pages = []

    for space_key in client.config.space_keys:
        try:
            print(f"  Browsing {space_key} space (limit {limit})...")
            pages = client.list_space_pages(limit=limit, space_key=space_key)
            print(f"    Found {len(pages)} pages")
            all_pages.extend(pages)
        except Exception as e:
            print(f"  Warning: Failed to browse {space_key}: {e}")

    return all_pages


def extract_services_from_pages(
    pages: List[Dict[str, Any]], services: Set[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Map services mentioned in pages."""
    service_pages: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for page in pages:
        page_id = str(page.get("id", ""))
        title = str(page.get("title", "Untitled"))
        space_key = ((page.get("space") or {}).get("key", ""))

        # Check if page title contains service references
        title_lower = title.lower()
        for service in services:
            service_lower = service.lower()
            if (
                service_lower in title_lower
                or title_lower in service_lower
                or service.replace("cds.", "") in title_lower
                or service.replace("-", " ") in title_lower
            ):
                service_pages[service].append(
                    {
                        "page_id": page_id,
                        "page_title": title,
                        "space_key": space_key,
                        "match_type": "title",
                    }
                )

    return service_pages


def extract_team_ownership(text: str) -> Optional[str]:
    """Extract team/owner information from text."""
    patterns = [
        r"[Oo]wned by\s+([A-Za-z\s&]+?)(?:\s*\||\.|\s*$)",
        r"[Tt]eam:\s*([A-Za-z\s&]+?)(?:\s*\||\.|\s*$)",
        r"[Oo]wner:\s*([A-Za-z\s&]+?)(?:\s*\||\.|\s*$)",
        r"[Rr]esponsible team:\s*([A-Za-z\s&]+?)(?:\s*\||\.|\s*$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            team = match.group(1).strip()
            if team and len(team) < 100:
                return team

    return None


def extract_business_domain(text: str, service_name: str) -> Optional[str]:
    """Extract business domain/capability from text and service name."""
    domain_keywords = {
        "cart": "Shopping Cart & Commerce",
        "checkout": "Checkout & Payment",
        "product": "Product Information",
        "search": "Search & Discovery",
        "order": "Order Management",
        "fulfillment": "Fulfillment & Shipping",
        "loyalty": "Customer Loyalty",
        "profile": "Customer Profile",
        "auth": "Authentication & Authorization",
        "inventory": "Inventory Management",
        "pricing": "Pricing & Promotion",
        "dms": "Distributed Merchandise System",
        "availability": "Availability Management",
        "shipping": "Shipping & Logistics",
        "payment": "Payment Processing",
        "integration": "Third-party Integration",
        "notification": "Customer Notifications",
        "rfid": "RFID & Asset Tracking",
        "recommendation": "Product Recommendations",
        "personalization": "User Personalization",
    }

    service_lower = service_name.lower()
    for keyword, domain in domain_keywords.items():
        if keyword in service_lower:
            return domain

    text_lower = text.lower()
    for keyword, domain in domain_keywords.items():
        if keyword in text_lower:
            return domain

    return None


def extract_integration_patterns(text: str) -> List[str]:
    """Extract integration patterns from text."""
    patterns = []

    if re.search(r"(?i)(rest|http|api)", text):
        patterns.append("REST API")
    if re.search(r"(?i)(kafka|event|stream|pub.?sub)", text):
        patterns.append("Event Stream")
    if re.search(r"(?i)grpc", text):
        patterns.append("gRPC")
    if re.search(r"(?i)(database|sql|nosql)", text):
        patterns.append("Database")
    if re.search(r"(?i)(message|queue|amq)", text):
        patterns.append("Message Queue")
    if re.search(r"(?i)(cache|redis)", text):
        patterns.append("Cache Layer")

    return patterns


def build_service_knowledge_map(
    services: List[str],
    service_pages: Dict[str, List[Dict[str, Any]]],
    client: Any = None,
) -> Dict[str, Any]:
    """Build comprehensive service knowledge map."""

    services_documented = []
    service_domains: Dict[str, List[str]] = defaultdict(list)
    team_mappings: Dict[str, List[str]] = defaultdict(list)
    gaps_identified: List[Dict[str, str]] = []

    service_details: Dict[str, Dict[str, Any]] = {}

    all_services_set = set(services)

    for service in services:
        pages = service_pages.get(service, [])

        service_detail = {
            "name": service,
            "documented_in_pages": [p["page_id"] for p in pages],
            "team_ownership": None,
            "business_domain": None,
            "service_type": None,
            "documentation_confidence": 0.0,
            "dependencies": [],
            "dependents": [],
            "integration_patterns": [],
            "notes": [],
        }

        if pages:
            # Extract metadata from documented pages
            service_detail["documentation_confidence"] = min(
                1.0, len(pages) * 0.4
            )  # 0.4 per page found

            # Try to fetch and extract detailed info from first page
            if client and pages:
                try:
                    page = client.get_page(page_id=pages[0]["page_id"])
                    page_body = page.get("body", {}).get("storage", {}).get("value", "")
                    page_title = page.get("title", "")

                    # Extract text version
                    text = re.sub(r"<[^>]+>", " ", page_body)
                    text = re.sub(r"\s+", " ", text).strip()

                    service_detail["team_ownership"] = extract_team_ownership(text)
                    service_detail["business_domain"] = extract_business_domain(
                        text, service
                    )
                    service_detail["integration_patterns"] = extract_integration_patterns(
                        text
                    )

                except Exception as e:
                    # Silently continue - page details are optional
                    pass

            services_documented.append(service)

        else:
            # Documentation gap
            gaps_identified.append(
                {
                    "service": service,
                    "reason": "No Confluence documentation found",
                    "severity": "high",
                }
            )

        # Categorize by domain
        if service_detail["business_domain"]:
            service_domains[service_detail["business_domain"]].append(service)

        # Track team ownership
        if service_detail["team_ownership"]:
            team_mappings[service_detail["team_ownership"]].append(service)

        service_details[service] = service_detail

    # Build service relationships from page titles and content
    service_relationships = []

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "analysis_summary": {
            "total_services_analyzed": len(services),
            "services_documented": len(services_documented),
            "documentation_coverage_percent": (
                len(services_documented) / len(services) * 100 if services else 0
            ),
            "unique_teams": len(team_mappings),
            "business_domains": len(service_domains),
            "dependencies_mapped": len(service_relationships),
            "documentation_gaps": len(gaps_identified),
        },
        "services_documented": services_documented,
        "service_details": service_details,
        "service_domains": dict(service_domains),
        "service_relationships": service_relationships,
        "team_mappings": dict(team_mappings),
        "gaps_identified": gaps_identified,
        "metrics": {
            "high_confidence_services": sum(
                1 for d in service_details.values() if d["documentation_confidence"] >= 0.7
            ),
            "medium_confidence_services": sum(
                1
                for d in service_details.values()
                if 0.3 <= d["documentation_confidence"] < 0.7
            ),
            "low_confidence_services": sum(
                1
                for d in service_details.values()
                if d["documentation_confidence"] < 0.3
            ),
        },
    }


def main() -> None:
    args = parse_args()
    bootstrap()

    from confluence_client import ConfluenceClient  # pylint: disable=import-error

    print("=" * 80)
    print("NewRelic Services to Confluence Mapping")
    print("=" * 80)

    # Load services
    print(f"\n[1/5] Loading services from {args.service_list}...")
    services = load_services(args.service_list)
    print(f"  Loaded {len(services)} services")

    # Initialize Confluence client
    print("\n[2/5] Connecting to Confluence...")
    try:
        client = ConfluenceClient.from_env()
        print(f"  Connected to {client.config.host}")
        print(f"  Searching spaces: {', '.join(client.config.space_keys)}")
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    # Browse space pages
    print(f"\n[3/5] Browsing Confluence pages...")
    all_pages = browse_space_pages(client, limit=100)
    print(f"  Total pages found: {len(all_pages)}")

    # Extract services mentioned in pages
    print(f"\n[4/5] Extracting service documentation...")
    service_pages = extract_services_from_pages(all_pages, set(services))
    print(f"  Found documentation for {len(service_pages)} services")

    # Build knowledge map
    print(f"\n[5/5] Building service knowledge map...")
    knowledge_map = build_service_knowledge_map(services, service_pages, client)

    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(knowledge_map, f, indent=2)

    print(f"  Saved to {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    summary = knowledge_map["analysis_summary"]
    print(f"Total Services Analyzed:     {summary['total_services_analyzed']}")
    print(f"Services with Documentation: {summary['services_documented']}")
    print(f"Documentation Coverage:      {summary['documentation_coverage_percent']:.1f}%")
    print(f"Unique Teams:                {summary['unique_teams']}")
    print(f"Business Domains:            {summary['business_domains']}")
    print(f"Dependencies Mapped:         {summary['dependencies_mapped']}")
    print(f"Documentation Gaps:          {summary['documentation_gaps']}")

    print("\n" + "=" * 80)
    print("CONFIDENCE METRICS")
    print("=" * 80)

    metrics = knowledge_map["metrics"]
    print(f"High Confidence (>=70%):     {metrics['high_confidence_services']} services")
    print(f"Medium Confidence (30-69%):  {metrics['medium_confidence_services']} services")
    print(f"Low Confidence (<30%):       {metrics['low_confidence_services']} services")

    if knowledge_map["team_mappings"]:
        print("\n" + "=" * 80)
        print("TOP TEAMS BY SERVICE COUNT")
        print("=" * 80)
        sorted_teams = sorted(
            knowledge_map["team_mappings"].items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
        for team, team_services in sorted_teams[:5]:
            print(f"{team:40} {len(team_services):3} services")

    if knowledge_map["service_domains"]:
        print("\n" + "=" * 80)
        print("BUSINESS DOMAINS COVERAGE")
        print("=" * 80)
        sorted_domains = sorted(
            knowledge_map["service_domains"].items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
        for domain, domain_services in sorted_domains[:5]:
            print(f"{domain:40} {len(domain_services):3} services")

    if knowledge_map["gaps_identified"]:
        print("\n" + "=" * 80)
        print("TOP DOCUMENTATION GAPS (first 10)")
        print("=" * 80)
        for i, gap in enumerate(knowledge_map["gaps_identified"][:10], 1):
            print(f"{i:2}. {gap['service']}: {gap['reason']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
