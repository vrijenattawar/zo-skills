---
created: 2026-02-07
last_edited: 2026-02-07
version: 1.0
provenance: skills-importer-build
---

# Curated Skills from Skills.sh Ecosystem

A comprehensive directory of high-value skills from the skills.sh ecosystem, organized by category with install counts and brief descriptions. Use this as a reference for deciding which skills to import into your N5 OS.

## Frontend & React Development

### Vercel Labs Collection (`vercel-labs/agent-skills`)

**React Best Practices** (19K+ installs)
```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-best-practices
```
- Modern React patterns and conventions
- Performance optimization techniques
- Component composition best practices

**Web Design Guidelines**
```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/web-design-guidelines
```
- Design system principles
- UI/UX best practices
- Responsive design patterns

**React Native Guidelines**
```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-native-guidelines
```
- Mobile-first development patterns
- Performance optimization for mobile
- Platform-specific considerations

**Composition Patterns**
```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/composition-patterns
```
- Advanced React composition techniques
- Render props and higher-order components
- Custom hooks patterns

**Vercel Deploy**
```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/vercel-deploy-claimable
```
- Deployment automation
- CI/CD with Vercel
- Environment configuration

### Anthropic Collection (`anthropics/skills`)

**Frontend Design**
```bash
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/frontend-design
```
- Modern frontend design principles
- Component architecture
- Design system implementation

## Development Practices & Methodologies

### Obra's Superpowers (`obra/superpowers`)

**Systematic Debugging** (6.5K installs)
```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/systematic-debugging
```
- Scientific approach to debugging
- Problem isolation techniques
- Root cause analysis methods
- Documentation and reproduction strategies

**Test-Driven Development** (5.7K installs)
```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/test-driven-development
```
- Red-Green-Refactor cycle
- Test design patterns
- Integration testing strategies
- TDD for different languages/frameworks

**Writing Plans** (5.6K installs)
```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/writing-plans
```
- Project planning methodologies
- Breaking down complex tasks
- Risk assessment and mitigation
- Documentation standards

**Brainstorming** (11.5K installs)
```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/brainstorming
```
- Structured ideation techniques
- Creative problem solving
- Group brainstorming facilitation
- Idea evaluation and selection

## Document Processing & Data Handling

### Anthropic Document Tools (`anthropics/skills`)

**PDF Processing**
```bash
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/pdf
```
- PDF parsing and extraction
- Text and metadata extraction
- Form processing
- Document analysis

**Word Document Handling**
```bash
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/docx
```
- .docx file processing
- Content extraction and formatting
- Template generation
- Document conversion

**Excel Processing**
```bash
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/xlsx
```
- Spreadsheet analysis
- Data extraction and transformation
- Formula evaluation
- Chart and graph processing

## Database & Backend Development

### Supabase Collection (`supabase/agent-skills`)

**PostgreSQL Best Practices** (12.4K installs)
```bash
python3 Skills/skills-importer/scripts/import_skill.py supabase/agent-skills/supabase-postgres-best-practices
```
- Database design patterns
- Query optimization
- Security best practices
- Supabase-specific features

## Quality Assurance & Testing

**Coming from various repositories...**

**API Testing Frameworks**
- RESTful API testing patterns
- Integration test strategies
- Mock and stub implementations

**Performance Testing**
- Load testing methodologies
- Performance benchmarking
- Optimization strategies

## Content Creation & Writing

**Technical Writing**
- Documentation standards
- API documentation patterns
- User guide creation

**Content Strategy**
- Content planning and organization
- SEO optimization
- Multi-platform content adaptation

## DevOps & Infrastructure

**Docker Best Practices**
- Container optimization
- Multi-stage builds
- Security practices

**CI/CD Pipeline Design**
- Automation strategies
- Testing integration
- Deployment patterns

## Data Science & Analytics

**Data Analysis Frameworks**
- Statistical analysis patterns
- Data visualization techniques
- Report generation

**Machine Learning Workflows**
- Model training pipelines
- Feature engineering
- Model evaluation

## Import Strategies

### Essential Starter Pack
For new N5 OS users, start with these foundational skills:

```bash
# Core development practices
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/systematic-debugging
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/writing-plans

# Document processing
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/pdf
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/docx

# Creative thinking
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/brainstorming
```

### Frontend Developer Pack
For frontend-focused work:

```bash
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-best-practices
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/web-design-guidelines
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/frontend-design
```

### Full Stack Developer Pack
For comprehensive development capabilities:

```bash
# Frontend
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills/react-best-practices

# Backend
python3 Skills/skills-importer/scripts/import_skill.py supabase/agent-skills/supabase-postgres-best-practices

# Development practices
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/test-driven-development
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/systematic-debugging
```

### Content Creator Pack
For writing and content creation:

```bash
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/brainstorming
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/writing-plans

# Document processing for content workflows
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/docx
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills/pdf
```

## Repository Exploration Commands

Use these commands to explore what's available before importing:

```bash
# Browse popular collections
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers --list
python3 Skills/skills-importer/scripts/import_skill.py vercel-labs/agent-skills --list  
python3 Skills/skills-importer/scripts/import_skill.py anthropics/skills --list
python3 Skills/skills-importer/scripts/import_skill.py supabase/agent-skills --list

# Preview before importing
python3 Skills/skills-importer/scripts/import_skill.py obra/superpowers/brainstorming --dry-run
```

## Install Count Methodology

Install counts are sourced from:
- Skills.sh public leaderboards
- GitHub repository statistics
- Community adoption metrics

**Note**: Counts are approximate and may change. Use `--dry-run` to preview any skill before importing.

## Quality Indicators

### High-Quality Signals
- **High install counts** (>5K typically indicates community validation)
- **Active maintenance** (recent commits, issue responses)
- **Clear documentation** (comprehensive SKILL.md files)
- **Complete implementations** (includes scripts/, references/, examples)

### Repository Reputation
- **obra/superpowers**: Jesse Orbell - systematic methodologies
- **vercel-labs/agent-skills**: Vercel team - frontend expertise  
- **anthropics/skills**: Anthropic team - AI-native tooling
- **supabase/agent-skills**: Supabase team - database/backend focus

## Contributing Back

When you enhance imported skills:
1. Consider contributing improvements back to the original repository
2. Maintain `metadata.source` for easy identification of upstream
3. Follow the original repository's contribution guidelines
4. Share N5-specific adaptations that might benefit the broader community

## Maintenance Notes

This curated list is maintained manually and may not reflect the latest skills.sh ecosystem changes. For the most current information:

1. Explore repositories directly using `--list` commands
2. Check skills.sh leaderboards for trending skills
3. Browse GitHub repositories for new additions
4. Monitor community discussions for quality recommendations

**Last Updated**: 2026-02-07
**Next Review**: 2026-05-07 (quarterly review cycle)