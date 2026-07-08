"""Custom draggable div component.

Reflex's newer versions removed drag events (on_drag_start, on_drag_over,
on_drop) from standard HTML elements like Div and ReactRouterLink.
This component re-adds those triggers by subclassing rx.el.Div and
declaring them as EventHandler-typed fields, which is the API that
get_event_triggers() in this Reflex version reads via args_specs_from_fields().
"""

import reflex as rx


class DraggableDiv(rx.el.Div):
    """A <div> that supports HTML5 drag-and-drop event triggers.

    Actively wired in _tab_item(): on_drag_start, on_drag_over, on_drop.
    Kept as extension points (not yet wired): on_drag_end, on_drag_enter,
    on_drag_leave, on_drag.
    """

    on_drag_start: rx.EventHandler
    on_drag_end: rx.EventHandler       # extension point
    on_drag_enter: rx.EventHandler     # extension point
    on_drag_leave: rx.EventHandler     # extension point
    on_drag_over: rx.EventHandler
    on_drop: rx.EventHandler
    on_drag: rx.EventHandler           # extension point


draggable_div = DraggableDiv.create

