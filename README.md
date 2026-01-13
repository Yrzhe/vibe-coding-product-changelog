# Product Changelog Viewer

A web application for viewing and comparing product changelog updates across multiple competing products. Features automatic crawling, LLM-based tagging, and a tag-product matrix view.

## Features

- **Matrix View**: Compare product features across a tag hierarchy
- **Tags Browser**: Browse features by primary/secondary tags
- **Product Changelogs**: View individual product update history
- **Excel Export**: Export the tag-product matrix to Excel
- **Auto Crawling**: Scheduled crawlers for each product's changelog
- **LLM Tagging**: Automatic feature categorization using LLM

## Quick Start

### Using Docker (Recommended)

```bash
# Build and start the web app
docker-compose up -d web

# Access at http://localhost:8080
```

### Local Development

```bash
cd webapp
npm install
npm run dev
```

## Project Structure

```
.
├── webapp/           # React + Vite frontend
├── script/           # Python crawlers and LLM tagger
│   ├── crawl/        # Product-specific crawlers
│   ├── prompts/      # LLM prompt templates
│   ├── monitor.py    # Incremental update orchestrator
│   └── llm_tagger.py # LLM-based feature tagger
├── storage/          # Product data JSON files
├── info/             # Tag definitions and configs
└── docker-compose.yml
```

## Configuration

### LLM Tagger Setup

Copy the example config and add your API key:

```bash
cp script/prompts/llm_config.example.json script/prompts/llm_config.json
# Edit llm_config.json with your API key
```

### Scheduled Updates

```bash
# Make the script executable
chmod +x run-crawler.sh

# Add to crontab for daily updates
crontab -e
# Add: 0 2 * * * /path/to/run-crawler.sh >> /var/log/changelog-crawler.log 2>&1
```

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed deployment instructions.

## Tech Stack

- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Crawlers**: Python, Playwright
- **LLM**: Claude API (configurable)
- **Deployment**: Docker, nginx

## License

MIT
