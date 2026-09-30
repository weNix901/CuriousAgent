# Delta for WebUI

## ADDED Requirements

### Requirement: Trusted Source Management Tab
The WebUI SHALL provide a `🔒 可信数据源` tab with:
- Table listing all trusted sources (domain, name, type, trust_level, enabled status)
- Add new source button with form (domain, name, type, trust_level)
- Delete source button per row
- Toggle enable/disable per row
- Import/export JSON functionality
- URL check input to test if a URL is from a trusted source

#### Scenario: View trusted sources
- GIVEN the trusted sources tab is opened
- WHEN the page loads
- THEN it displays all configured trusted sources from `/api/trusted-sources`

#### Scenario: Add trusted source
- GIVEN the add form is filled with domain, name, type, trust_level
- WHEN the user clicks add
- THEN the new source appears in the table

#### Scenario: Toggle enable/disable
- GIVEN a trusted source is enabled
- WHEN the user clicks toggle
- THEN the source status changes and the UI updates
