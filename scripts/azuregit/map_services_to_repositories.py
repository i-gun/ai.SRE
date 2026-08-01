#!/usr/bin/env python3
"""Map NewRelic APM services to Azure DevOps repositories."""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def load_services(services_file: Path) -> List[str]:
    """Load service names from text file."""
    services = []
    with open(services_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                services.append(line)
    return services


def load_repo_map(repo_map_file: Path) -> Dict[str, Any]:
    """Load repository map from JSON."""
    with open(repo_map_file, "r") as f:
        return json.load(f)


def flatten_repositories(repo_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten repository map into list with project context."""
    repos = []
    for project_name, repo_list in repo_map.get("projects", {}).items():
        for repo in repo_list:
            repos.append({**repo, "project": project_name})
    return repos


def normalize_name(name: str) -> str:
    """Normalize name for comparison."""
    return name.lower().replace("-", "").replace("_", "").replace(".", "")


def extract_tokens(name: str) -> Set[str]:
    """Extract meaningful tokens from a name."""
    # Split on common delimiters and convert to lowercase
    tokens = set()
    # Split on - and _ and .
    parts = re.split(r"[-_.]", name.lower())
    for part in parts:
        if part and len(part) > 1:  # Filter short parts
            tokens.add(part)
    return tokens


def similarity_ratio(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def strip_environment_suffix(name: str) -> str:
    """Remove environment suffixes from service name."""
    # Remove common environment suffixes
    suffixes = [
        r"-prod$",
        r"-prd$",
        r"-production$",
        r"-dev$",
        r"-staging$",
        r"-qa$",
        r"-test$",
    ]
    result = name
    for suffix in suffixes:
        result = re.sub(suffix, "", result, flags=re.IGNORECASE)
    return result


def match_service_to_repos(
    service_name: str, repositories: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], str, float]:
    """
    Match a service name to repositories using multiple strategies.
    Returns (matched_repo, match_type, confidence_score)
    """
    # Strip environment suffixes for better matching
    service_stripped = strip_environment_suffix(service_name)
    service_normalized = normalize_name(service_stripped)
    service_tokens = extract_tokens(service_stripped)

    best_match = None
    best_match_type = None
    best_confidence = 0.0

    for repo in repositories:
        repo_name = repo.get("name", "")
        repo_normalized = normalize_name(repo_name)
        repo_tokens = extract_tokens(repo_name)

        # Strategy 1: Exact match (normalized, after stripping env suffix)
        if service_normalized == repo_normalized:
            return (repo, "exact", 1.0)

        # Strategy 2: Service name contains repo name or vice versa
        if service_normalized in repo_normalized or repo_normalized in service_normalized:
            # Calculate confidence based on overlap
            if service_normalized in repo_normalized:
                confidence = len(service_normalized) / len(repo_normalized)
            else:
                confidence = len(repo_normalized) / len(service_normalized)

            if confidence > best_confidence and confidence >= 0.6:
                best_match = repo
                best_match_type = "substring"
                best_confidence = confidence

        # Strategy 3: Token overlap (better matching for composite names)
        if service_tokens and repo_tokens:
            overlap = service_tokens & repo_tokens
            if overlap:
                # Boost confidence if important tokens match
                important_tokens = {
                    t
                    for t in overlap
                    if len(t) > 3 or t in {"cds", "dms", "api", "cart", "checkout"}
                }
                if important_tokens:
                    confidence = (len(important_tokens) / len(service_tokens)) * 0.95
                else:
                    confidence = len(overlap) / len(service_tokens | repo_tokens)

                if confidence > best_confidence and confidence >= 0.4:
                    best_match = repo
                    best_match_type = "token_overlap"
                    best_confidence = confidence

        # Strategy 4: Sequence similarity with higher threshold
        ratio = similarity_ratio(service_normalized, repo_normalized)
        if ratio > best_confidence and ratio >= 0.75:
            best_match = repo
            best_match_type = "similarity"
            best_confidence = ratio

    # Require minimum confidence for match
    if best_confidence >= 0.5:
        return (best_match, best_match_type, best_confidence)

    return (None, "no_match", 0.0)


def classify_service(service_name: str) -> str:
    """Classify service as internal, external, or managed."""
    lower_name = service_name.lower()

    # External/managed services patterns
    external_patterns = [
        r"new\s+relic",
        r"databricks",
        r"onetrust",
        r"sendgrid",
        r"sendmail",
        r"suitevvm",
        r"tomcat",
        r"tibco",
        r"narvar",
        r"atlas",
        r"atlas-sapi",
        r"autosearch",
        r"inventory\s+service",
        r"sku-pdp",
        r"aj-sendsuite",
        r"mapi",
        r"nmapi",
        r"rfid",
    ]

    for pattern in external_patterns:
        if re.search(pattern, lower_name, re.IGNORECASE):
            return "external"

    # Internal services (based on observed patterns)
    if (
        lower_name.startswith("cds.")
        or lower_name.startswith("prod")
        or lower_name.startswith("p-")
        or "prod" in lower_name
        or "prd" in lower_name
    ):
        return "internal"

    return "unknown"


def infer_repository_project(service_name: str) -> Optional[str]:
    """Infer likely Azure DevOps project for a service based on naming patterns."""
    lower_name = service_name.lower().replace("-prod", "").replace("-prd", "")

    # CDS services -> digital-ado-* projects
    if lower_name.startswith("cds."):
        # Extract sub-domain
        parts = lower_name.split(".")
        if len(parts) > 1:
            subdomain = parts[1].split("-")[0]
            # Map service subdomains to projects
            project_map = {
                "cart": "digital-ado-exp",
                "checkout": "digital-ado-exp",
                "product": "digital-ado-exp",
                "profile": "digital-ado-exp",
                "search": "digital-ado-aut",
                "dms": "digital-ado-mer",
                "order": "digital-ado-ful",
                "authorization": "digital-ado-exp",
                "loyalty": "digital-ado-loy",
                "store": "digital-ado-exp",
                "notification": "digital-ado-exp",
                "subscription": "digital-ado-exp",
                "category": "digital-ado-exp",
            }
            return project_map.get(subdomain)
    return None



def analyze_repository_patterns(
    matched_services: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Analyze patterns in matched services and repositories."""
    patterns = {
        "by_project": defaultdict(list),
        "by_tech_stack": defaultdict(list),
        "by_branch": defaultdict(int),
        "size_distribution": {},
    }

    tech_stack_hints = {
        "python": ["python", "flask", "django"],
        "dotnet": ["dotnet", "csharp", "aspnetcore"],
        "node": ["node", "typescript", "javascript"],
        "java": ["java", "maven", "gradle"],
        "golang": ["go", "golang"],
    }

    for item in matched_services:
        repo = item.get("repository", {})
        project = repo.get("project", "unknown")
        branch = repo.get("defaultBranch", "refs/heads/main").split("/")[-1]
        repo_name = repo.get("name", "")

        patterns["by_project"][project].append(repo_name)
        patterns["by_branch"][branch] += 1

        # Detect tech stack hints from repo name
        for stack, keywords in tech_stack_hints.items():
            if any(kw in repo_name.lower() for kw in keywords):
                patterns["by_tech_stack"][stack].append(repo_name)

    # Compute size distribution
    sizes = [item.get("repository", {}).get("size", 0) for item in matched_services]
    if sizes:
        patterns["size_distribution"] = {
            "min": min(sizes),
            "max": max(sizes),
            "avg": sum(sizes) // len(sizes),
            "median": sorted(sizes)[len(sizes) // 2],
        }

    return patterns


def main():
    """Main entry point."""
    workspace_root = Path(__file__).resolve().parents[2]
    services_file = (
        workspace_root / "data" / "newrelic_apm_service_names_1679802.txt"
    )
    repo_map_file = workspace_root / "artifacts" / "azuregit_repo_map.json"
    output_file = workspace_root / "artifacts" / "azuregit_service_repository_map.json"

    # Load data
    print(f"Loading services from {services_file}...")
    services = load_services(services_file)
    print(f"Loaded {len(services)} services")

    print(f"Loading repository map from {repo_map_file}...")
    repo_map = load_repo_map(repo_map_file)
    repositories = flatten_repositories(repo_map)
    print(f"Loaded {len(repositories)} repositories")

    # Perform matching
    print("\nPerforming service-to-repository matching...")
    matched_services = []
    unmatched_services = []
    external_services = []
    classification_counts = Counter()

    for service in services:
        classification = classify_service(service)
        classification_counts[classification] += 1

        if classification == "external":
            external_services.append(
                {
                    "name": service,
                    "classification": "external",
                    "reason": "External or managed service",
                }
            )
        else:
            matched_repo, match_type, confidence = match_service_to_repos(
                service, repositories
            )
            if matched_repo:
                matched_services.append(
                    {
                        "service_name": service,
                        "repository": {
                            "id": matched_repo.get("id"),
                            "name": matched_repo.get("name"),
                            "project": matched_repo.get("project"),
                            "url": matched_repo.get("remoteUrl"),
                            "defaultBranch": matched_repo.get("defaultBranch"),
                        },
                        "match_type": match_type,
                        "confidence": round(confidence, 3),
                    }
                )
            else:
                inferred_project = infer_repository_project(service)
                unmatched_services.append(
                    {
                        "name": service,
                        "classification": classification,
                        "reason": "No repository match found",
                        "inferred_project": inferred_project,
                        "recommendation": f"Consider creating repository in {inferred_project or 'appropriate project'}",
                    }
                )

    # Analyze patterns
    print("Analyzing repository patterns...")
    repo_patterns = analyze_repository_patterns(matched_services)

    # Compute coverage metrics
    total_services = len(services)
    matched_count = len(matched_services)
    unmatched_count = len(unmatched_services)
    external_count = len(external_services)

    coverage_metrics = {
        "total_services": total_services,
        "matched_services": matched_count,
        "unmatched_services": unmatched_count,
        "external_services": external_count,
        "coverage_percentage": round(
            (matched_count / total_services * 100) if total_services > 0 else 0, 1
        ),
        "internal_coverage_percentage": round(
            (
                matched_count
                / (total_services - external_count)
                * 100
            )
            if (total_services - external_count) > 0
            else 0,
            1,
        ),
        "classification_summary": dict(classification_counts),
    }

    # Generate analysis summary
    analysis_summary = {
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "services_file": str(services_file),
        "repo_map_source": repo_map_file.name,
        "repo_map_generated_at": repo_map.get("generated_at"),
        "total_projects_scanned": len(repo_map.get("projects", {})),
        "total_repositories_scanned": len(repositories),
    }

    # Identify repository patterns from repository name analysis
    repo_name_patterns = Counter()
    for repo in repositories:
        name = repo.get("name", "")
        if "cds" in name.lower():
            repo_name_patterns["cds_services"] += 1
        if "dms" in name.lower():
            repo_name_patterns["dms_services"] += 1
        if "platform" in name.lower():
            repo_name_patterns["platform_services"] += 1
        if "api" in name.lower():
            repo_name_patterns["api_services"] += 1
        if "experience" in name.lower():
            repo_name_patterns["experience_services"] += 1
        if "integration" in name.lower():
            repo_name_patterns["integration_services"] += 1

    # Analyze unmatched services by category
    unmatched_by_category = defaultdict(list)
    for unmatched in unmatched_services:
        service_name = unmatched["name"].lower()
        if service_name.startswith("cds."):
            category = "cds_services"
        elif service_name.startswith("p-dmt"):
            category = "legacy_services"
        elif any(
            x in service_name
            for x in ["prod", "prd", "corp", "digital", "order", "rfid"]
        ):
            category = "infrastructure_services"
        else:
            category = "other"
        unmatched_by_category[category].append(unmatched["name"])

    # Generate recommendations
    recommendations = {
        "high_priority": [],
        "medium_priority": [],
        "low_priority": [],
    }

    # High priority: CDS services without repositories
    cds_unmatched = len(unmatched_by_category.get("cds_services", []))
    if cds_unmatched > 10:
        recommendations["high_priority"].append(
            f"Create {cds_unmatched} CDS service repositories across experience/core project groups"
        )

    # Medium priority: Organization consistency
    if coverage_metrics["coverage_percentage"] < 20:
        recommendations["medium_priority"].append(
            "Implement consistent naming convention between NewRelic services and repositories"
        )

    # Medium priority: External service documentation
    if external_count > 0:
        recommendations["medium_priority"].append(
            f"Document external/managed service integrations ({external_count} services)"
        )

    # Low priority: Migration path
    recommendations["low_priority"].append(
        "Establish service-to-repository mapping as part of CI/CD pipeline"
    )

    # Compile final output
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "analysis_summary": analysis_summary,
        "total_services": total_services,
        "coverage_metrics": coverage_metrics,
        "repository_patterns": dict(repo_patterns),
        "repository_name_patterns": dict(repo_name_patterns),
        "unmatched_by_category": dict(unmatched_by_category),
        "matched_services": matched_services,
        "unmatched_services": unmatched_services,
        "external_services": external_services,
        "organization_recommendations": recommendations,
    }

    # Write output
    print(f"\nWriting output to {output_file}...")
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print("\n" + "=" * 80)
    print("SERVICE-TO-REPOSITORY MAPPING ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total Services Analyzed: {total_services}")
    print(f"Matched to Repositories: {matched_count} ({coverage_metrics['coverage_percentage']}%)")
    print(f"Unmatched Services: {unmatched_count}")
    print(f"External/Managed Services: {external_count}")
    print(f"Internal Coverage: {coverage_metrics['internal_coverage_percentage']}%")
    print(f"\nClassification Summary:")
    for classification, count in sorted(classification_counts.items()):
        print(f"  - {classification}: {count}")
    print(f"\nRepository Patterns:")
    for pattern, count in sorted(repo_name_patterns.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {pattern}: {count}")
    print(f"\nUnmatched Services by Category:")
    for category, services_list in sorted(unmatched_by_category.items()):
        print(f"  - {category}: {len(services_list)}")
    print(f"\nProjects Scanned: {len(repo_map.get('projects', {}))}")
    print(f"Total Repositories Scanned: {len(repositories)}")
    print("\n" + "-" * 80)
    print("ORGANIZATION RECOMMENDATIONS")
    print("-" * 80)
    if recommendations["high_priority"]:
        print("\nHIGH PRIORITY:")
        for rec in recommendations["high_priority"]:
            print(f"  ★ {rec}")
    if recommendations["medium_priority"]:
        print("\nMEDIUM PRIORITY:")
        for rec in recommendations["medium_priority"]:
            print(f"  • {rec}")
    if recommendations["low_priority"]:
        print("\nLOW PRIORITY:")
        for rec in recommendations["low_priority"]:
            print(f"  ○ {rec}")
    print("\n✓ Output saved to:", output_file)


if __name__ == "__main__":
    main()
