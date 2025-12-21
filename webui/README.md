# just-dna-lite Web UI 🧬

A modern, Reflex-based web interface for the `just-dna-lite` genomic analysis platform.

## Features

- **Personal Dashboard**: Manage your genomic files and analysis results.
- **Job Monitoring**: Track the progress of long-running genomic pipelines in real-time.
- **Interactive Analysis**: Visualize genomic data and annotation results directly in the browser.
- **File Management**: Upload and organize your VCF files.
- **Configuration UI**: Manage platform settings and environment variables.

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed and are in the root of the `just-dna-lite` workspace.

### Running the Development Server

You can start the Web UI from the workspace root:

```bash
uv run start
```

Or from the `webui/` directory:

```bash
cd webui
uv run reflex run
```

The app will be available at `http://localhost:3000`.

## Project Structure

The Web UI is built with [Reflex](https://reflex.dev/):

- `src/webui/app.py`: Main application entry point and page registration.
- `src/webui/pages/`: Individual page definitions (Dashboard, Analysis, Jobs, etc.).
- `src/webui/components/`: Reusable UI components.
- `src/webui/state.py`: Global application state management.

## Development

To add a new page:
1. Create a new file in `src/webui/pages/`.
2. Define your page component and decorate it with `@rx.page()`.
3. Register the page in `src/webui/app.py`.

## Configuration

The Web UI uses the same environment variables as the GenoBear library for backend operations. See the root `README.md` for more details.
