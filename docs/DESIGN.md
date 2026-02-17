# Design System: Fomantic-UI and Reflex

This document defines the visual design language for **just-dna-lite** UI components using **Fomantic UI**.

## Core Aesthetic

"Chunky & Tactile" feel. High affordance for non-professional users. Elements must look like physical objects with clear boundaries and solid fills.

## 1. Component Styling

- **Buttons:** `ui primary button`, `ui massive button`. Solid backgrounds only.
- **Segments:** `ui segment`, `ui raised segment`, `ui piled segment`.
- **Inputs:** `ui input`, `ui fluid input`.
- **Icons:** Oversized (min 2rem). Pair with every major label.
- **Icon Implementation:** Use `fomantic_icon()` from `webui.components.layout`. Do NOT use `rx.icon()` directly as Lucide icons often fail to load or trigger terminal warnings.
    - Verified icons (mapped by helper): `cloud-upload`, `circle-play`, `circle-alert`, `dna`, `activity`, `files`, `refresh-cw`, `file-text`, `loader-circle`, `external-link`, `tags`, `plus`, `x`, `user`, `scale`, `edit`, `folder`, `clipboard`, `paw-print`, `hard-drive`, `eye`, `arrow-left`.

## 2. Layout & Spacing

- **Spacing:** Liberal use of `ui segments` and `ui divider`.
- **Typography:** Large font sizes. Headers should use `ui header`.

### Grid Layout (IMPORTANT)

Fomantic UI's grid system uses a **16-column** layout. However, **in Reflex, Fomantic grids often don't work reliably** and columns may stack vertically instead of horizontally.

**Recommended: Use CSS Flexbox instead of Fomantic grid for multi-column layouts:**

```python
# GOOD - Flexbox for reliable horizontal columns
rx.el.div(
    rx.el.div(left_content, style={"flex": "0 0 30%"}),
    rx.el.div(center_content, style={"flex": "0 0 40%"}),
    rx.el.div(right_content, style={"flex": "1 1 30%"}),
    style={"display": "flex", "flexDirection": "row", "gap": "10px"},
)

# UNRELIABLE - Fomantic grid may not work in Reflex
rx.el.div(
    rx.el.div(..., class_name="five wide column"),
    rx.el.div(..., class_name="six wide column"),
    class_name="ui grid",
)
```

**For scrollable columns:**

```python
column_style = {
    "height": "calc(100vh - 140px)",
    "overflowY": "auto",
    "overflowX": "hidden",
}
```

### Menu/Navigation

**Use flexbox for horizontal menus**, not `ui fixed menu`:

```python
# GOOD - Flexbox menu
rx.el.div(
    rx.el.div(..., style={"display": "flex", "alignItems": "center"}),  # left items
    rx.el.div(..., style={"marginLeft": "auto"}),  # right items
    style={
        "display": "flex",
        "justifyContent": "space-between",
        "position": "fixed",
        "top": "0",
        "left": "0",
        "right": "0",
        "height": "50px",
        "backgroundColor": "#fff",
        "zIndex": "1000",
    },
)
```

### Two-Column Layout with Tabs

For master-detail layouts where one panel is fixed and another has tabbed content:

```python
def two_column_layout(left: rx.Component, right: rx.Component) -> rx.Component:
    """Two-column layout: narrow left panel, wide right panel with tabs."""
    column_height = "calc(100vh - 150px)"
    column_base = {
        "height": column_height,
        "overflowY": "auto",
        "padding": "16px",
        "backgroundColor": "#ffffff",
        "borderRadius": "4px",
        "boxShadow": "0 1px 2px rgba(0,0,0,0.1)",
    }
    
    return rx.el.div(
        rx.el.div(left, style={**column_base, "flex": "0 0 28%", "maxWidth": "350px"}),
        rx.el.div(style={"width": "1px", "backgroundColor": "#e0e0e0", "margin": "0 12px"}),
        rx.el.div(right, style={**column_base, "flex": "1 1 70%", "minWidth": "500px"}),
        style={"display": "flex", "flexDirection": "row", "width": "100%"},
    )
```

### Fomantic UI Tabs (State-Based)

Fomantic UI tabs require jQuery for dynamic behavior, but **in Reflex, use state-based class toggling instead**:

```python
# State variable to track active tab
class MyState(rx.State):
    active_tab: str = "tab1"
    
    def switch_tab(self, tab_name: str):
        self.active_tab = tab_name

# Tab menu component
def tab_menu() -> rx.Component:
    return rx.el.div(
        rx.el.a(
            fomantic_icon("sliders-horizontal", size=16),
            " Tab 1",
            class_name=rx.cond(MyState.active_tab == "tab1", "active item", "item"),
            on_click=lambda: MyState.switch_tab("tab1"),
            style={"display": "flex", "alignItems": "center", "cursor": "pointer"},
        ),
        rx.el.a(
            fomantic_icon("history", size=16),
            " Tab 2",
            class_name=rx.cond(MyState.active_tab == "tab2", "active item", "item"),
            on_click=lambda: MyState.switch_tab("tab2"),
            style={"display": "flex", "alignItems": "center", "cursor": "pointer"},
        ),
        class_name="ui top attached tabular menu",
    )

# Tab content with rx.match
def tab_content() -> rx.Component:
    return rx.el.div(
        rx.match(
            MyState.active_tab,
            ("tab1", tab1_content()),
            ("tab2", tab2_content()),
            tab1_content(),  # default
        ),
        class_name="ui bottom attached segment",
    )
```

**Key points:**
- Use `ui top attached tabular menu` for tab headers
- Use `ui bottom attached segment` for tab content
- Add `active item` class conditionally with `rx.cond`
- Use `rx.match` to render the correct tab content

### Collapsible Sections Pattern

For accordion-style collapsible sections with consistent styling. Each section uses an `accent_color` that matches its parent Fomantic segment color:

```python
def _collapsible_header(
    expanded: rx.Var[bool],
    icon_name: str,
    title: str,
    right_badge: rx.Component,
    on_toggle: rx.EventSpec,
    accent_color: str = "#2185d0",  # Match to parent segment color
) -> rx.Component:
    """Reusable foldable section header."""
    return rx.el.div(
        rx.el.div(
            rx.cond(
                expanded,
                fomantic_icon("chevron-down", size=20, color=accent_color),
                fomantic_icon("chevron-right", size=20, color=accent_color),
            ),
            fomantic_icon(icon_name, size=20, color=accent_color, style={"marginLeft": "6px"}),
            rx.el.span(title, style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "8px"}),
            style={"display": "flex", "alignItems": "center"},
        ),
        right_badge,
        on_click=on_toggle,
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "cursor": "pointer",
            "padding": "12px",
            "backgroundColor": "#f9fafb",
            "borderRadius": "6px",
            "marginBottom": rx.cond(expanded, "16px", "0"),
        },
    )

# Usage: accent_color must match the segment color
# Outputs = teal (#00b5ad), Run History = green (#21ba45), New Analysis = blue (#2185d0)
rx.el.div(
    _collapsible_header(
        expanded=MyState.section_expanded,
        icon_name="folder-output",
        title="Outputs",
        right_badge=rx.el.span("5 files", class_name="ui mini teal label"),
        on_toggle=MyState.toggle_section,
        accent_color="#00b5ad",  # Matches ui teal segment
    ),
    rx.cond(MyState.section_expanded, section_content(), rx.box()),
    class_name="ui teal segment",
    style={"padding": "16px"},
)
```

**Key points:**
- Chevron icon indicates expand/collapse state (`chevron-right` → `chevron-down`)
- `accent_color` parameter matches the parent segment's Fomantic color hex
- Right badge shows count or status
- Wrap in colored Fomantic segment (`ui teal segment`, `ui green segment`, etc.)

### Two Independent Data Grids Pattern

The app uses two separate `LazyFrameGridMixin` state classes to power two independent data grids that never interfere:

```python
# state.py — each class gets its own LazyFrame cache (keyed by class name)
class UploadState(LazyFrameGridMixin):
    """VCF input grid — always shows the uploaded VCF file."""
    ...

class OutputPreviewState(LazyFrameGridMixin):
    """Output preview grid — shows parquet/CSV on demand inside Outputs section."""
    output_preview_expanded: bool = False
    output_preview_label: str = ""

    def view_output_file(self, file_path: str):
        """Generator — called directly from on_click, no bridge needed."""
        self.output_preview_expanded = True
        yield
        lf, descriptions = scan_file(Path(file_path))
        yield from self.set_lazyframe(lf, descriptions, chunk_size=300)
        self.output_preview_label = Path(file_path).name
```

```python
# annotate.py — each grid renders with its own state class
lazyframe_grid(UploadState, ...)          # VCF grid in violet segment
lazyframe_grid(OutputPreviewState, ...)   # Output grid inside teal Outputs segment
```

**Key points:**
- Each `LazyFrameGridMixin` subclass gets its own cache (keyed by `type(self).__name__`)
- The output grid's `on_click` calls `OutputPreviewState.view_output_file` **directly** — no bridge through `UploadState`
- The output grid is hidden until the user clicks the eye icon; dismissed with a close (X) button
- Generator event handlers must use `yield` and `yield from self.set_lazyframe(...)` to propagate loading state

## 3. Color Palette (DNA Logo-Derived, Fomantic-Native)

The color palette is derived from the DNA double-helix logo and maps directly to Fomantic UI built-in colors. This gives us free hover/active/focus states, backgrounds, labels, buttons, and segments with **zero custom CSS**.

### 5-Color Palette

| Role | Fomantic Class | Hex | Logo Source | UI Usage |
|------|---------------|-----|-------------|----------|
| **Primary** | `blue` | `#2185d0` | Central helix (cyan-blue range) | Navbar, primary buttons, active tabs, links, selected items |
| **Success** | `green` | `#21ba45` | Left backbone (green strands) | Completed runs, benign variants, success messages, save buttons |
| **Info / Data** | `teal` | `#00b5ad` | Central helix curve | Info badges, data displays, VUS variants, outputs section |
| **Warning** | `yellow` | `#fbbd08` | Upper-right rungs (gold/amber) | In-progress, pending review, running status, attention needed |
| **Danger** | `red` | `#db2828` | Phosphate atoms (red dots) | Pathogenic variants, errors, destructive actions, required markers |

### Brand Gradient (decorative header banner only)

```css
linear-gradient(135deg, #21ba45, #00b5ad, #2185d0)
```

This echoes the DNA helix flow: green (left backbone) -> teal (center) -> blue (right backbone).

### Semantic Color Mapping

- **Variant Classification:**
  - `ui green label` - Benign
  - `ui red label` - Pathogenic
  - `ui teal label` - VUS (Variant of Uncertain Significance)

- **Run Status Badges:**
  - `ui green label` - SUCCESS / completed
  - `ui yellow label` - RUNNING / in-progress
  - `ui red label` - FAILURE / error
  - `ui grey label` - QUEUED / ready

- **File Status Badges:**
  - `ui mini green label` - completed
  - `ui mini yellow label` - running
  - `ui mini label` - ready (default grey)
  - `ui mini red label` - error

- **Section Accent Segments:**
  - `ui violet segment` - Input VCF Preview (data inspection)
  - `ui teal segment` - Outputs section (data/results + output preview grid)
  - `ui green segment` - Run History section (success/timeline)
  - `ui blue segment` - New Analysis section (primary action)

### Module Cards

Each annotation module is displayed as a card with:
- **Logo from HuggingFace**: If the module has a `logo.jpg`/`logo.png` in the HF repository, it is displayed as the card image. Falls back to a colored Fomantic icon if no logo exists.
- **Source repo badge**: A small label showing which HF repository the module comes from (e.g. `just-dna-seq/annotators`).
- **Module Sources section**: Above the module cards, a "Module Sources" section lists all HF repositories with clickable links and module counts.

Logo URLs are converted from `hf://` protocol to browsable HTTPS URLs:
```
hf://datasets/repo/data/module/logo.jpg
→ https://huggingface.co/datasets/repo/resolve/main/data/module/logo.jpg
```

**Fallback colors** (used when no logo is available):

| Module | Fomantic Color | Class | Rationale |
|--------|---------------|-------|-----------|
| Coronary | `red` | `#db2828` | Heart, clinical urgency |
| Lipid Metabolism | `yellow` | `#fbbd08` | Metabolic energy |
| Longevity Map | `green` | `#21ba45` | Life, longevity |
| Sportshuman | `teal` | `#00b5ad` | Performance, vitality |
| VO2 Max | `blue` | `#2185d0` | Oxygen, respiration |
| Pharmacogenomics | `purple` | `#a333c8` | Drug/chemistry |

### Icon Colors

When using `fomantic_icon()` with explicit `color=` parameter, use the Fomantic hex value matching the semantic context:

| Context | Color Hex | When |
|---------|-----------|------|
| Primary / interactive | `#2185d0` | Primary buttons, blue section headers, nav icons |
| Success / completed | `#21ba45` | Check marks, save actions, green section headers |
| Info / data | `#00b5ad` | DNA icon, teal section headers, file type icons, selected items |
| Warning / attention | `#fbbd08` | In-progress indicators, running status |
| Danger / error | `#db2828` | Required field markers, delete buttons, error badges |
| Muted / secondary | `#767676` | Library icons, secondary info |

**Section header icons must use the matching segment color:**
- Input VCF Preview header (`ui violet segment`) → `accent_color="#6435c9"`
- Outputs header (`ui teal segment`) → `accent_color="#00b5ad"`
- Run History header (`ui green segment`) → `accent_color="#21ba45"`
- New Analysis header (`ui blue segment`) → `accent_color="#2185d0"`

### Tactile Feedback

- Fomantic UI provides built-in hover and active states for all colored elements.
- For custom effects, use inline styles: `hover: shadow-lg`, `active: scale-95`.

## 4. Component Mapping (Fomantic)

| Component Type | Fomantic Class |
| :--- | :--- |
| Segment | `ui segment` |
| Primary Button | `ui primary button` |
| Message | `ui message` |
| Divider | `ui divider` |
| Label | `ui label` |
| Checkbox | `ui checkbox` (requires specific structure) |
| Checked Checkbox | `ui checked checkbox` |

### Fomantic UI Checkbox (IMPORTANT)

Fomantic UI checkboxes require **specific HTML structure** to work correctly. Do NOT use Reflex's `rx.checkbox()` if you want Fomantic styling.

**Required structure:**
```html
<div class="ui checkbox">
  <input type="checkbox">
  <label>Label text</label>
</div>
```

**In Reflex:**
```python
def fomantic_checkbox(checked: rx.Var[bool], on_click: rx.EventHandler) -> rx.Component:
    """Fomantic UI styled checkbox."""
    return rx.el.div(
        rx.el.input(
            type="checkbox",
            checked=checked,
            read_only=True,  # Controlled by parent click
        ),
        rx.el.label(),  # Can be empty or contain label text
        on_click=on_click,
        class_name=rx.cond(checked, "ui checked checkbox", "ui checkbox"),
    )
```

**Checkbox variations:**
- `ui checkbox` - Standard checkbox
- `ui checked checkbox` - Checked state (add dynamically)
- `ui toggle checkbox` - Toggle switch style
- `ui slider checkbox` - Slider style
- `ui radio checkbox` - Radio button
- `ui disabled checkbox` - Disabled state

## 5. Example Components

### Primary Button

```python
rx.el.button(
    fomantic_icon("circle-play", size=32),
    " Run Analysis",
    class_name="ui primary massive button"
)
```

### Card/Segment

```python
rx.el.div(
    rx.el.h2("Card Title", class_name="ui header"),
    rx.el.div(class_name="ui divider"),
    rx.el.p("Content goes here...", style={"fontSize": "1.2rem"}),
    class_name="ui segment raised"
)
```

### Alert/Message

```python
rx.el.div(
    fomantic_icon("circle-check", size=32),
    rx.el.div(
        rx.el.div("Variant is benign", class_name="header"),
        class_name="content"
    ),
    class_name="ui positive message"
)
```

## 6. Reflex Component Patterns

### Icon Usage (CRITICAL)

**Use `fomantic_icon()` instead of `rx.icon()`.** Lucide icons often fail to load or trigger terminal warnings. 

**Icons require STATIC string names.** You cannot pass a dynamic `rx.Var` to `fomantic_icon()` or `rx.icon()`.

```python
# BAD - will crash with "Icon name must be a string, got typing.Any"
rx.foreach(
    items,
    lambda item: fomantic_icon(item["icon_name"], size=24)  # CRASHES
)

# GOOD - use rx.match for dynamic icons
def get_icon(name: rx.Var[str]) -> rx.Component:
    return rx.match(
        name,
        ("heart", fomantic_icon("heart", size=24)),
        ("star", fomantic_icon("star", size=24)),
        fomantic_icon("circle", size=24),  # default
    )

rx.foreach(items, lambda item: get_icon(item["icon_name"]))
```

### Verified Icon Names

Always use **hyphenated** names. Common mistakes:

| Wrong | Correct |
| :--- | :--- |
| `check-circle` | `circle-check` |
| `check_circle` | `circle-check` |
| `upload_cloud` | `cloud-upload` |
| `alert-circle` | `circle-alert` |
| `play-circle` | `circle-play` |

**Verified working icons:**
- `circle-check`, `circle-x`, `circle-alert`, `circle-play`
- `cloud-upload`, `upload`, `download`, `file-text`, `files`
- `dna`, `heart`, `heart-pulse`, `activity`, `zap`, `droplets`, `pill`
- `loader-circle` (for spinners), `refresh-cw`
- `external-link`, `terminal`, `database`, `boxes`
- `inbox`, `history`, `chart-bar`, `play`, `list`
- `sliders-horizontal`, `folder-output`, `folder-x`, `scale`, `book-open`, `trash-2`
- `chevron-down`, `chevron-left`, `chevron-right`, `chevron-up` (for collapsible sections / hints)
- `clock`, `plus-circle`, `plus`, `tags`, `user`, `x`
- `edit`, `folder`, `clipboard`, `paw-print`, `hard-drive`
- `eye`, `arrow-left` (for output preview and navigation)

Full list: https://reflex.dev/docs/library/data-display/icon/#icons-list

### rx.foreach Limitations

Inside `rx.foreach`, values from dictionaries are typed as `Any`. This breaks components that require specific types:

```python
# BAD - checkbox checked expects bool, gets Any
rx.foreach(items, lambda item: rx.checkbox(checked=item["is_checked"]))

# GOOD - explicitly handle the type or use rx.cond
rx.foreach(items, lambda item: rx.checkbox(
    checked=item["is_checked"].to(bool)
))
```

### Conditional Styling

Use `rx.cond()` for conditional classes, not Python ternary:

```python
# GOOD
class_name=rx.cond(is_active, "ui primary button", "ui button")

# BAD - won't react to state changes
class_name="ui primary button" if is_active else "ui button"
```

## 7. Metadata Form Pattern

For editable metadata with dropdowns, text inputs, and custom key-value fields:

```python
def metadata_row(label: str, value: rx.Var[str], icon: str) -> rx.Component:
    """Single metadata row with icon, label, and value (read-only)."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon(icon, size=14, color="#888"),
            rx.el.span(label, style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
            style={"display": "flex", "alignItems": "center", "minWidth": "80px"},
        ),
        rx.el.span(value, style={"fontSize": "0.85rem", "fontWeight": "500"}),
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "3px 0"},
    )

def dropdown_row(label: str, icon: str, options: rx.Var[list], value: rx.Var[str], on_change: rx.EventHandler) -> rx.Component:
    """Dropdown row for selectable metadata."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon(icon, size=14, color="#888"),
            rx.el.span(label, style={"color": "#666", "fontSize": "0.8rem", "marginLeft": "6px"}),
            style={"display": "flex", "alignItems": "center", "minWidth": "80px"},
        ),
        rx.el.select(
            rx.foreach(options, lambda opt: rx.el.option(opt, value=opt)),
            value=value,
            on_change=on_change,
            style={"fontSize": "0.8rem", "padding": "2px 6px", "borderRadius": "4px", "border": "1px solid #ddd"},
        ),
        style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "3px 0"},
    )
```

### Custom Key-Value Fields

For user-defined metadata fields with add/remove functionality:

```python
# State for custom fields
class MyState(rx.State):
    custom_fields: Dict[str, str] = {}
    new_field_name: str = ""
    new_field_value: str = ""
    
    def add_custom_field(self, name: str, value: str):
        self.custom_fields = {**self.custom_fields, name: value}
    
    def remove_custom_field(self, name: str):
        self.custom_fields = {k: v for k, v in self.custom_fields.items() if k != name}

# UI for custom fields
rx.el.div(
    # Existing fields with delete buttons
    rx.foreach(
        MyState.custom_fields_list,  # [{name: str, value: str}, ...]
        lambda field: rx.el.div(
            rx.el.span(field["name"].to(str), style={"fontWeight": "500"}),
            rx.el.span(field["value"].to(str)),
            rx.el.button(
                fomantic_icon("x", size=12),
                on_click=lambda f=field: MyState.remove_custom_field(f["name"].to(str)),
                class_name="ui mini icon button",
            ),
            style={"display": "flex", "alignItems": "center", "gap": "8px"},
        ),
    ),
    # Add new field inputs
    rx.el.div(
        rx.el.input(value=MyState.new_field_name, on_change=MyState.set_new_field_name, placeholder="Field name"),
        rx.el.input(value=MyState.new_field_value, on_change=MyState.set_new_field_value, placeholder="Value"),
        rx.el.button(fomantic_icon("plus", size=12), on_click=MyState.save_new_custom_field, class_name="ui mini icon positive button"),
        style={"display": "flex", "gap": "4px"},
    ),
)
```

## 8. Empty State / Onboarding Pattern

When a panel has no content to display (e.g. no file selected, no results yet), show a **workflow onboarding** instead of a redundant prompt. Do NOT duplicate controls that already exist elsewhere (e.g. don't show "upload a file" when the left panel already has that form).

```python
def no_file_selected_message() -> rx.Component:
    """Welcome/onboarding when no sample is selected."""
    def workflow_step(number: str, bg_color: str, icon: str, title: str, desc: str) -> rx.Component:
        return rx.el.div(
            rx.el.div(number, style={..., "backgroundColor": bg_color}),  # numbered circle
            rx.el.div(
                rx.el.div(fomantic_icon(icon, size=16, color=bg_color), rx.el.strong(title), ...),
                rx.el.div(desc, ...),
            ),
            ...
        )

    return rx.el.div(
        fomantic_icon("dna", size=56, color="#00b5ad"),
        rx.el.h3("Welcome to Genomic Annotation"),
        rx.el.p("Annotate your VCF files with specialized modules"),
        workflow_step("1", "#21ba45", "cloud-upload", "Add a sample", "..."),
        workflow_step("2", "#00b5ad", "dna", "Choose modules", "..."),
        workflow_step("3", "#2185d0", "play", "Run analysis", "..."),
        rx.el.div(fomantic_icon("chevron-left", ...), "Select a sample from the left panel to begin"),
    )
```

**Key principles:**
- Use the DNA palette colors for step numbers (green → teal → blue, matching the gradient)
- Explain the workflow, don't duplicate UI controls
- Point the user to where they should act (e.g. "left panel") with a directional hint
- Show a branded icon (DNA) to reinforce identity

### Selected Item Highlighting

File list items use **teal** (`#00b5ad`) for the selected state, differentiating from the primary blue used for buttons/actions:

```python
style={
    "backgroundColor": rx.cond(is_selected, "#00b5ad", "#fff"),
    "color": rx.cond(is_selected, "#fff", "inherit"),
    "border": rx.cond(is_selected, "1px solid #009c95", "1px solid #e0e0e0"),
}
```

## 9. Anti-Patterns

Avoid these patterns:

- Ghost buttons (transparent backgrounds)
- Small icons (< 2rem)
- Thin borders
- Subtle/muted colors for important actions
- Dense layouts with tight spacing
- **Dynamic values in `fomantic_icon()` or `rx.icon()` name parameter**
- **Underscore or wrong-order icon names**
- **Python conditionals for reactive styling** (use `rx.cond`)
- **Duplicating controls across panels** (e.g. file upload in both left and right panels)
- **Vague empty states** ("Select a file") — show workflow onboarding instead
- **Hardcoded colors that don't match a Fomantic named color** — always use the 5-color DNA palette
- **Using `#2185d0` for all accent colors** — match `accent_color` to the parent segment's Fomantic color
- **Using orange** (`#f2711c`) — not in our palette; use `yellow` for warnings or `red` for errors
