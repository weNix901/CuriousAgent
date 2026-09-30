# Data Sources Specification

## Purpose
Describes trusted source management and search priority logic.

## Requirements

### Requirement: Trusted Source Management
The system SHALL maintain a trusted source list in `config/trusted_sources.json` with:
- `domain`, `name`, `type`, `trust_level` (1-5), `enabled` flag
- `web_scrape` flag for scraping permission
- 13 default academic sources (arxiv, nature, ieee, acm, springer, etc.)

### Requirement: TrustedSourceManager
The `TrustedSourceManager` class SHALL provide:
- `is_trusted_url(url)`: Check if URL is from trusted source
- CRUD operations for trusted sources
- Import/export functionality

### Requirement: Search Priority
Search operations SHALL prioritize trusted sources:
1. First search trusted source domains
2. If trusted source hits, download and mark `is_trusted=true`
3. If no trusted source hits, fall back to general web search
4. General search results are marked `is_trusted=false` with quality penalty
