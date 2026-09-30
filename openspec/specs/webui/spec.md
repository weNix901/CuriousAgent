# WebUI Specification

## Purpose
Describes the web interface views and functionality.

## Requirements

### Requirement: Knowledge Graph View
The WebUI SHALL provide a D3.js force-directed graph visualization that:
- Renders automatically on load (no tabs)
- Shows DERIVED_FROM relations
- Supports clicking nodes for detail modal
- Color-codes nodes by status (active/gray/done)

### Requirement: Knowledge List View
The WebUI SHALL provide a list view of all knowledge nodes with:
- Topic, status, quality, depth, completeness_score columns
- Filtering and sorting capabilities

### Requirement: Settings Page
The WebUI SHALL provide a settings page for configuring:
- LLM providers
- Search providers
- Deep read settings
- Temperature and archive settings

### Requirement: View Modes
The WebUI SHALL support external and internal view modes with corresponding views.
