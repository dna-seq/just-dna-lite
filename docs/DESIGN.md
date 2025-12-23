# Design System: Fomantic-Legacy with DaisyUI and Reflex

This document defines the visual design language for **just-dna-lite** UI components.

## Core Aesthetic

"Chunky & Tactile" feel. High affordance for non-professional users. Elements must look like physical objects with clear boundaries and solid fills.

## 1. Component Styling

- **Buttons:** `btn-lg`, `rounded-md`, `font-bold`. Solid backgrounds only (no ghost buttons).
- **Segments:** `card bg-base-100 border border-base-300 shadow-sm rounded-md p-6`.
- **Inputs:** `input-bordered`, `input-lg`. High contrast borders.
- **Icons:** Oversized (min 2rem / `w-8 h-8`). Pair with every major label.
- **Lucide Icons:** Use standard names: `cloud-upload`, `circle-play`, `circle-alert`, `dna`, `activity`.

## 2. Layout & Spacing

- **Spacing:** Liberal use of `gap-8` and `<div class="divider"></div>`.
- **Typography:** Base `text-lg`, headers `text-3xl` or larger.

## 3. Color & Feedback

- **Semantic Colors:**
  - `bg-success` - Safe/Benign variants
  - `bg-error` - Pathogenic variants
  - `bg-info` - VUS (Variant of Uncertain Significance) / Info

- **Tactile Feedback:**
  - `hover:shadow-lg` - Elevation on hover
  - `active:scale-95` - Press-in effect
  - `transition-all` - Smooth transitions

## 4. Component Mapping (Fomantic → DaisyUI)

| Fomantic | daisyUI / Tailwind |
| :--- | :--- |
| `ui segment` | `card card-bordered bg-base-100 p-8 rounded-md shadow-sm` |
| `ui primary button` | `btn btn-primary btn-lg rounded-md font-black uppercase shadow-md` |
| `ui message` | `alert shadow-sm border border-base-300` |
| `ui divider` | `div class="divider font-bold uppercase text-base-content/30"` |
| `ui label` | `badge badge-outline p-4 font-bold` |

## 5. Example Components

### Primary Button

```html
<button class="btn btn-primary btn-lg rounded-md font-black uppercase shadow-md hover:shadow-lg active:scale-95 transition-all">
  <lucide-icon name="circle-play" class="w-8 h-8" />
  Run Analysis
</button>
```

### Card/Segment

```html
<div class="card card-bordered bg-base-100 p-8 rounded-md shadow-sm">
  <h2 class="text-3xl font-bold">Card Title</h2>
  <div class="divider font-bold uppercase text-base-content/30">Section</div>
  <p class="text-lg">Content goes here...</p>
</div>
```

### Alert/Message

```html
<div class="alert bg-success shadow-sm border border-base-300">
  <lucide-icon name="circle-check" class="w-8 h-8" />
  <span class="text-lg font-bold">Variant is benign</span>
</div>
```

## 6. Anti-Patterns

Avoid these patterns:

- ❌ Ghost buttons (transparent backgrounds)
- ❌ Small icons (< 2rem)
- ❌ Thin borders
- ❌ Subtle/muted colors for important actions
- ❌ Dense layouts with tight spacing

