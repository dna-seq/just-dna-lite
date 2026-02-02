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
    - Verified icons (mapped by helper): `cloud-upload`, `circle-play`, `circle-alert`, `dna`, `activity`, `files`, `refresh-cw`, `file-text`, `loader-circle`, `external-link`.

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

For accordion-style collapsible sections with consistent styling:

```python
def _collapsible_header(
    expanded: rx.Var[bool],
    icon_name: str,
    title: str,
    right_badge: rx.Component,
    on_toggle: rx.EventSpec,
) -> rx.Component:
    """Reusable foldable section header."""
    return rx.el.div(
        rx.el.div(
            rx.cond(
                expanded,
                fomantic_icon("chevron-down", size=20, color="#2185d0"),
                fomantic_icon("chevron-right", size=20, color="#2185d0"),
            ),
            fomantic_icon(icon_name, size=20, color="#2185d0", style={"marginLeft": "6px"}),
            rx.el.span(title, style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "8px"}),
            style={"display": "flex", "alignItems": "center"},
        ),
        right_badge,  # e.g., rx.el.span("5 files", class_name="ui mini teal label")
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

# Usage: wrap in colored segment
rx.el.div(
    _collapsible_header(
        expanded=MyState.section_expanded,
        icon_name="folder-output",
        title="Outputs",
        right_badge=rx.el.span("5 files", class_name="ui mini teal label"),
        on_toggle=MyState.toggle_section,
    ),
    rx.cond(
        MyState.section_expanded,
        section_content(),
        rx.box(),
    ),
    class_name="ui teal segment",  # or green, blue, etc.
    style={"padding": "16px"},
)
```

**Key points:**
- Chevron icon indicates expand/collapse state (`chevron-right` → `chevron-down`)
- Right badge shows count or status
- Background color and margin animate on toggle
- Wrap in colored Fomantic segment (`ui teal segment`, `ui green segment`, etc.)

## 3. Color & Feedback

- **Semantic Colors (Fomantic Classes):**
  - `success` / `positive` / `green` - Safe/Benign variants
  - `error` / `negative` / `red` - Pathogenic variants
  - `info` / `blue` - VUS (Variant of Uncertain Significance) / Info

- **Tactile Feedback:**
  - Fomantic UI provides built-in hover and active states for most elements.
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
- `chevron-down`, `chevron-right`, `chevron-up` (for collapsible sections)
- `clock`, `plus-circle`

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

## 7. Anti-Patterns

Avoid these patterns:

- Ghost buttons (transparent backgrounds)
- Small icons (< 2rem)
- Thin borders
- Subtle/muted colors for important actions
- Dense layouts with tight spacing
- **Dynamic values in `fomantic_icon()` or `rx.icon()` name parameter**
- **Underscore or wrong-order icon names**
- **Python conditionals for reactive styling** (use `rx.cond`)
