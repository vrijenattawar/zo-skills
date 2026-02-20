---
created: 2026-02-01
last_edited: 2026-02-01
version: 1.0
provenance: con_MKZ5RVBt8uiFukI5
---

# Meeting ID Convention

This document defines the canonical meeting ID and folder naming convention for the meeting ingestion system.

## Format

```
YYYY-MM-DD_Descriptive-Name
```

## Rules

### Date Component (YYYY-MM-DD)
- Use ISO 8601 date format (YYYY-MM-DD)
- Always use the meeting date, not the processing/ingestion date
- Use zero-padded months and days (01, 02, etc.)

### Descriptive Name Component
- Convert to kebab-case (lowercase with hyphens)
- Remove or transform special characters
- Limit to reasonable length (recommended: 50 characters max)
- Must be URL-safe and filesystem-safe

## Transformation Rules

### Text Processing
1. **Convert to lowercase**: "Team Meeting" → "team-meeting"
2. **Replace spaces with hyphens**: "Weekly Standup" → "weekly-standup"
3. **Remove special characters**: Keep only alphanumeric characters and hyphens
4. **Collapse multiple hyphens**: "Team--Meeting" → "team-meeting"
5. **Trim leading/trailing hyphens**: "-team-meeting-" → "team-meeting"

### Character Mapping
| Input Character(s) | Output |
|-------------------|---------|
| Space ` ` | `-` |
| Underscore `_` | `-` |
| Period `.` | `-` |
| Comma `,` | `-` |
| Colon `:` | `-` |
| Semicolon `;` | `-` |
| Slash `/`, `\` | `-` |
| Parentheses `()` | Remove |
| Brackets `[]`, `{}` | Remove |
| Quotes `"`, `'` | Remove |
| Ampersand `&` | `and` |
| At symbol `@` | `at` |
| Hash `#` | Remove |
| Plus `+` | `plus` |
| Percent `%` | `percent` |

## Examples

### Basic Examples
- **Input**: "2024-03-15 Team Meeting"
- **Output**: `2024-03-15_team-meeting`

- **Input**: "2024-12-01 Q4 Planning Session"
- **Output**: `2024-12-01_q4-planning-session`

### Special Character Examples
- **Input**: "2024-06-15 Product Review & Strategy"
- **Output**: `2024-06-15_product-review-and-strategy`

- **Input**: "2024-08-30 Client Meeting (Acme Corp)"
- **Output**: `2024-08-30_client-meeting-acme-corp`

- **Input**: "2024-11-22 Budget Review: Finance Team"
- **Output**: `2024-11-22_budget-review-finance-team`

### Long Name Examples
- **Input**: "2024-07-10 Engineering Architecture Review for New Platform Initiative"
- **Output**: `2024-07-10_engineering-architecture-review-for-new-platform` (truncated)

- **Input**: "2024-09-05 Cross-functional Team Alignment Meeting for Product Launch"
- **Output**: `2024-09-05_cross-functional-team-alignment-meeting-for-prod` (truncated)

## Edge Cases

### Multiple Spaces and Special Characters
- **Input**: "2024-04-20 Team   Meeting!!!  @  Office"
- **Intermediate**: "2024-04-20 team---meeting---at--office"
- **Output**: `2024-04-20_team-meeting-at-office`

### Numbers and Mixed Case
- **Input**: "2024-05-15 Q2 2024 OKR Review"
- **Output**: `2024-05-15_q2-2024-okr-review`

### Already Compliant Names
- **Input**: "2024-01-10 daily-standup"
- **Output**: `2024-01-10_daily-standup` (unchanged)

### Empty or Very Short Names
- **Input**: "2024-06-01 "
- **Output**: `2024-06-01_meeting` (fallback)

- **Input**: "2024-06-01 Q"
- **Output**: `2024-06-01_q`

## Implementation Guidelines

### Name Generation Algorithm
1. Extract date from meeting metadata
2. Extract title/name from meeting metadata
3. Apply character transformations in order
4. Validate length constraints
5. Apply fallbacks for edge cases

### Validation Rules
- Total length should not exceed 100 characters
- Must contain only lowercase letters, numbers, hyphens, and underscores
- Must start and end with alphanumeric characters
- Date component must be valid ISO 8601 date
- No consecutive hyphens or underscores

### Fallback Strategies
- If no descriptive name is available, use "meeting"
- If name becomes empty after transformation, use "meeting"
- If name is too long, truncate at word boundaries when possible
- If date is missing or invalid, use ingestion date with warning

## Related Components

This convention is used by:
- Meeting manifest generation
- Folder structure creation
- File naming within meeting directories
- URL generation for meeting links
- Database indexing and search