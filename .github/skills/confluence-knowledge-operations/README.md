# Confluence Knowledge Operations

This skill package provides Confluence Cloud page discovery and service-flow analysis helpers backed by `.env` credentials.

## Required Variables

- `JIRA_HOST`
- `JIRA_USERNAME`
- `JIRA_API_TOKEN`
- `CONFLUENCE_SPACE_KEY` — single key or comma-separated list (e.g. `PLATFORM` or `PLATFORM,DEV,OPS`)

## Included Files

- `SKILL.md` - behavior contract for Confluence browsing, search, extraction, and graphing
- `confluence_client.py` - implementation for Confluence Cloud REST operations and service graph synthesis

## Helper Scripts

The repository includes execution helpers under `scripts/confluence/`:

- `common.py` - shared bootstrap (`.env` loading + skill import path setup)
- `search_space_pages.py` - list pages from all configured `CONFLUENCE_SPACE_KEY` spaces
- `search_content.py` - run CQL search with safe scoped behavior across all configured spaces
- `build_service_flow_graph.py` - build graph from page IDs or CQL-discovered pages

Example CLI usage:

```bash
python scripts/confluence/search_space_pages.py --limit 10
python scripts/confluence/search_content.py --cql "type = page AND text ~ \"schema\"" --limit 20
python scripts/confluence/build_service_flow_graph.py --page-id 12345 --page-id 67890
python scripts/confluence/build_service_flow_graph.py --cql "type = page AND text ~ \"integration\"" --limit 8
```

## Supported Workflows

- Browse pages in one or all configured Confluence spaces
- Search content with CQL (scoped to all configured spaces by default)
- Fetch page details by ID
- Resolve page by title across all configured spaces
- Extract service relationship signals across pages
- Build service-flow graphs with evidence-backed edges

## Usage Examples

```python
from confluence_client import ConfluenceClient

client = ConfluenceClient.from_env()

# Browse pages across all configured spaces
pages = client.list_space_pages(limit=10)

# Browse a specific space only
pages_dev = client.list_space_pages(limit=10, space_key="DEV")

results = client.search_content(
    cql="type=page AND text ~ \"event schema\"",
    limit=20,
)

page = client.get_page(page_id="123456789")

api_page = client.find_page_by_title("Order API Contract")

graph = client.build_service_flow_graph(
    page_ids=["123456789", "223344556"],
)
print(graph["mermaid"])
print(graph["space_keys"])  # list of all configured space keys
```

## Notes

- Confluence Cloud basic auth uses `JIRA_USERNAME` and `JIRA_API_TOKEN`
- `CONFLUENCE_SPACE_KEY` accepts a single key (`PLATFORM`) or a comma-separated list (`PLATFORM,DEV,OPS`)
- All space keys are normalized to uppercase during loading
- CQL queries are automatically scoped to all configured spaces unless the query already contains a `space =` clause
- `list_space_pages` and `find_page_by_title` accept an optional `space_key` argument to narrow to a single space
- Service-link extraction is heuristic and should be validated against source pages
- Relationship detection supports common phrasing patterns such as `calls`, `invokes`, `depends on`, `uses`, `integrates with`, `publishes to`, `emits to`, and arrow notation (`A -> B`)

## Tests

Run unit tests for extraction and graph synthesis:

```bash
python -m unittest tests/test_confluence_client.py -v
```
