# just-dna-lite Web UI

Reflex-based UI for the `just-dna-lite` workspace.

## Features

- Dashboard for user files and outputs
- Job tracking for pipeline runs
- File upload / organization for VCF inputs

## Getting Started

### Prerequisites

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

### Running the Development Server

The recommended way to start the Web UI is from the **workspace root**:

```bash
uv run start
```

This starts Reflex (frontend + backend dev server). For other entry points, see the root [README.md](../README.md).

If you need to run it directly from this directory:

```bash
uv run reflex run
```

## Architectural Overview

For those familiar with Python but new to [Reflex](https://reflex.dev/), here is an overview of how the application is structured.

### 1. Pure Python UI
Reflex allows building full-stack web apps in pure Python. There is no HTML/JS/CSS to write. Components like `rx.vstack()`, `rx.heading()`, and `rx.table()` are compiled into a React frontend.

### 2. State Management (The "Backend")
The application's logic resides in `src/webui/state.py`.
- **`rx.State`**: Classes inheriting from `rx.State` represent the "Backend".
- **Variables (Vars)**: Any class attribute is automatically synced between the server and the browser.
- **Event Handlers**: Methods on these classes are the only way to modify state. They are triggered by UI events (e.g., `on_click`).

### 3. Layout and Templating
To maintain a consistent look across the platform (sidebar, topbar, navigation), we use a wrapper pattern.
- **`src/webui/components/layout.py`**: Contains the `template` function.
- **The Pattern**: Every page function wraps its content in `template(...)`. This ensures that even though the center content changes during navigation, the "Shell" (navigation and header) remains persistent and efficient.

### 4. File Structure
- `src/webui/app.py`: The "Wiring" file. It initializes the `rx.App` and registers routes.
- `src/webui/pages/`: Modular route definitions. Each file typically corresponds to one URL (e.g., `/dashboard`).
- `src/webui/components/`: Pure UI functions that don't hold state.
- `assets/`: Static files (images, custom CSS) served at the root.

## Development

To add a new feature:
1. Define state: add variables and event handlers to `src/webui/state.py`.
2. Create a page in `src/webui/pages/` using the `template` wrapper.
3. Register the route in `src/webui/app.py`.

## Configuration

The Web UI uses the same environment variables as the Just DNA Pipelines library for backend operations. See the root [README.md](../README.md) for more details.
