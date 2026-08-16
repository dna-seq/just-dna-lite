"""
Genomic Annotation Page - Two-panel layout with run-centric workflow.

Left Panel: File Management (upload and selection)
Right Panel (Run-Centric View):
  - Last Run Summary: Shows most recent run with status, modules, and quick actions
  - Run Timeline: Expandable list of past runs with details
  - New Analysis Section: Collapsible module selection and run button
  - Outputs Modal: View and download output files
"""
from __future__ import annotations

import reflex as rx

from webui.components.layout import template, two_column_layout, fomantic_icon
from webui.components.draggable import draggable_div
from webui.crawler_assets import page_image_url, page_meta
from webui.state import UploadState, OutputPreviewState, PRSState, PRSTraitState
from reflex_mui_datagrid import lazyframe_grid
from prs_ui import prs_scores_selector
from prs_ui.components.prs_section import prs_workbench_mode_panel
from prs_ui.grid_style import data_grid_scroll_css
from prs_ui.mixin import sample_color
from prs_ui.pages.traits import trait_selector


RIGHT_PANEL_TAB_STYLE = {
    "cursor": "pointer",
    "display": "flex",
    "alignItems": "center",
    "gap": "8px",
    "fontSize": "1rem",
    "fontWeight": "600",
    "padding": "14px 18px",
    "minHeight": "52px",
}

RIGHT_PANEL_TAB_BADGE_STYLE = {
    "marginLeft": "4px",
    "fontSize": "0.8rem",
    "padding": "4px 7px",
}

PRS_ALIGNMENT_CSS = """
#segment-prs i.icon {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    line-height: 1 !important;
    margin: 0;
    vertical-align: middle;
}

#segment-prs .rt-Button,
#segment-prs button {
    align-items: center;
    justify-content: center;
    line-height: 1.2;
}

#segment-prs .rt-Badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    line-height: 1.2;
    white-space: nowrap;
}

#segment-prs .rt-CheckboxRoot,
#segment-prs label:has(input[type="checkbox"]) {
    display: inline-flex !important;
    align-items: center !important;
    gap: 0.45rem;
    line-height: 1.2;
    margin: 0;
    vertical-align: middle;
    white-space: nowrap;
}

#segment-prs .rt-CheckboxRoot button,
#segment-prs input[type="checkbox"] {
    flex: 0 0 auto;
    margin-top: 0;
    margin-bottom: 0;
    vertical-align: middle;
}
"""

OUTPUT_CARD_META_ROW_STYLE = {
    "display": "flex",
    "alignItems": "center",
    "gap": "12px",
    "marginTop": "8px",
    "flexWrap": "wrap",
}


# Schematic of the whole-genome sequencing journey shown on the welcome panel.
# Static inline SVG (no state), so novices can see where the VCF they must
# download from their sequencing provider fits into the pipeline. The dashed
# "zoom rays" at the bottom visually connect the Just-DNA-Lite box to the
# how-to-use panel rendered directly below the SVG.
SEQUENCING_JOURNEY_SVG = """
<svg viewBox="0 0 1010 262" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Full-genome sequencing pipeline: DNA sample, sequencing (FASTQ), alignment (BAM/CRAM), variant calling (VCF - the file you download from your provider), then annotation and PRS in this app."
     style="width: 100%; height: auto; font-family: Lato, 'Helvetica Neue', Arial, sans-serif;">
  <defs>
    <marker id="jd-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="#b5b5b5"/>
    </marker>
    <marker id="jd-arrow-red" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="#db2828"/>
    </marker>
  </defs>

  <!-- "You are here" callout above the VCF stage -->
  <text x="716" y="26" text-anchor="middle" font-size="22" font-weight="800" fill="#db2828">You are here</text>
  <text x="716" y="46" text-anchor="middle" font-size="13" font-weight="600" fill="#db2828">download this file from your sequencing provider</text>
  <line x1="716" y1="52" x2="716" y2="92" stroke="#db2828" stroke-width="2.5" marker-end="url(#jd-arrow-red)"/>

  <!-- Bounding box: full-genome sequencing (done by the provider) -->
  <rect x="8" y="64" width="804" height="142" rx="12" fill="#fdfdfd" stroke="#c9c9c9" stroke-width="1.5"/>
  <text x="26" y="90" font-size="15" font-weight="700" fill="#555">Full-genome sequencing</text>
  <text x="212" y="90" font-size="12" fill="#999">&#8212; already done by your sequencing provider</text>

  <!-- Stage 1: DNA sample -->
  <rect x="24" y="100" width="160" height="100" rx="10" fill="#fafafa" stroke="#d4d4d5" stroke-width="1.5"/>
  <text x="104" y="124" text-anchor="middle" font-size="14" font-weight="700" fill="#333">DNA sample</text>
  <text x="104" y="141" text-anchor="middle" font-size="11" fill="#777">what you sent in</text>
  <rect x="54" y="154" width="100" height="24" rx="12" fill="#fff" stroke="#bbb"/>
  <text x="104" y="170" text-anchor="middle" font-size="11" font-weight="600" fill="#666">saliva / blood</text>

  <line x1="188" y1="150" x2="224" y2="150" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-arrow)"/>

  <!-- Stage 2: Sequencing -->
  <rect x="228" y="100" width="160" height="100" rx="10" fill="#fafafa" stroke="#d4d4d5" stroke-width="1.5"/>
  <text x="308" y="124" text-anchor="middle" font-size="14" font-weight="700" fill="#333">Sequencing</text>
  <text x="308" y="141" text-anchor="middle" font-size="11" fill="#777">machine reads your DNA</text>
  <rect x="274" y="154" width="68" height="24" rx="12" fill="#fff" stroke="#bbb"/>
  <text x="308" y="170" text-anchor="middle" font-size="11" font-weight="600" fill="#666">FASTQ</text>

  <line x1="392" y1="150" x2="428" y2="150" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-arrow)"/>

  <!-- Stage 3: Alignment -->
  <rect x="432" y="100" width="160" height="100" rx="10" fill="#fafafa" stroke="#d4d4d5" stroke-width="1.5"/>
  <text x="512" y="124" text-anchor="middle" font-size="14" font-weight="700" fill="#333">Alignment</text>
  <text x="512" y="141" text-anchor="middle" font-size="11" fill="#777">reads mapped to genome</text>
  <rect x="463" y="154" width="98" height="24" rx="12" fill="#fff" stroke="#bbb"/>
  <text x="512" y="170" text-anchor="middle" font-size="11" font-weight="600" fill="#666">BAM / CRAM</text>

  <line x1="596" y1="150" x2="632" y2="150" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-arrow)"/>

  <!-- Stage 4: Variant calling (the VCF the user needs) -->
  <rect x="636" y="100" width="160" height="100" rx="10" fill="#fff6f6" stroke="#db2828" stroke-width="2"/>
  <text x="716" y="124" text-anchor="middle" font-size="14" font-weight="700" fill="#333">Variant calling</text>
  <text x="716" y="141" text-anchor="middle" font-size="11" fill="#777">your genetic variants</text>
  <rect x="651" y="154" width="130" height="24" rx="12" fill="#fff" stroke="#db2828" stroke-width="1.5"/>
  <text x="716" y="170" text-anchor="middle" font-size="11" font-weight="700" fill="#db2828">VCF (.vcf / .vcf.gz)</text>
  <ellipse cx="716" cy="167" rx="74" ry="19" fill="none" stroke="#db2828" stroke-width="2" stroke-dasharray="6 4"/>

  <line x1="800" y1="150" x2="838" y2="150" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-arrow)"/>

  <!-- Stage 5: Annotation and PRS (this app) -->
  <rect x="842" y="100" width="160" height="100" rx="10" fill="#eafaf8" stroke="#00b5ad" stroke-width="2"/>
  <text x="922" y="124" text-anchor="middle" font-size="14" font-weight="700" fill="#00756f">Annotation &amp; PRS</text>
  <text x="922" y="141" text-anchor="middle" font-size="11" fill="#00877f">Just-DNA-Lite &#8212; this app</text>
  <rect x="865" y="154" width="114" height="24" rx="12" fill="#fff" stroke="#00b5ad"/>
  <text x="922" y="170" text-anchor="middle" font-size="11" font-weight="600" fill="#00877f">reports &amp; scores</text>

  <!-- Zoom rays: magnify the app box into the how-to panel below -->
  <line x1="842" y1="208" x2="12" y2="258" stroke="#00b5ad" stroke-width="2" stroke-dasharray="7 5" opacity="0.75"/>
  <line x1="1002" y1="208" x2="1002" y2="258" stroke="#00b5ad" stroke-width="2" stroke-dasharray="7 5" opacity="0.75"/>
</svg>
"""


# DAG of the in-app workflow, drawn in the same style as the pipeline schematic
# so it reads as a map rather than as UI controls. Only the two pill "buttons"
# in the "Add a sample" node are clickable (inline onclick guides that scroll
# to and flash the real left-panel control); every downstream node is muted
# grey/purple to signal it is not interactive.
#
# Topology: add sample -> {annotation modules and/or PRS} -> explore results
# -> ask AI about results. Annotation modules <-> Module Manager (new modules
# extend the list), and Module Manager takes research papers + the AI agent
# as inputs.
JOURNEY_DAG_SVG = """
<svg viewBox="0 0 1010 330" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Just-DNA-Lite workflow: add a sample (upload your VCF or try a public genome), then annotation modules and/or PRS risk scores, both leading to explore results, then ask AI about your results. Annotation modules exchange with the Module Manager, which takes research papers and the AI agent as inputs."
     style="width: 100%; height: auto; font-family: Lato, 'Helvetica Neue', Arial, sans-serif;">
  <defs>
    <marker id="jd-dag-arrow" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="#b5b5b5"/>
    </marker>
    <marker id="jd-dag-arrow-rev" markerWidth="9" markerHeight="9" refX="2" refY="4.5" orient="auto">
      <path d="M9,0 L1,4.5 L9,9 z" fill="#b5b5b5"/>
    </marker>
    <marker id="jd-dag-arrow-purple" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L8,4.5 L0,9 z" fill="#c9a8dd"/>
    </marker>
  </defs>

  <!-- Edges (drawn first, nodes on top) -->
  <!-- fork: add sample -> modules / PRS -->
  <path d="M216,155 C256,140 256,95 281,95" fill="none" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-dag-arrow)"/>
  <path d="M216,195 C256,215 256,285 281,285" fill="none" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-dag-arrow)"/>
  <text x="395" y="193" text-anchor="middle" font-size="11" font-weight="700" fill="#999">and / or</text>
  <!-- merge: modules / PRS -> explore results -->
  <path d="M505,112 C540,112 540,165 556,165" fill="none" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-dag-arrow)"/>
  <path d="M505,285 C540,285 540,185 556,185" fill="none" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-dag-arrow)"/>
  <!-- modules <-> module manager (two-sided: new modules extend the list) -->
  <path d="M509,80 L786,80" fill="none" stroke="#b5b5b5" stroke-width="2" marker-start="url(#jd-dag-arrow-rev)" marker-end="url(#jd-dag-arrow)"/>
  <text x="647" y="70" text-anchor="middle" font-size="10.5" font-style="italic" fill="#999">new modules extend the list</text>
  <!-- explore results -> ask AI -->
  <path d="M740,185 C768,195 762,285 786,285" fill="none" stroke="#b5b5b5" stroke-width="2" marker-end="url(#jd-dag-arrow)"/>
  <!-- inputs into module manager: papers + AI agent -->
  <path d="M821,30 L821,56" fill="none" stroke="#c9a8dd" stroke-width="2" marker-end="url(#jd-dag-arrow-purple)"/>
  <path d="M930,30 L930,56" fill="none" stroke="#c9a8dd" stroke-width="2" marker-end="url(#jd-dag-arrow-purple)"/>

  <!-- Inputs of the Module Manager: research papers + AI agent -->
  <rect x="766" y="6" width="110" height="22" rx="11" fill="#faf7fc" stroke="#c9a8dd" stroke-width="1.5" stroke-dasharray="4 3"/>
  <text x="821" y="21" text-anchor="middle" font-size="10" font-weight="600" fill="#75589c">research papers</text>
  <rect x="892" y="6" width="76" height="22" rx="11" fill="#faf7fc" stroke="#c9a8dd" stroke-width="1.5" stroke-dasharray="4 3"/>
  <text x="930" y="21" text-anchor="middle" font-size="10" font-weight="600" fill="#75589c">AI agent</text>

  <!-- Node 1: Add a sample (the only interactive node) -->
  <rect x="16" y="110" width="200" height="130" rx="12" fill="#ffffff" stroke="#21ba45" stroke-width="2"/>
  <circle cx="28" cy="110" r="13" fill="#21ba45"/>
  <text x="28" y="115" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">1</text>
  <text x="116" y="137" text-anchor="middle" font-size="15" font-weight="700" fill="#333">Add a sample</text>
  <text x="116" y="154" text-anchor="middle" font-size="11" font-weight="700" fill="#f2711c">&#8592; in the left panel</text>
  <g class="jd-svg-click" onclick="event.stopPropagation();var ids=['add-sample-form','file-column-content'];var el=null;for(var i=0;i!==ids.length;i++){el=document.getElementById(ids[i]);if(el){break;}}if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.classList.remove('jd-flash-target');void el.offsetWidth;el.classList.add('jd-flash-target');setTimeout(function(){el.classList.remove('jd-flash-target');},2300);}">
    <rect x="33" y="163" width="166" height="24" rx="12" fill="#fff" stroke="#21ba45" stroke-width="1.5"/>
    <text x="116" y="179" text-anchor="middle" font-size="11" font-weight="700" fill="#1e9e3e">Upload your VCF</text>
  </g>
  <text x="116" y="197" text-anchor="middle" font-size="9.5" font-weight="700" fill="#999">or</text>
  <g class="jd-svg-click" onclick="event.stopPropagation();var ids=['public-genome-hint','file-column-content'];var el=null;for(var i=0;i!==ids.length;i++){el=document.getElementById(ids[i]);if(el){break;}}if(el){el.scrollIntoView({behavior:'smooth',block:'center'});el.classList.remove('jd-flash-target');void el.offsetWidth;el.classList.add('jd-flash-target');setTimeout(function(){el.classList.remove('jd-flash-target');},2300);}">
    <rect x="33" y="202" width="166" height="24" rx="12" fill="#fff" stroke="#00b5ad" stroke-width="1.5"/>
    <text x="116" y="218" text-anchor="middle" font-size="11" font-weight="700" fill="#00877f">Try a public genome</text>
  </g>

  <!-- Node 2a: Annotation modules (muted, not clickable) -->
  <rect x="285" y="60" width="220" height="70" rx="10" fill="#f7f8f8" stroke="#9fcfcc" stroke-width="1.5"/>
  <circle cx="297" cy="60" r="12" fill="#7fbcb8"/>
  <text x="297" y="65" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">2</text>
  <text x="395" y="86" text-anchor="middle" font-size="14" font-weight="700" fill="#556">Annotation modules</text>
  <text x="395" y="103" text-anchor="middle" font-size="10.5" fill="#889">pick modules (longevity, cardio &#8230;)</text>
  <text x="395" y="117" text-anchor="middle" font-size="10.5" fill="#889">and run the annotation pipeline</text>

  <!-- Node 2b: PRS (muted, not clickable) -->
  <rect x="285" y="250" width="220" height="70" rx="10" fill="#f7f8f8" stroke="#a8c6e2" stroke-width="1.5"/>
  <circle cx="297" cy="250" r="12" fill="#8fb3d9"/>
  <text x="297" y="255" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">2</text>
  <text x="395" y="276" text-anchor="middle" font-size="14" font-weight="700" fill="#556">PRS &#8212; risk scores</text>
  <text x="395" y="293" text-anchor="middle" font-size="10.5" fill="#889">compute polygenic risk scores</text>
  <text x="395" y="307" text-anchor="middle" font-size="10.5" fill="#889">directly, no modules needed</text>

  <!-- Node 3: Explore results (vertically centered between the branches) -->
  <rect x="560" y="140" width="180" height="70" rx="10" fill="#f7f8f8" stroke="#9bb5cc" stroke-width="1.5"/>
  <circle cx="572" cy="140" r="12" fill="#7f9cb8"/>
  <text x="572" y="145" text-anchor="middle" font-size="12" font-weight="700" fill="#fff">3</text>
  <text x="650" y="166" text-anchor="middle" font-size="14" font-weight="700" fill="#556">Explore results</text>
  <text x="650" y="183" text-anchor="middle" font-size="10.5" fill="#889">reports, tables, and scores</text>
  <text x="650" y="197" text-anchor="middle" font-size="10.5" fill="#889">appear in this panel</text>

  <!-- Node 4: Module Manager (muted purple, exchanges with annotation modules) -->
  <rect x="790" y="60" width="200" height="70" rx="10" fill="#faf7fc" stroke="#c9a8dd" stroke-width="1.5"/>
  <circle cx="802" cy="60" r="12" fill="#b57edb"/>
  <text x="802" y="65" text-anchor="middle" font-size="13" font-weight="700" fill="#fff">+</text>
  <text x="890" y="88" text-anchor="middle" font-size="13.5" font-weight="700" fill="#75589c">Module Manager</text>
  <text x="890" y="105" text-anchor="middle" font-size="10.5" fill="#a08cb8">create &amp; install new modules,</text>
  <text x="890" y="119" text-anchor="middle" font-size="10.5" fill="#a08cb8">its own tab in the top menu</text>

  <!-- Node 5: Ask AI about results (muted purple) -->
  <rect x="790" y="250" width="200" height="70" rx="10" fill="#faf7fc" stroke="#c9a8dd" stroke-width="1.5"/>
  <circle cx="802" cy="250" r="12" fill="#b57edb"/>
  <text x="802" y="254" text-anchor="middle" font-size="9" font-weight="700" fill="#fff">AI</text>
  <text x="890" y="276" text-anchor="middle" font-size="13.5" font-weight="700" fill="#75589c">Ask AI about results</text>
  <text x="890" y="293" text-anchor="middle" font-size="10.5" fill="#a08cb8">take your reports to any</text>
  <text x="890" y="307" text-anchor="middle" font-size="10.5" fill="#a08cb8">AI assistant you trust</text>
</svg>
"""


# Onboarding CSS: nudge animation for "use the left panel" arrows, a flash
# highlight for guide targets, and hover affordance for clickable guides.
LEFT_NUDGE_CSS = """
@keyframes jd-nudge {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(-8px); }
}
.jd-left-nudge {
  display: inline-flex;
  align-items: center;
  animation: jd-nudge 1.6s ease-in-out infinite;
}
@keyframes jd-flash {
  0% { box-shadow: 0 0 0 0 rgba(242, 113, 28, 0.85); }
  100% { box-shadow: 0 0 0 16px rgba(242, 113, 28, 0); }
}
.jd-flash-target {
  animation: jd-flash 0.75s ease-out 3;
}
.jd-svg-click {
  cursor: pointer;
}
.jd-svg-click:hover rect {
  stroke-width: 2.5;
  fill: #f2faf7;
}
"""


def sequencing_journey_diagram() -> rx.Component:
    """Sequencing-journey schematic plus the zoomed-in "how to use" panel.

    The first SVG shows the full-genome sequencing pipeline with the VCF
    circled; dashed rays "magnify" the Just-DNA-Lite box into a second SVG
    below: a DAG of the in-app workflow (add sample, then annotation modules
    and/or PRS, both merging into explore results, with the AI module creator
    as a follow-up node). Only the two pills in the "Add a sample" DAG node
    are clickable; they flash the matching left-panel control.
    """
    return rx.el.div(
        rx.el.style(LEFT_NUDGE_CSS),
        rx.html(SEQUENCING_JOURNEY_SVG),

        # Zoomed-in view of the Just-DNA-Lite box: what you do inside the app
        rx.el.div(
            rx.el.div(
                fomantic_icon("search plus", size=20, color="#00b5ad", style={"marginRight": "8px"}),
                rx.el.span(
                    "Inside Just-DNA-Lite \u2014 your steps",
                    style={"fontSize": "1.3rem", "fontWeight": "800", "color": "#00756f"},
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "marginBottom": "6px",
                },
            ),
            rx.el.div(
                "The green buttons are clickable and point to the matching controls; "
                "grey boxes are a map of what happens where.",
                style={"fontSize": "0.9rem", "color": "#7aa8a4", "marginBottom": "14px"},
            ),
            rx.html(JOURNEY_DAG_SVG),
            style={
                "border": "2px dashed #00b5ad",
                "borderRadius": "12px",
                "backgroundColor": "#f6fffd",
                "padding": "22px 24px 24px 24px",
                "marginTop": "-3px",
            },
        ),
        style={
            "maxWidth": "1180px",
            "width": "100%",
            "margin": "0 auto 40px auto",
            "textAlign": "center",
        },
    )


# ============================================================================
# COLUMN 1: FILE MANAGEMENT
# ============================================================================

def add_sample_form() -> rx.Component:
    """
    Compact Add Sample form - minimal file picker + metadata fields.
    Single "Add Sample" button submits both file and metadata together.
    """
    return rx.el.div(
        # Form header with inline file picker
        rx.el.div(
            fomantic_icon("plus-circle", size=16, color="#2185d0"),  # primary blue
            rx.el.span(" Add Sample", style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "4px"}),
            # Unstyled root: StyledUpload defaults to padding: 5em (dropzone).
            rx.upload.root(
                rx.el.button(
                    fomantic_icon("file-text", size=16, color="#666"),
                    rx.cond(
                        rx.selected_files("vcf_upload").length() > 0,
                        rx.foreach(
                            rx.selected_files("vcf_upload"),
                            lambda f: rx.el.span(
                                f,
                                style={
                                    "marginLeft": "4px",
                                    "color": "#00b5ad",
                                    "maxWidth": "120px",
                                    "overflow": "hidden",
                                    "textOverflow": "ellipsis",
                                    "whiteSpace": "nowrap",
                                },
                            ),
                        ),
                        rx.el.span("Select VCF..."),
                    ),
                    type="button",
                    class_name="ui large button",
                ),
                id="vcf_upload",
                style={"marginLeft": "auto"},
                multiple=False,
                accept={
                    "application/vcf": [".vcf", ".vcf.gz"],
                    "text/vcf": [".vcf", ".vcf.gz"],
                    "application/gzip": [".vcf.gz"],
                },
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        
        # Compact form - 2 columns. key=form_key remounts every field after
        # upload so uncontrolled inputs and native <select>s return to defaults.
        rx.el.div(
            # Row 1: Subject ID + Sex
            rx.el.div(
                rx.el.input(
                    default_value=UploadState.new_sample_subject_id,
                    on_change=UploadState.set_new_sample_subject_id,
                    placeholder="Subject ID",
                    style={"flex": "1", "padding": "6px 8px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.95rem"},
                ),
                rx.el.select(
                    rx.foreach(UploadState.sex_options, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_sex,
                    on_change=UploadState.set_new_sample_sex,
                    style={"width": "80px", "padding": "6px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.95rem", "backgroundColor": "#fff"},
                ),
                style={"display": "flex", "gap": "6px", "marginBottom": "6px"},
            ),
            # Row 2: Species + Reference Genome
            rx.el.div(
                rx.el.select(
                    rx.foreach(UploadState.species_options, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_species,
                    on_change=UploadState.set_new_sample_species,
                    style={"flex": "1", "padding": "6px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.95rem", "backgroundColor": "#fff"},
                ),
                rx.el.select(
                    rx.foreach(UploadState.new_sample_available_genomes, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_reference_genome,
                    on_change=UploadState.set_new_sample_reference_genome,
                    title="The map of human DNA your VCF was written against. Most current files use GRCh38.",
                    style={"width": "100px", "padding": "6px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.95rem", "backgroundColor": "#fff"},
                ),
                style={"display": "flex", "gap": "6px", "marginBottom": "6px"},
            ),
            # Row 3: Tissue + Study Name
            rx.el.div(
                rx.el.select(
                    rx.foreach(UploadState.tissue_options, lambda opt: rx.el.option(opt, value=opt)),
                    value=UploadState.new_sample_tissue,
                    on_change=UploadState.set_new_sample_tissue,
                    style={"flex": "1", "padding": "6px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.95rem", "backgroundColor": "#fff"},
                ),
                rx.el.input(
                    default_value=UploadState.new_sample_study_name,
                    on_change=UploadState.set_new_sample_study_name,
                    placeholder="Study name",
                    style={"flex": "1", "padding": "6px 8px", "borderRadius": "4px", "border": "1px solid #ddd", "fontSize": "0.95rem"},
                ),
                style={"display": "flex", "gap": "6px", "marginBottom": "8px"},
            ),
            # Add button
            rx.el.button(
                rx.cond(
                    UploadState.uploading,
                    rx.el.i("", class_name="spinner loading icon"),
                    rx.el.i("", class_name="plus icon"),
                ),
                " Add",
                on_click=UploadState.handle_upload_with_metadata(rx.upload_files(upload_id="vcf_upload")),
                disabled=rx.selected_files("vcf_upload").length() == 0,
                class_name="ui primary small button",
                style={"width": "100%"},
            ),

            # Divider + Zenodo import (inline, inside the same segment)
            rx.el.div(
                rx.text("or import from Zenodo"),
                class_name="ui horizontal divider",
                style={"margin": "10px 0 8px 0", "fontSize": "0.85rem", "color": "#aaa"},
            ),
            rx.el.div(
                rx.el.input(
                    value=UploadState.zenodo_url_input,
                    on_change=UploadState.set_zenodo_url_input,
                    placeholder="https://zenodo.org/records/...",
                    style={
                        "flex": "1",
                        "padding": "6px 8px",
                        "borderRadius": "4px",
                        "border": "1px solid #ddd",
                        "fontSize": "0.95rem",
                    },
                ),
                rx.el.button(
                    rx.cond(
                        UploadState.zenodo_importing,
                        rx.el.i("", class_name="spinner loading icon"),
                        rx.el.i("", class_name="cloud upload icon"),
                    ),
                    on_click=UploadState.handle_zenodo_import,
                    disabled=UploadState.zenodo_importing,
                    class_name="ui mini purple icon button",
                    style={"marginLeft": "6px"},
                    title="Import from Zenodo",
                ),
                style={"display": "flex", "alignItems": "center"},
            ),
            key=UploadState.form_key,
        ),

        class_name="ui blue segment",
        style={"padding": "10px 12px", "marginBottom": "12px"},
        id="add-sample-form",
    )


def file_status_label(status: rx.Var[str]) -> rx.Component:
    """Return a colored label based on file status (DNA palette: green/yellow/red/grey)."""
    return rx.match(
        status,
        ("completed", rx.el.span("completed", class_name="ui green label")),
        ("running", rx.el.span("running", class_name="ui yellow label")),
        ("uploaded", rx.el.span("uploaded", class_name="ui label")),
        ("error", rx.el.span("error", class_name="ui red label")),
        rx.el.span(status, class_name="ui grey label"),
    )


def file_metadata_section() -> rx.Component:
    """
    Display metadata for the currently selected file using Fomantic UI form.
    
    Uses proper form structure with:
    - Required fields marked with asterisk
    - Two-column layout for compact display
    - Grouped related fields
    """
    info = UploadState.selected_file_info
    
    def required_field(label: str) -> rx.Component:
        """Label with required asterisk."""
        return rx.el.label(
            label,
            rx.el.span(" *", style={"color": "#db2828"}),  # Fomantic red
        )
    
    def optional_field(label: str) -> rx.Component:
        """Label for optional field."""
        return rx.el.label(label)
    
    return rx.cond(
        UploadState.has_file_metadata,
        rx.el.div(
            # Form header
            rx.el.div(
                fomantic_icon("file-text", size=18, color="#21ba45"),
                rx.el.span(
                    " Sample: ",
                    rx.el.strong(info["sample_name"].to(str)),
                    style={"fontSize": "1.1rem", "marginLeft": "6px"},
                ),
                rx.el.span(
                    " (",
                    info["size_mb"].to(str),
                    " MB)",
                    style={"fontSize": "0.95rem", "color": "#888", "marginLeft": "4px"},
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "12px"},
            ),
            
            # Fomantic UI Form
            rx.el.form(
                # === REQUIRED FIELDS SECTION ===
                rx.el.h5("Required Fields", class_name="ui dividing header", style={"marginTop": "0"}),
                
                # Row 1: Subject ID and Sex (two fields inline)
                rx.el.div(
                    rx.el.div(
                        required_field("Subject ID"),
                        rx.el.input(
                            type="text",
                            key=UploadState.selected_file,
                            default_value=UploadState.current_subject_id,
                            on_change=UploadState.update_file_subject_id.debounce(300),
                            placeholder="e.g. Patient-001",
                        ),
                        class_name="required field",
                    ),
                    rx.el.div(
                        required_field("Sex"),
                        rx.el.select(
                            rx.foreach(
                                UploadState.sex_options,
                                lambda opt: rx.el.option(opt, value=opt),
                            ),
                            value=UploadState.current_sex,
                            on_change=UploadState.update_file_sex,
                            class_name="ui dropdown",
                        ),
                        class_name="required field",
                    ),
                    class_name="two fields",
                ),
                
                # Row 2: Species and Reference Genome
                rx.el.div(
                    rx.el.div(
                        required_field("Species"),
                        rx.el.select(
                            rx.foreach(
                                UploadState.species_options,
                                lambda opt: rx.el.option(opt, value=opt),
                            ),
                            value=UploadState.current_species,
                            on_change=UploadState.update_file_species,
                            class_name="ui dropdown",
                        ),
                        class_name="required field",
                    ),
                    rx.el.div(
                        required_field("Reference Genome"),
                        rx.el.select(
                            rx.foreach(
                                UploadState.available_reference_genomes,
                                lambda opt: rx.el.option(opt, value=opt),
                            ),
                            value=UploadState.current_reference_genome,
                            on_change=UploadState.update_file_reference_genome,
                            class_name="ui dropdown",
                        ),
                        class_name="required field",
                    ),
                    class_name="two fields",
                ),
                
                # Row 3: Tissue
                rx.el.div(
                    required_field("Tissue Source"),
                    rx.el.select(
                        rx.foreach(
                            UploadState.tissue_options,
                            lambda opt: rx.el.option(opt, value=opt),
                        ),
                        value=UploadState.current_tissue,
                        on_change=UploadState.update_file_tissue,
                        class_name="ui dropdown",
                    ),
                    class_name="required field",
                ),
                
                # === OPTIONAL FIELDS SECTION ===
                rx.el.h5("Optional Fields", class_name="ui dividing header"),
                
                # Study Name
                rx.el.div(
                    optional_field("Study / Project"),
                    rx.el.input(
                        type="text",
                        key=UploadState.selected_file + "_study",
                        default_value=UploadState.current_study_name,
                        on_change=UploadState.update_file_study_name.debounce(300),
                        placeholder="e.g. Longevity Study 2026",
                    ),
                    class_name="field",
                ),
                
                # Notes
                rx.el.div(
                    optional_field("Notes"),
                    rx.el.textarea(
                        key=UploadState.selected_file + "_notes",
                        default_value=UploadState.current_notes,
                        on_change=UploadState.update_file_notes.debounce(300),
                        placeholder="Additional notes about this sample...",
                        rows=2,
                    ),
                    class_name="field",
                ),
                
                # === CUSTOM FIELDS SECTION ===
                rx.el.h5("Custom Fields", class_name="ui dividing header"),
                
                # Existing custom fields
                rx.cond(
                    UploadState.has_custom_fields,
                    rx.el.div(
                        rx.foreach(
                            UploadState.custom_fields_list,
                            lambda field: rx.el.div(
                                rx.el.span(
                                    field["name"].to(str),
                                    class_name="ui label",
                                    style={"marginRight": "8px"},
                                ),
                                rx.el.span(field["value"].to(str), style={"flex": "1"}),
                                rx.el.button(
                                    fomantic_icon("x", size=12),
                                    on_click=lambda f=field: UploadState.remove_custom_field(f["name"].to(str)),
                                    class_name="ui mini icon button",
                                    type="button",
                                    style={"marginLeft": "8px"},
                                ),
                                style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
                            ),
                        ),
                        style={"marginBottom": "10px"},
                    ),
                    rx.box(),
                ),
                
                # Add new custom field
                rx.el.div(
                    rx.el.div(
                        rx.el.input(
                            type="text",
                            default_value=UploadState.new_custom_field_name,
                            on_change=UploadState.set_new_field_name.debounce(300),
                            placeholder="Field name",
                        ),
                        class_name="field",
                        style={"flex": "1"},
                    ),
                    rx.el.div(
                        rx.el.input(
                            type="text",
                            default_value=UploadState.new_custom_field_value,
                            on_change=UploadState.set_new_field_value.debounce(300),
                            placeholder="Value",
                        ),
                        class_name="field",
                        style={"flex": "2"},
                    ),
                    rx.el.button(
                        fomantic_icon("plus", size=14),
                        " Add",
                        on_click=UploadState.save_new_custom_field,
                        class_name="ui mini positive button",
                        type="button",
                    ),
                    class_name="inline fields",
                    style={"alignItems": "flex-end"},
                ),
                
                rx.el.div(class_name="ui divider"),
                
                # Save button
                rx.el.button(
                    fomantic_icon("save", size=16),
                    " Save Metadata",
                    on_click=UploadState.save_metadata_to_dagster,
                    class_name="ui green button",
                    type="button",
                ),
                rx.el.span(
                    " Persists to Dagster asset catalog",
                    style={"fontSize": "0.9rem", "color": "#888", "marginLeft": "10px"},
                ),
                
                class_name="ui form",
            ),
            
            class_name="ui green segment",
            style={"marginBottom": "16px"},
            id="file-metadata-section",
        ),
        rx.fragment(),
    )


def file_item_expanded_content() -> rx.Component:
    """
    Expanded accordion content showing metadata preview for the selected file.
    Uses the selected_file_info computed var for safe access.
    """
    info = UploadState.selected_file_info
    
    def metadata_preview_row(label: str, value: rx.Var[str], fallback: str = "—") -> rx.Component:
        """Compact metadata row for accordion content."""
        return rx.el.div(
            rx.el.span(label + ": ", style={"color": "rgba(255,255,255,0.7)", "fontSize": "0.9rem", "minWidth": "60px"}),
            rx.el.span(
                rx.cond(value != "", value, fallback),
                style={"fontSize": "0.9rem", "fontWeight": "500"},
            ),
            style={"display": "flex", "alignItems": "center", "padding": "1px 0"},
        )
    
    return rx.el.div(
        # Metadata grid (2 columns)
        rx.el.div(
            metadata_preview_row("Subject", info["subject_id"].to(str)),
            metadata_preview_row("Sex", info["sex"].to(str)),
            metadata_preview_row("Tissue", info["tissue"].to(str)),
            metadata_preview_row("Species", info["species"].to(str)),
            metadata_preview_row("Genome", info["reference_genome"].to(str)),
            metadata_preview_row("Size", info["size_mb"].to(str) + " MB"),
            style={
                "display": "grid",
                "gridTemplateColumns": "1fr 1fr",
                "gap": "2px 12px",
                "padding": "8px 12px 8px 28px",
                "backgroundColor": "rgba(0,0,0,0.1)",
                "borderTop": "1px solid rgba(255,255,255,0.15)",
            },
        ),
        # Hint text
        rx.el.div(
            fomantic_icon("edit", size=10, color="rgba(255,255,255,0.5)", style={"marginRight": "4px"}),
            rx.el.span(
                "Edit in form above",
                style={"fontSize": "0.85rem", "color": "rgba(255,255,255,0.6)"},
            ),
            style={"display": "flex", "alignItems": "center", "padding": "4px 12px 8px 28px"},
        ),
    )


def file_item(filename: rx.Var[str]) -> rx.Component:
    """
    Accordion-style file item for the library list.
    
    - Header shows Subject ID (if available) or sample name
    - VCF filename shown inside when expanded
    - Read-only metadata by default, Edit button to enable editing
    """
    is_selected = UploadState.selected_file == filename
    display_name = UploadState.sample_display_names[filename]
    upload_date = UploadState.sample_upload_dates[filename]
    
    return rx.el.div(
        # === HEADER ROW (always visible) ===
        rx.el.div(
            # Expand/collapse chevron
            rx.cond(
                is_selected,
                fomantic_icon("chevron-down", size=14, color="#fff", style={"marginRight": "6px", "flexShrink": "0"}),
                fomantic_icon("chevron-right", size=14, color="#888", style={"marginRight": "6px", "flexShrink": "0"}),
            ),
            # Name + upload date stacked
            rx.el.div(
                # Display name (Subject ID or sample name)
                rx.el.div(
                    display_name,
                    style={
                        "fontSize": "1.1rem",
                        "overflow": "hidden", 
                        "textOverflow": "ellipsis", 
                        "whiteSpace": "nowrap",
                        "fontWeight": "600",
                    },
                ),
                # Upload date
                rx.cond(
                    upload_date != "",
                    rx.el.div(
                        upload_date,
                        style={
                            "fontSize": "0.9rem",
                            "color": rx.cond(is_selected, "rgba(255,255,255,0.7)", "#999"),
                            "lineHeight": "1.2",
                        },
                    ),
                    rx.fragment(),
                ),
                style={"flex": "1", "minWidth": "0"},
            ),
            # Status label
            file_status_label(UploadState.file_statuses[filename]),
            # Delete button
            rx.el.button(
                fomantic_icon("trash-2", size=12),
                on_click=lambda: UploadState.delete_file(filename),
                class_name=rx.cond(is_selected, "ui small icon inverted button", "ui small icon button"),
                title="Delete sample",
                style={"padding": "6px 8px", "marginLeft": "6px", "flexShrink": "0"},
            ),
            on_click=lambda: UploadState.select_file(filename),
            role="button",
            tab_index=0,
            style={
                "display": "flex",
                "alignItems": "center",
                "cursor": "pointer",
                "padding": "10px 10px",
            },
        ),
        
        # === EXPANDED CONTENT (read-only metadata) ===
        rx.cond(
            is_selected & UploadState.has_file_metadata,
            file_item_readonly_content(filename),
            rx.fragment(),
        ),
        
        id=rx.Var.create("file-item-") + filename.to(str),
        style={
            "marginBottom": "4px",
            "backgroundColor": rx.cond(is_selected, "#00b5ad", "#fff"),
            "color": rx.cond(is_selected, "#fff", "inherit"),
            "border": rx.cond(is_selected, "1px solid #009c95", "1px solid #e0e0e0"),
            "borderRadius": "4px",
            "transition": "all 0.15s ease",
            "overflow": "hidden",
        },
    )


def file_item_readonly_content(filename: rx.Var[str]) -> rx.Component:
    """
    Read-only metadata display for expanded accordion item.
    Shows key info in a compact format with an Edit button.
    """
    info = UploadState.selected_file_info
    
    def meta_row(label: str, value: rx.Var[str]) -> rx.Component:
        """Compact read-only metadata row."""
        return rx.el.div(
            rx.el.span(label + ":", style={"color": "rgba(255,255,255,0.7)", "fontSize": "0.9rem", "minWidth": "68px"}),
            rx.el.span(value, style={"fontSize": "0.9rem", "fontWeight": "500"}),
            style={"display": "flex", "gap": "4px", "alignItems": "center"},
        )
    
    return rx.el.div(
        # VCF filename (always show since header may show Subject ID)
        rx.el.div(
            fomantic_icon("file-text", size=10, color="rgba(255,255,255,0.6)", style={"marginRight": "4px"}),
            rx.el.span(filename, style={"fontSize": "0.85rem", "color": "rgba(255,255,255,0.8)"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
        ),
        # Metadata in compact grid
        rx.el.div(
            meta_row("Species", info["species"].to(str)),
            meta_row("Genome", info["reference_genome"].to(str)),
            meta_row("Sex", UploadState.current_sex),
            meta_row("Tissue", UploadState.current_tissue),
            rx.cond(
                UploadState.current_study_name != "",
                meta_row("Study", UploadState.current_study_name),
                rx.fragment(),
            ),
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "2px 8px", "marginBottom": "6px"},
        ),
        # Zenodo source link (shown when file was imported from Zenodo)
        rx.cond(
            UploadState.current_zenodo_url != "",
            rx.el.div(
                fomantic_icon("external-link", size=10, color="rgba(255,255,255,0.6)", style={"marginRight": "4px", "flexShrink": "0"}),
                rx.el.a(
                    UploadState.current_zenodo_url,
                    href=UploadState.current_zenodo_url,
                    target="_blank",
                    style={
                        "fontSize": "0.85rem",
                        "color": "rgba(255,255,255,0.9)",
                        "textDecoration": "underline",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                        "whiteSpace": "nowrap",
                    },
                ),
                rx.cond(
                    UploadState.current_zenodo_license != "",
                    rx.el.span(
                        UploadState.current_zenodo_license,
                        class_name="ui mini label",
                        style={"marginLeft": "6px", "padding": "2px 6px", "fontSize": "0.75rem", "flexShrink": "0"},
                    ),
                    rx.fragment(),
                ),
                style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
            ),
            rx.fragment(),
        ),
        # Action buttons
        rx.el.div(
            rx.el.button(
                fomantic_icon("edit", size=10),
                " Edit",
                on_click=UploadState.enable_metadata_edit_mode,
                class_name="ui mini inverted button",
                style={"padding": "4px 10px", "fontSize": "0.85rem"},
            ),
            style={"display": "flex", "justifyContent": "flex-end"},
        ),
        style={"padding": "6px 10px", "backgroundColor": "rgba(0,0,0,0.1)"},
    )


def _immutable_disclaimer_box() -> rx.Component:
    """Yellow info box shown instead of upload form in immutable mode."""
    return rx.el.div(
        rx.el.div(
            fomantic_icon("lock", size=16, color="#b58105"),
            rx.el.strong(" Public Demo Mode", style={"marginLeft": "6px"}),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        rx.el.p(
            UploadState.immutable_disclaimer,
            style={"fontSize": "0.95rem", "color": "#666", "marginBottom": "8px", "lineHeight": "1.4"},
        ),
        rx.el.a(
            fomantic_icon("download", size=12),
            " Install locally",
            href="https://github.com/dna-seq/just-dna-lite#quick-start",
            target="_blank",
            class_name="ui mini yellow button",
        ),
        rx.cond(
            UploadState.allow_zenodo_import,
            rx.el.div(
                rx.el.div(
                    rx.text("or import from Zenodo"),
                    class_name="ui horizontal divider",
                    style={"margin": "10px 0 8px 0", "fontSize": "0.85rem", "color": "#aaa"},
                ),
                rx.el.div(
                    rx.el.input(
                        value=UploadState.zenodo_url_input,
                        on_change=UploadState.set_zenodo_url_input,
                        placeholder="https://zenodo.org/records/...",
                        style={
                            "flex": "1",
                            "padding": "6px 8px",
                            "borderRadius": "4px",
                            "border": "1px solid #ddd",
                            "fontSize": "0.95rem",
                        },
                    ),
                    rx.el.button(
                        rx.cond(
                            UploadState.zenodo_importing,
                            rx.el.i("", class_name="spinner loading icon"),
                            rx.el.i("", class_name="cloud upload icon"),
                        ),
                        on_click=UploadState.handle_zenodo_import,
                        disabled=UploadState.zenodo_importing,
                        class_name="ui mini purple icon button",
                        style={"marginLeft": "6px"},
                        title="Import from Zenodo",
                    ),
                    style={"display": "flex", "alignItems": "center"},
                ),
            ),
            rx.fragment(),
        ),
        class_name="ui yellow message",
        style={"padding": "12px", "marginBottom": "12px"},
    )


def _public_genome_row(sample: rx.Var) -> rx.Component:
    """One public genome entry: label, license, and Import button / Imported badge."""
    return rx.el.div(
        rx.el.span(sample["label"].to(str), style={"fontWeight": "500", "fontSize": "1rem"}),
        rx.el.span(sample["license"].to(str), class_name="ui mini teal label", style={"marginLeft": "4px"}),
        rx.cond(
            sample["imported"].to(bool),
            rx.el.span(
                rx.el.i("", class_name="check icon"),
                "Imported",
                class_name="ui mini green basic label",
                style={"marginLeft": "auto"},
            ),
            rx.el.button(
                rx.cond(
                    UploadState.zenodo_importing,
                    rx.el.i("", class_name="spinner loading icon"),
                    rx.el.i("", class_name="download icon"),
                ),
                " Import",
                on_click=lambda: UploadState.import_default_sample(sample["zenodo_url"].to(str)),
                disabled=UploadState.zenodo_importing,
                class_name="ui mini button",
                style={"marginLeft": "auto", "padding": "4px 8px"},
            ),
        ),
        style={"display": "flex", "alignItems": "center", "marginBottom": "6px"},
    )


def _public_genome_hint() -> rx.Component:
    """Non-blocking info message suggesting public genomes for quick import.

    The genome list comes from ``modules.yaml`` (``immutable_mode.default_samples``)
    via ``UploadState.default_public_samples`` — never hardcode Zenodo URLs here.
    Already-imported genomes show an "Imported" badge instead of the button.
    """
    return rx.el.div(
        rx.el.div(
            fomantic_icon("dna", size=14, color="#2185d0"),
            rx.el.span(
                " Try a public genome",
                style={"fontSize": "1.05rem", "fontWeight": "600", "marginLeft": "4px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
        ),
        rx.el.div(
            rx.foreach(UploadState.default_public_samples, _public_genome_row),
        ),
        rx.el.div(
            "Voluntarily shared under open licenses for research use.",
            style={"fontSize": "0.85rem", "color": "#999", "marginTop": "8px"},
        ),
        class_name="ui info message",
        style={"padding": "10px 12px", "marginBottom": "12px"},
        id="public-genome-hint",
    )


def _progress_indicator() -> rx.Component:
    """Non-blocking progress indicator for long operations."""
    return rx.cond(
        UploadState.has_progress_status,
        rx.el.div(
            rx.el.i("", class_name="spinner loading icon"),
            rx.el.span(
                UploadState.progress_status,
                style={"marginLeft": "8px", "fontSize": "0.95rem"},
            ),
            class_name="ui icon message",
            style={"padding": "10px 12px", "marginBottom": "12px"},
        ),
        rx.fragment(),
    )


LEFT_PANEL_TYPE_CSS = """
#file-column-content {
    font-size: 1rem;
    line-height: 1.4;
}
#file-column-content .ui.form .field > label {
    font-size: 0.95rem !important;
}
#file-column-content .ui.form input,
#file-column-content .ui.form select,
#file-column-content .ui.form textarea {
    font-size: 0.95rem !important;
}
#file-column-content .ui.dividing.header {
    font-size: 1.05rem !important;
}
#file-column-content .ui.label {
    font-size: 0.85rem;
}
#file-column-content .ui.mini.label,
#file-column-content .ui.mini.button,
#file-column-content .ui.mini.circular.label {
    font-size: 0.8rem;
}
#file-column-content .ui.message,
#file-column-content .ui.message p {
    font-size: 0.95rem;
}
"""


def file_column_content() -> rx.Component:
    """Column 1 content: Unified add sample form and library."""
    return rx.el.div(
        rx.el.style(LEFT_PANEL_TYPE_CSS),
        # ============================================================
        # ADD SAMPLE FORM or IMMUTABLE DISCLAIMER
        # ============================================================
        rx.cond(
            UploadState.is_immutable_mode,
            _immutable_disclaimer_box(),
            add_sample_form(),
        ),

        # ============================================================
        # PUBLIC GENOME SUGGESTION
        # Always visible: imported genomes show an "Imported" badge, the
        # rest keep their one-click Import button. Hiding it after the
        # first import made the second public genome unreachable and broke
        # the welcome-diagram "Try a public genome" guide target.
        # ============================================================
        _public_genome_hint(),

        # ============================================================
        # PROGRESS INDICATOR for long operations
        # ============================================================
        _progress_indicator(),

        # ============================================================
        # METADATA EDIT SECTION - Only shown when edit mode is enabled
        # ============================================================
        rx.cond(
            UploadState.has_selected_file & UploadState.metadata_edit_mode,
            rx.el.div(
                rx.el.div(
                    fomantic_icon("edit", size=16, color="#21ba45"),
                    rx.el.span(" Edit Metadata", style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "6px", "flex": "1"}),
                    rx.el.button(
                        fomantic_icon("x", size=12),
                        " Done",
                        on_click=UploadState.disable_metadata_edit_mode,
                        class_name="ui mini button",
                        style={"padding": "4px 8px"},
                    ),
                    style={"display": "flex", "alignItems": "center", "marginBottom": "10px"},
                ),
                file_metadata_section(),
                class_name="ui green segment",
                style={"padding": "10px 12px", "marginBottom": "12px"},
            ),
            rx.fragment(),
        ),

        # ============================================================
        # LIBRARY SECTION - List of uploaded samples
        # ============================================================
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    fomantic_icon("database", size=16, color="#767676"),
                    rx.el.span(" Samples", style={"fontSize": "1.1rem", "fontWeight": "600", "marginLeft": "4px"}),
                    rx.el.span(
                        UploadState.files.length(),
                        class_name="ui mini circular label",
                        style={"marginLeft": "6px"},
                    ),
                    style={"display": "flex", "alignItems": "center"},
                ),
                rx.el.button(
                    fomantic_icon("refresh-cw", size=12),
                    on_click=UploadState.on_load,
                    class_name="ui mini icon button",
                    id="refresh-files-button",
                    title="Refresh library",
                ),
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"},
            ),

            rx.cond(
                UploadState.files.length() > 0,
                rx.el.div(
                    rx.foreach(UploadState.files, file_item),
                    id="file-list",
                    style={"paddingRight": "4px"},
                ),
                rx.el.div(
                    fomantic_icon("inbox", size=40, color="#ccc"),
                    rx.el.div("No samples yet", style={"color": "#888", "marginTop": "8px"}),
                    rx.el.div(
                        "Upload a VCF file or import from Zenodo to get started",
                        style={"color": "#aaa", "fontSize": "0.95rem", "marginTop": "4px"},
                    ),
                    style={"textAlign": "center", "padding": "30px 10px"},
                    id="empty-file-list",
                ),
            ),

            class_name="ui segment",
        ),
        id="file-column-content",
    )


# ============================================================================
# MODULE SELECTION COMPONENTS
# ============================================================================

def module_icon(name: rx.Var[str]) -> rx.Component:
    """
    Return the appropriate icon for a module.
    Icons must be static strings - use rx.match for dynamic selection.
    """
    return rx.match(
        name,
        ("coronary", fomantic_icon("heart", size=24, color="#fff")),
        ("lipidmetabolism", fomantic_icon("droplets", size=24, color="#fff")),
        ("longevitymap", fomantic_icon("heart-pulse", size=24, color="#fff")),
        ("superhuman", fomantic_icon("zap", size=24, color="#fff")),
        ("vo2max", fomantic_icon("activity", size=24, color="#fff")),
        ("drugs", fomantic_icon("pill", size=24, color="#fff")),
        fomantic_icon("database", size=24, color="#fff"),  # default
    )


def fomantic_checkbox(checked: rx.Var[bool]) -> rx.Component:
    """
    Fomantic UI styled checkbox (display only, parent handles click).
    
    Structure: <div class="ui checkbox"><input type="checkbox"><label></label></div>
    The checkbox state is controlled via class name (checked adds 'checked' class).
    Note: No on_click here - parent card handles the toggle to avoid double-firing.
    """
    return rx.el.div(
        rx.el.input(
            type="checkbox",
            checked=checked,
            read_only=True,  # Controlled by parent click
            style={"pointerEvents": "none"},  # Let clicks pass through to parent
        ),
        rx.el.label(),
        class_name=rx.cond(checked, "ui checked checkbox", "ui checkbox"),
        style={"marginRight": "12px", "pointerEvents": "none"},  # Let clicks pass through
    )


def module_logo_or_icon(module: rx.Var[dict]) -> rx.Component:
    """
    Show the module's logo image if available, otherwise fall back to the static icon.
    HF logos are served from HuggingFace CDN, local logos via /api/module-logo/.
    """
    return rx.cond(
        module["logo_url"].to(str) != "",
        rx.el.img(
            src=module["logo_url"].to(str),
            alt=module["name"].to(str),
            style={
                "position": "absolute",
                "inset": "0",
                "width": "100%",
                "height": "100%",
                "objectFit": "contain",
                "borderRadius": "4px",
            },
        ),
        module_icon(module["name"]),
    )


def module_card(module: rx.Var[dict]) -> rx.Component:
    """
    Module card styled like the reference screenshot.
    Shows: Fomantic checkbox, logo/icon, title, description, repo source badge.
    """
    is_selected = module["selected"].to(bool)
    has_file = UploadState.has_selected_file
    
    return rx.el.div(
        rx.el.div(
            # Left: Fomantic UI Checkbox (display only, card handles click)
            fomantic_checkbox(checked=rx.cond(has_file, is_selected, False)),
            # Module logo or icon (colored box using per-module color from DNA palette)
            rx.el.div(
                module_logo_or_icon(module),
                style={
                    "width": "48px",
                    "height": "48px",
                    "position": "relative",
                    "backgroundColor": rx.cond(
                        module["logo_url"].to(str) != "",
                        "transparent",
                        rx.cond(
                            has_file,
                            rx.cond(is_selected, module["color"].to(str), "#bbb"),
                            "#ccc"
                        ),
                    ),
                    "borderRadius": "6px",
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "center",
                    "marginRight": "12px",
                    "flexShrink": "0",
                    "overflow": "hidden",
                },
            ),
            # Content
            rx.el.div(
                rx.el.div(
                    rx.el.strong(module["title"], style={"fontSize": "1.05rem"}),
                    style={"marginBottom": "5px"},
                ),
                rx.el.div(
                    module["description"],
                    style={"fontSize": "0.94rem", "color": "#666", "lineHeight": "1.35", "marginBottom": "8px"},
                ),
                # Source repo badge (compact, muted)
                rx.cond(
                    module["repo_id"].to(str) != "",
                    rx.el.span(
                        module["repo_id"].to(str),
                        class_name="ui mini label",
                        style={"fontSize": "0.78rem", "fontWeight": "400", "color": "#888"},
                    ),
                    rx.fragment(),
                ),
                style={"flex": "1"},
            ),
            style={
                "display": "flex", 
                "alignItems": "flex-start", 
                "width": "100%",
                "opacity": rx.cond(has_file, "1.0", "0.5"),
            },
        ),
        id=rx.Var.create("module-card-") + module["name"].to(str),
        on_click=rx.cond(has_file, UploadState.toggle_module(module["name"]), UploadState.do_nothing),
        class_name=rx.cond(has_file, "ui segment", "ui disabled segment"),
        style={
            "cursor": rx.cond(has_file, "pointer", "not-allowed"),
            "margin": "0 0 10px 0",
            "padding": "16px",
            "border": "1px solid #e0e0e0",
            "borderRadius": "6px",
            "backgroundColor": rx.cond(
                has_file,
                rx.cond(is_selected, "#f8faff", "#fff"),
                "#fafafa"
            ),
            "transition": "all 0.2s ease",
        },
    )


# ============================================================================
# RUN-CENTRIC UI COMPONENTS
# ============================================================================


def run_status_badge(status: rx.Var[str]) -> rx.Component:
    """Return a colored badge based on run status (DNA palette: green/yellow/red/grey)."""
    return rx.match(
        status,
        ("SUCCESS", rx.el.span("SUCCESS", class_name="ui green label")),
        ("FAILURE", rx.el.span("FAILURE", class_name="ui red label")),
        ("RUNNING", rx.el.span("RUNNING", class_name="ui yellow label")),
        ("QUEUED", rx.el.span("QUEUED", class_name="ui grey label")),
        ("CANCELED", rx.el.span("CANCELED", class_name="ui grey label")),
        rx.el.span(status, class_name="ui grey label"),
    )


def file_type_icon(file_type: rx.Var[str]) -> rx.Component:
    """Return an icon for file type (DNA palette)."""
    return rx.match(
        file_type,
        ("weights", fomantic_icon("scale", size=22, color="#2185d0")),
        ("annotations", fomantic_icon("file-text", size=22, color="#21ba45")),
        ("studies", fomantic_icon("book-open", size=22, color="#00b5ad")),
        ("vcf_export", fomantic_icon("dna", size=22, color="#6435c9")),
        fomantic_icon("file", size=22, color="#767676"),
    )


def file_type_label(file_type: rx.Var[str]) -> rx.Component:
    """Return a colored label for file type (DNA palette: blue/green/teal)."""
    return rx.match(
        file_type,
        ("weights", rx.el.span("weights", class_name="ui blue label")),
        ("annotations", rx.el.span("annotations", class_name="ui green label")),
        ("studies", rx.el.span("studies", class_name="ui teal label")),
        ("vcf_export", rx.el.span("vcf", class_name="ui violet label")),
        rx.el.span(file_type, class_name="ui grey label"),
    )


def _collapsible_header(
    expanded: rx.Var[bool],
    icon_name: str,
    title: str | rx.Var[str],
    right_badge: rx.Component,
    on_toggle: rx.EventSpec,
    accent_color: str | rx.Var[str] = "#2185d0",
) -> rx.Component:
    """
    Reusable foldable section header matching New Analysis style.
    Chevron + icon + title on left; optional badge on right.
    accent_color should match the parent segment color (teal/green/blue).
    """
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


def _materialization_badge(
    materialized_at: rx.Var[str],
    needs_materialization: rx.Var[bool],
) -> rx.Component:
    """Compact badge showing last materialization datetime and staleness."""
    return rx.el.div(
        rx.cond(
            materialized_at != "",
            rx.el.div(
                rx.cond(
                    needs_materialization,
                    fomantic_icon("circle-alert", size=12, color="#f2711c", style={"marginRight": "4px"}),
                    fomantic_icon("circle-check", size=12, color="#21ba45", style={"marginRight": "4px"}),
                ),
                rx.el.span(
                    materialized_at,
                    style={"fontSize": "0.86rem", "color": "#666"},
                ),
                rx.cond(
                    needs_materialization,
                    rx.el.span(
                        " stale",
                        class_name="ui mini orange label",
                        style={"marginLeft": "4px", "fontSize": "0.72rem", "padding": "3px 5px"},
                    ),
                    rx.fragment(),
                ),
                style={"display": "flex", "alignItems": "center"},
            ),
            rx.el.div(
                fomantic_icon("circle-x", size=12, color="#999", style={"marginRight": "4px"}),
                rx.el.span("not materialized", style={"fontSize": "0.86rem", "color": "#999"}),
                style={"display": "flex", "alignItems": "center"},
            ),
        ),
        style={"display": "inline-flex", "alignItems": "center"},
    )


def _run_id_badge(file_info: rx.Var[dict]) -> rx.Component:
    """Compact 'run abc12345' label under an output card, linked to the Dagster run page.

    Hidden when the file's materialization has no associated run_id (e.g.,
    runless events from PRS checkpoints or pre-tracking historical files).
    """
    run_id = file_info["run_id"].to(str)
    run_short = file_info["run_short"].to(str)
    dagster_url = UploadState.dagster_web_url + "/runs/" + run_id
    return rx.cond(
        run_short != "",
        rx.el.a(
            fomantic_icon("history", size=13, color="#2185d0"),
            " run ",
            rx.el.code(
                run_short,
                style={
                    "fontSize": "0.86rem",
                    "background": "transparent",
                    "padding": "0",
                    "color": "#2185d0",
                    "fontWeight": "700",
                },
            ),
            href=dagster_url,
            target="_blank",
            title="Open the run that produced this file in Dagster",
            style={
                "display": "inline-flex",
                "alignItems": "center",
                "gap": "5px",
                "fontSize": "0.86rem",
                "fontWeight": "600",
                "color": "#2185d0",
                "textDecoration": "none",
                "padding": "4px 8px",
                "border": "1px solid #d4e6f6",
                "borderRadius": "999px",
                "backgroundColor": "#f3f8fc",
            },
        ),
        rx.fragment(),
    )


def _output_card_meta_row(file_info: rx.Var[dict]) -> rx.Component:
    """Single metadata row for output cards: materialized date plus run link."""
    return rx.el.div(
        _materialization_badge(
            file_info["materialized_at"].to(str),
            file_info["needs_materialization"].to(bool),
        ),
        _run_id_badge(file_info),
        style=OUTPUT_CARD_META_ROW_STYLE,
    )


def output_file_card(file_info: rx.Var[dict]) -> rx.Component:
    """Card for a single output file with view and download buttons."""
    download_url = rx.cond(
        file_info["type"].to(str) == "vcf_export",
        UploadState.backend_api_url + "/api/download-vcf/" + UploadState.safe_user_id + "/" + file_info["sample_name"].to(str) + "/" + file_info["name"].to(str),
        UploadState.backend_api_url + "/api/download/" + UploadState.safe_user_id + "/" + file_info["sample_name"].to(str) + "/" + file_info["name"].to(str),
    )

    return rx.el.div(
        rx.el.div(
            # File type icon
            file_type_icon(file_info["type"]),
            # File info
            rx.el.div(
                rx.el.span(
                    file_info["name"].to(str),
                    on_click=OutputPreviewState.view_output_file(file_info["path"].to(str)),
                    style={
                        "fontSize": "1.12rem",
                        "fontWeight": "700",
                        "color": "#2185d0",
                        "cursor": "pointer",
                        "lineHeight": "1.25",
                        "wordBreak": "break-word",
                    },
                ),
                rx.el.div(
                    file_type_label(file_info["type"]),
                    rx.el.span(
                        "Produced by ",
                        rx.el.strong(file_info["module"].to(str)),
                        " module",
                        style={
                            "color": "#444",
                            "fontSize": "0.96rem",
                            "marginLeft": "6px",
                        },
                    ),
                    rx.el.span(
                        file_info["size_mb"].to(str),
                        " MB",
                        class_name="ui label",
                        style={
                            "color": "#666",
                            "fontSize": "0.86rem",
                            "marginLeft": "8px",
                        },
                    ),
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "6px",
                        "marginTop": "6px",
                        "flexWrap": "wrap",
                    },
                ),
                _output_card_meta_row(file_info),
                style={"flex": "1", "marginLeft": "14px", "minWidth": "0"},
            ),
            # Action buttons
            rx.el.div(
                # View in grid button
                rx.el.button(
                    fomantic_icon("eye", size=15),
                    on_click=OutputPreviewState.view_output_file(file_info["path"].to(str)),
                    class_name="ui icon button",
                    title="Preview in data grid",
                ),
                # Download button
                rx.el.a(
                    fomantic_icon("download", size=15),
                    href=download_url,
                    download=file_info["name"].to(str),
                    class_name="ui icon primary button",
                ),
                style={"display": "flex", "gap": "8px", "marginLeft": "auto", "flexShrink": "0"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        style={
            "padding": "16px 12px",
            "borderBottom": "1px solid #eee",
        },
    )


def report_file_card(file_info: rx.Var[dict]) -> rx.Component:
    """Card for a single report file with view and download buttons."""
    view_url = (
        UploadState.backend_api_url + "/api/report/"
        + UploadState.safe_user_id + "/"
        + file_info["sample_name"].to(str) + "/"
        + file_info["name"].to(str)
    )

    return rx.el.div(
        rx.el.div(
            # Report icon
            fomantic_icon("file-text", size=22, color="#e03997"),
            # File info
            rx.el.div(
                rx.el.a(
                    file_info["name"].to(str),
                    href=view_url,
                    target="_blank",
                    style={
                        "fontSize": "1.12rem",
                        "fontWeight": "700",
                        "color": "#e03997",
                        "textDecoration": "none",
                        "cursor": "pointer",
                        "lineHeight": "1.25",
                        "wordBreak": "break-word",
                    },
                ),
                rx.el.div(
                    rx.el.span("report", class_name="ui pink label"),
                    rx.el.span(
                        file_info["size_kb"].to(str),
                        " KB",
                        style={"color": "#666", "fontSize": "0.86rem", "marginLeft": "8px"},
                    ),
                    style={"display": "flex", "alignItems": "center", "gap": "6px", "marginTop": "6px"},
                ),
                _output_card_meta_row(file_info),
                style={"flex": "1", "marginLeft": "14px", "minWidth": "0"},
            ),
            # View button (opens in new tab)
            rx.el.a(
                fomantic_icon("external-link", size=15),
                " View",
                href=view_url,
                target="_blank",
                class_name="ui pink button",
                style={"marginLeft": "auto", "display": "flex", "alignItems": "center", "gap": "6px", "flexShrink": "0"},
            ),
            # Download button
            rx.el.a(
                fomantic_icon("download", size=15),
                href=view_url,
                download=file_info["name"].to(str),
                class_name="ui icon button",
                style={"marginLeft": "8px", "flexShrink": "0"},
            ),
            style={"display": "flex", "alignItems": "center", "width": "100%"},
        ),
        style={
            "padding": "16px 12px",
            "borderBottom": "1px solid #eee",
        },
    )


def _vcf_export_button() -> rx.Component:
    """Button to trigger VCF export for the current sample, with Dagster link while running."""
    return rx.el.div(
        rx.el.div(
            rx.cond(
                UploadState.vcf_exporting,
                rx.el.span(
                    fomantic_icon("loader-circle", size=12, color="#6435c9"),
                    " Exporting VCF...",
                    style={"color": "#6435c9", "fontSize": "0.8rem", "display": "flex", "alignItems": "center", "gap": "4px"},
                ),
                rx.fragment(),
            ),
            rx.cond(
                UploadState.vcf_export_dagster_url != "",
                rx.el.a(
                    fomantic_icon("external-link", size=12, color="#6435c9"),
                    " View in Dagster",
                    href=UploadState.vcf_export_dagster_url,
                    target="_blank",
                    style={
                        "color": "#6435c9",
                        "fontSize": "0.78rem",
                        "textDecoration": "none",
                        "display": "flex",
                        "alignItems": "center",
                        "gap": "3px",
                        "marginLeft": "8px",
                    },
                ),
                rx.fragment(),
            ),
            style={"display": "flex", "alignItems": "center"},
        ),
        rx.el.button(
            rx.cond(
                UploadState.vcf_exporting,
                fomantic_icon("loader-circle", size=14, color="white"),
                fomantic_icon("dna", size=14, color="white"),
            ),
            rx.cond(
                UploadState.vcf_exporting,
                " Exporting...",
                " Export VCF",
            ),
            on_click=UploadState.run_vcf_export,
            disabled=UploadState.vcf_exporting,
            class_name=rx.cond(
                UploadState.vcf_exporting,
                "ui mini violet loading button",
                "ui mini violet button",
            ),
            style={"display": "flex", "alignItems": "center", "gap": "4px"},
            title="Export annotated data as VCF files (per-module + combined)",
        ),
        style={
            "display": "flex",
            "justifyContent": "space-between",
            "alignItems": "center",
            "padding": "6px 10px",
            "borderBottom": "1px solid #eee",
            "backgroundColor": "#fafafa",
        },
    )


def _data_files_content() -> rx.Component:
    """Content for the Data Files sub-tab."""
    return rx.cond(
        UploadState.output_file_count > 0,
        rx.el.div(
            _vcf_export_button(),
            rx.el.div(
                rx.foreach(UploadState.output_files, output_file_card),
            ),
        ),
        rx.el.div(
            fomantic_icon("inbox", size=30, color="#ccc"),
            rx.el.div(
                "No data files yet",
                style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
            ),
            rx.el.div(
                "Run an analysis to generate parquet output files",
                style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.82rem"},
            ),
            style={"textAlign": "center", "padding": "20px 16px"},
        ),
    )


def _reports_content() -> rx.Component:
    """Content for the Reports sub-tab."""
    return rx.cond(
        UploadState.has_report_files,
        rx.el.div(
            rx.foreach(UploadState.report_files, report_file_card),
        ),
        rx.el.div(
            fomantic_icon("file-text", size=30, color="#ccc"),
            rx.el.div(
                "No reports yet",
                style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
            ),
            rx.el.div(
                "Generate a report after running the annotation pipeline",
                style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.82rem"},
            ),
            style={"textAlign": "center", "padding": "20px 16px"},
        ),
    )


def _output_preview_grid() -> rx.Component:
    """Inline output preview grid inside the Outputs section.

    Uses ``OutputPreviewState`` which has its own ``LazyFrameGridMixin``,
    completely independent from the VCF input grid.  Hidden until the
    user clicks the eye icon on a data file.
    """
    return rx.cond(
        OutputPreviewState.output_preview_expanded,
        rx.el.div(
            # Header bar with file name and row count
            rx.el.div(
                rx.el.div(
                    fomantic_icon("eye", size=16, color="#00b5ad"),
                    rx.el.strong(
                        "Output Preview",
                        style={"marginLeft": "6px"},
                    ),
                    rx.cond(
                        OutputPreviewState.output_preview_label != "",
                        rx.el.span(
                            OutputPreviewState.output_preview_label,
                            class_name="ui mini teal label",
                            style={"marginLeft": "8px"},
                        ),
                        rx.fragment(),
                    ),
                    rx.cond(
                        OutputPreviewState.has_output_preview,
                        rx.el.span(
                            OutputPreviewState.output_preview_row_count,
                            " rows",
                            class_name="ui mini teal label",
                            style={"marginLeft": "4px"},
                        ),
                        rx.fragment(),
                    ),
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "flexWrap": "wrap",
                        "gap": "4px",
                    },
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "padding": "8px 0",
                    "marginBottom": "10px",
                    "borderBottom": "1px solid #e0e0e0",
                },
            ),
            # Loading spinner
            rx.cond(
                OutputPreviewState.output_preview_loading,
                rx.el.div(
                    rx.el.i("", class_name="spinner loading icon"),
                    rx.el.span(" Loading output preview...", style={"marginLeft": "8px"}),
                    style={"padding": "16px", "color": "#666"},
                ),
                rx.fragment(),
            ),
            # Error overlay
            rx.cond(
                OutputPreviewState.has_output_preview_error,
                rx.el.div(
                    rx.el.div(
                        rx.el.strong("Failed to load output preview"),
                        rx.el.div(
                            OutputPreviewState.output_preview_error,
                            style={"fontSize": "0.85rem", "marginTop": "6px"},
                        ),
                        class_name="content",
                    ),
                    class_name="ui negative message",
                    style={"margin": "0 0 8px 0"},
                ),
                rx.fragment(),
            ),
            rx.el.div(
                lazyframe_grid(
                    OutputPreviewState,
                    show_toolbar=True,
                    show_description_in_header=True,
                    density="compact",
                    column_header_height=70,
                    height="72vh",
                    width="100%",
                    debug_log=False,
                ),
                key=OutputPreviewState.lf_grid_view_token.to(str),
                style={
                    "display": rx.cond(OutputPreviewState.has_output_preview, "block", "none"),
                },
            ),
            style={
                "marginTop": "18px",
            },
        ),
        rx.fragment(),
    )


def quality_filter_stats_banner() -> rx.Component:
    """Compact banner showing quality filter statistics from normalization.

    Displayed between the collapsible header and the data grid when
    filter stats are available from the Dagster materialization metadata.
    """
    return rx.cond(
        UploadState.has_norm_stats,
        rx.el.div(
            # Icon + main message
            rx.el.div(
                fomantic_icon("filter", size=16, color="#6435c9", style={"marginRight": "8px", "flexShrink": "0"}),
                rx.el.span(
                    "Quality Filters Applied",
                    style={"fontWeight": "600", "fontSize": "0.9rem", "marginRight": "12px"},
                ),
                # Stats chips
                rx.el.span(
                    UploadState.norm_rows_before.to(str),
                    " total",
                    class_name="ui mini label",
                    style={"marginRight": "4px"},
                ),
                fomantic_icon("arrow-right", size=12, color="#888", style={"margin": "0 4px"}),
                rx.el.span(
                    UploadState.norm_rows_after.to(str),
                    " kept",
                    class_name="ui mini green label",
                    style={"marginRight": "4px"},
                ),
                rx.cond(
                    UploadState.norm_filters_active,
                    rx.el.span(
                        UploadState.norm_rows_removed.to(str),
                        " quality filtered (",
                        UploadState.norm_removed_pct,
                        "%)",
                        class_name="ui mini orange label",
                    ),
                    rx.el.span(
                        "0 quality filtered",
                        class_name="ui mini label",
                    ),
                ),
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "flexWrap": "wrap",
                    "gap": "2px",
                },
            ),
            style={
                "padding": "8px 12px",
                "marginBottom": "10px",
                "backgroundColor": "#f8f6ff",
                "border": "1px solid #e0d8f0",
                "borderRadius": "4px",
            },
            id="quality-filter-stats-banner",
        ),
        rx.fragment(),
    )


def input_vcf_preview_section() -> rx.Component:
    """Show the selected input VCF file without an inner accordion.

    The grid stays mounted across preview refreshes to avoid blinking.
    A sample switch remounts the parent workspace and bumps
    ``lf_grid_view_token`` so MUI cannot keep the previous filter/sort.
    """
    return rx.el.div(
        rx.el.div(
            fomantic_icon("database", size=16, color="#6435c9"),
            rx.el.strong(
                "Normalized VCF Preview",
                style={"marginLeft": "6px"},
            ),
            rx.cond(
                UploadState.preview_source_label != "",
                rx.el.span(
                    UploadState.preview_source_label,
                    class_name="ui mini violet label",
                    style={"marginLeft": "8px"},
                ),
                rx.fragment(),
            ),
            rx.el.span(
                UploadState.vcf_preview_row_count,
                " rows",
                class_name="ui mini violet label",
                style={"marginLeft": "4px"},
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "flexWrap": "wrap",
                "gap": "4px",
                "padding": "4px 0 10px 0",
                "marginBottom": "10px",
                "borderBottom": "1px solid #e0d8f0",
            },
        ),
        # Quality filter statistics banner
        quality_filter_stats_banner(),
        # Initial-load spinner (only during first VCF scan, NOT scroll loads)
        rx.cond(
            UploadState.vcf_preview_loading,
            rx.el.div(
                rx.el.i("", class_name="spinner loading icon"),
                rx.el.span(" Loading VCF preview...", style={"marginLeft": "8px"}),
                style={"padding": "16px", "color": "#666"},
            ),
            rx.fragment(),
        ),
        # Error overlay
        rx.cond(
            UploadState.has_vcf_preview_error,
            rx.el.div(
                rx.el.div(
                    rx.el.strong("Failed to load VCF preview"),
                    rx.el.div(
                        UploadState.vcf_preview_error,
                        style={"fontSize": "0.85rem", "marginTop": "6px"},
                    ),
                    class_name="content",
                ),
                class_name="ui negative message",
                style={"margin": "0"},
            ),
            rx.fragment(),
        ),
        rx.el.div(
            lazyframe_grid(
                UploadState,
                show_toolbar=True,
                show_description_in_header=True,
                density="compact",
                column_header_height=70,
                height="calc(100vh - 270px)",
                width="100%",
                debug_log=False,
            ),
            key=UploadState.lf_grid_view_token.to(str),
            style={
                "display": rx.cond(UploadState.has_vcf_preview, "block", "none"),
            },
        ),
        # Empty state placeholder (only when nothing loaded and no error)
        rx.cond(
            ~UploadState.has_vcf_preview & ~UploadState.has_vcf_preview_error & ~UploadState.vcf_preview_loading,
            rx.el.div(
                fomantic_icon("inbox", size=30, color="#ccc"),
                rx.el.div(
                    "No rows to preview",
                    style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
                ),
                style={"textAlign": "center", "padding": "20px 16px"},
            ),
            rx.fragment(),
        ),
        style={"padding": "0"},
        id="input-vcf-preview-section",
    )


def run_timeline_card(run: rx.Var[dict]) -> rx.Component:
    """
    Card for a run in the timeline.
    
    Shows status, date, module count. Expands on click to show details.
    The first run (latest) shows additional action buttons and is highlighted.
    """
    run_id = run["run_id"].to(str)
    is_expanded = UploadState.expanded_run_id == run_id
    is_latest = UploadState.latest_run_id == run_id
    dagster_url = UploadState.dagster_web_url + "/runs/" + run_id
    
    return rx.el.div(
        # Main row (always visible)
        rx.el.div(
            # Status badge
            run_status_badge(run["status"].to(str)),
            # Latest badge for first run
            rx.cond(
                is_latest,
                rx.el.span("latest", class_name="ui teal label", style={"marginLeft": "6px"}),
                rx.box(),
            ),
            # Timestamp
            rx.el.span(
                run["started_at"].to(str),
                style={"marginLeft": "12px", "color": "#666", "fontSize": "0.95rem", "flex": "1"},
            ),
            # Module count
            rx.el.span(
                run["modules"].to(list).length(),
                " modules",
                class_name="ui label",
                style={"marginRight": "8px"},
            ),
            # Expand/collapse button
            rx.el.button(
                rx.cond(
                    is_expanded,
                    fomantic_icon("chevron-up", size=16),
                    fomantic_icon("chevron-down", size=16),
                ),
                class_name="ui icon button",
                style={"padding": "8px", "pointerEvents": "none"},  # Let parent handle click
            ),
            style={"display": "flex", "alignItems": "center", "cursor": "pointer"},
            on_click=lambda: UploadState.toggle_run_expansion(run_id),
        ),
        
        # Expanded details (conditionally shown)
        rx.cond(
            is_expanded,
            rx.el.div(
                # Modules list
                rx.el.div(
                    rx.el.span("Modules: ", style={"color": "#666", "fontSize": "0.95rem"}),
                    rx.foreach(
                        run["modules"].to(list),
                        lambda m: rx.el.span(m.to(str), class_name="ui label", style={"marginRight": "4px"}),
                    ),
                    style={"marginBottom": "10px"},
                ),
                # Action buttons (only for latest run)
                rx.cond(
                    is_latest,
                    rx.el.div(
                        rx.el.button(
                            fomantic_icon("refresh-cw", size=14),
                            " Re-run",
                            on_click=UploadState.rerun_with_same_modules,
                            disabled=UploadState.selected_file_is_running,
                            class_name="ui primary button",
                            style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
                        ),
                        rx.el.button(
                            fomantic_icon("sliders-horizontal", size=14),
                            " Modify",
                            on_click=UploadState.modify_and_run,
                            class_name="ui button",
                            style={"display": "inline-flex", "alignItems": "center", "gap": "4px", "marginLeft": "6px"},
                        ),
                        style={"marginBottom": "10px"},
                    ),
                    rx.box(),
                ),
                # Run ID
                rx.el.div(
                    rx.el.span("Run ID: ", style={"color": "#666", "fontSize": "0.95rem"}),
                    rx.el.code(run_id, style={"fontSize": "0.86rem"}),
                    style={"marginBottom": "10px"},
                ),
                # Dagster link
                rx.el.a(
                    fomantic_icon("external-link", size=12),
                    " Open in Dagster",
                    href=dagster_url,
                    target="_blank",
                    class_name="ui button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "4px"},
                ),
                style={"marginTop": "12px", "paddingTop": "12px", "borderTop": "1px solid #eee"},
            ),
            rx.box(),
        ),
        
        class_name=rx.cond(is_latest, "ui teal segment", "ui segment"),
        style={"margin": "0 0 10px 0", "padding": "14px 16px"},
        id=rx.Var.create("timeline-run-") + run_id,
    )


def run_timeline() -> rx.Component:
    """
    Collapsible scrollable list of all runs for the selected file.
    The most recent run is highlighted and has action buttons.
    """
    run_count_badge = rx.el.span(
        UploadState.filtered_runs.length(),
        " runs",
        class_name="ui mini green label",
    )
    return rx.el.div(
        # Foldable header (green accent to match ui green segment)
        _collapsible_header(
            expanded=UploadState.run_history_expanded,
            icon_name="history",
            title="Run History",
            right_badge=run_count_badge,
            on_toggle=UploadState.toggle_run_history,
            accent_color="#21ba45",
        ),
        
        # Expanded content
        rx.cond(
            UploadState.run_history_expanded,
            rx.cond(
                UploadState.has_filtered_runs,
                rx.el.div(
                    rx.foreach(
                        UploadState.filtered_runs,
                        run_timeline_card,
                    ),
                    style={"maxHeight": "300px", "overflowY": "auto"},
                    id="run-timeline-list",
                ),
                rx.el.div(
                    fomantic_icon("inbox", size=32, color="#ccc"),
                    rx.el.div(
                        "No runs yet",
                        style={"color": "#888", "marginTop": "8px", "fontSize": "0.95rem"},
                    ),
                    rx.el.div(
                        "Start an analysis to see run history",
                        style={"color": "#aaa", "marginTop": "4px", "fontSize": "0.85rem"},
                    ),
                    style={"textAlign": "center", "padding": "20px 16px"},
                ),
            ),
            rx.box(),
        ),
        id="run-timeline-section",
        style={"padding": "0", "overflow": "hidden"},
    )


def new_analysis_section() -> rx.Component:
    """
    Section for starting a new analysis (always shown — no accordion header
    because the parent New Analysis tab is the entry point).

    Contains:
    - Manage-module-sources link
    - Module selection grid with logos (no internal scroll, grows naturally)
    - Ensembl annotation toggle
    - Start button
    """
    return rx.el.div(
        rx.el.div(
            fomantic_icon("boxes", size=14, color="#a333c8"),
            rx.el.a(
                " Manage module sources",
                href="/modules",
                style={"fontSize": "0.85rem", "color": "#a333c8", "marginLeft": "4px"},
            ),
            style={"display": "flex", "alignItems": "center", "marginBottom": "14px"},
        ),
        rx.el.div(
            rx.el.button(
                "Select All",
                on_click=UploadState.select_all_modules,
                class_name="ui mini button",
            ),
            rx.el.button(
                "Select None",
                on_click=UploadState.deselect_all_modules,
                class_name="ui mini button",
                style={"marginLeft": "6px"},
            ),
            style={"marginBottom": "16px"},
        ),
        rx.el.div(
            rx.foreach(UploadState.module_metadata_list, module_card),
            style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fill, minmax(320px, 1fr))",
                "gap": "12px",
                "marginBottom": "16px",
            },
            id="module-cards-grid",
        ),
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.input(
                        type="checkbox",
                        checked=UploadState.include_ensembl,
                        read_only=True,
                    ),
                    rx.el.label(
                        rx.el.strong("Include Ensembl Variation Annotations"),
                    ),
                    on_click=UploadState.toggle_ensembl,
                    class_name=rx.cond(
                        UploadState.include_ensembl,
                        "ui checked checkbox",
                        "ui checkbox",
                    ),
                ),
                style={"display": "flex", "alignItems": "center", "gap": "10px"},
            ),
            rx.el.div(
                "Position-based annotation with the Ensembl variation database via DuckDB. "
                "Adds rsid mapping and known variant classifications.",
                style={
                    "fontSize": "0.85rem",
                    "color": "#666",
                    "marginTop": "6px",
                    "lineHeight": "1.3",
                },
            ),
            class_name="ui segment",
            style={
                "padding": "14px",
                "marginBottom": "16px",
                "border": "1px solid #e0e0e0",
                "borderRadius": "6px",
                "backgroundColor": rx.cond(
                    UploadState.include_ensembl,
                    "#f0f7ff",
                    "#fff",
                ),
            },
        ),
        rx.el.button(
            UploadState.analysis_button_text,
            rx.el.i(
                "",
                class_name=rx.cond(
                    UploadState.selected_file_is_running,
                    "spinner loading icon",
                    rx.cond(
                        UploadState.last_run_success,
                        "check circle icon",
                        "play icon",
                    ),
                ),
            ),
            on_click=UploadState.start_annotation_run,
            disabled=~UploadState.can_run_annotation,
            class_name=UploadState.analysis_button_color,
            style={"maxWidth": "400px"},
        ),
        style={"padding": "0"},
        id="new-analysis-section",
    )


def no_file_selected_message() -> rx.Component:
    """
    Welcome/onboarding message when no sample is selected.
    Explains the workflow instead of duplicating the left panel.
    """
    def philosophy_item(icon: str, color: str, title: str, desc: str) -> rx.Component:
        return rx.el.div(
            fomantic_icon(icon, size=20, color=color, style={"marginRight": "12px"}),
            rx.el.div(
                rx.el.strong(title),
                rx.el.div(desc, style={"fontSize": "0.9rem", "color": "#666"}),
                style={"flex": "1"},
            ),
            style={
                "display": "flex",
                "alignItems": "start",
                "flex": "1 1 360px",
                "maxWidth": "420px",
                "textAlign": "left",
            },
        )

    return rx.el.div(
        rx.el.div(
            fomantic_icon("dna", size=36, color="#00b5ad", style={"marginRight": "10px"}),
            rx.el.h1(
                "Just-DNA-Lite",
                class_name="ui huge header",
                style={"margin": "0"},
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "marginBottom": "8px",
            },
        ),
        rx.el.p(
            "Explore your genome on your own computer. Nothing is sent to a server.",
            style={
                "fontSize": "1.25rem",
                "color": "#444",
                "margin": "0 0 12px 0",
                "lineHeight": "1.35",
            },
        ),
        rx.cond(
            UploadState.show_welcome_disclaimer,
            rx.el.div(
                rx.el.div(
                    rx.el.i(
                        "",
                        class_name="close icon",
                        on_click=UploadState.close_welcome_disclaimer,
                        role="button",
                        aria_label="Close medical disclaimer",
                        tab_index=0,
                        style={"cursor": "pointer"},
                    ),
                    fomantic_icon(
                        "exclamation-triangle",
                        size=16,
                        color="#db2828",
                        style={"marginRight": "8px"},
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.strong("Medical disclaimer"),
                            " (research use only)",
                            class_name="header",
                            style={"color": "#db2828", "fontSize": "0.9rem"},
                        ),
                        rx.el.p(
                            "This tool is for research, educational, and self-exploration "
                            "purposes only. It is ",
                            rx.el.strong("not a medical device"),
                            " and provides no medical advice. "
                            "The genetic modules and polygenic risk scores here are ",
                            rx.el.strong("not clinically validated"),
                            ". Do not use this tool for diagnostic or medical decisions. "
                            "Interesting findings should be re-tested with a clinically "
                            "validated method in a certified lab.",
                            style={"margin": "0", "lineHeight": "1.4", "fontSize": "0.8rem"},
                        ),
                        class_name="content",
                    ),
                    class_name="ui icon red message",
                    style={
                        "maxWidth": "840px",
                        "width": "100%",
                        "textAlign": "left",
                        "margin": "0",
                        "padding": "10px 14px",
                    },
                ),
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "width": "100%",
                    "marginBottom": "16px",
                },
            ),
            rx.fragment(),
        ),
        rx.el.p(
            "You need a VCF: the file your sequencing provider already produced. "
            "It is a table of places your DNA differs from a reference genome. "
            "The diagram below shows how that file is made, and what you do with it here.",
            style={
                "fontSize": "1.12rem",
                "color": "#555",
                "maxWidth": "820px",
                "margin": "0 auto 16px auto",
                "lineHeight": "1.45",
            },
        ),

        # Sequencing journey schematic + zoomed-in "how to use" panel
        sequencing_journey_diagram(),

        rx.el.div(
            rx.el.div(
                rx.el.strong("Reference genome. "),
                "The standard map of human DNA that labs write positions against. "
                "Most current files use GRCh38; choose that unless your provider used GRCh37/hg19.",
            ),
            rx.el.div(
                rx.el.strong("This tool annotates a VCF. "),
                "It does not sequence DNA or call variants. The file is only as complete as the lab that made it.",
            ),
            rx.el.div(
                rx.el.strong("23andMe and Ancestry are not sequencing. "),
                "Those services read a few hundred thousand pre-selected spots on a chip, "
                "not the whole genome. Support for those files is planned; for now the tool "
                "is built for whole-genome and whole-exome VCFs.",
            ),
            style={
                "maxWidth": "760px",
                "margin": "0 auto 28px auto",
                "textAlign": "left",
                "fontSize": "0.82rem",
                "color": "#777",
                "lineHeight": "1.45",
                "display": "flex",
                "flexDirection": "column",
                "gap": "4px",
            },
        ),

        # Core Philosophy (below the journey, 2x2 grid)
        rx.el.div(
            rx.el.h3(
                "Core Philosophy",
                class_name="ui large header",
                style={"textAlign": "center", "marginBottom": "24px"},
            ),
            rx.el.div(
                philosophy_item(
                    "lock", "#2185d0",
                    "Your data, your call",
                    "Runs entirely on your machine. Nothing leaves your computer.",
                ),
                philosophy_item(
                    "eye", "#fbbd08",
                    "Unfiltered access",
                    "We show the full research view, not a pre-filtered clinical summary.",
                ),
                philosophy_item(
                    "rocket", "#21ba45",
                    "Speed & Iteration",
                    "We optimize for rapid exploration and fast module creation, not clinical-style validation cycles.",
                ),
                philosophy_item(
                    "warning sign", "#767676",
                    "Scientific realism",
                    "Modules, PRS, and especially AI-generated content can be wrong, incomplete, or clinically irrelevant.",
                ),
                style={
                    "display": "flex",
                    "flexWrap": "wrap",
                    "gap": "18px 40px",
                    "justifyContent": "center",
                },
            ),
            style={"maxWidth": "900px", "margin": "0 auto"},
        ),

        style={"textAlign": "center", "padding": "4px 24px 32px 24px"},
        id="no-file-selected-message",
    )





# CSS injected once for drag-and-drop tab behaviour
TAB_DRAG_CSS = """
#right-panel-tab-menu .item {
    cursor: grab;
    transition: opacity 0.15s ease, box-shadow 0.15s ease;
    user-select: none;
}
#right-panel-tab-menu .item:active {
    cursor: grabbing;
}
#right-panel-tab-menu .item.tab-drag-over {
    box-shadow: -3px 0 0 0 #6435c9 inset;
    background: rgba(100, 53, 201, 0.06);
}
#right-panel-tab-menu .item.tab-dragging {
    opacity: 0.4;
}
"""

TAB_DRAG_JS = """
(function () {
    if (window.__tabDndInit) return;
    window.__tabDndInit = true;
    var MENU = '#right-panel-tab-menu';
    var SEL = MENU + ' .item';
    var menuEl = function () { return document.querySelector(MENU); };
    var clearMarks = function () {
        document.querySelectorAll(
            MENU + ' .tab-dragging, ' + MENU + ' .tab-drag-over'
        ).forEach(function (el) { el.classList.remove('tab-dragging', 'tab-drag-over'); });
    };
    document.addEventListener('dragstart', function (e) {
        var item = e.target.closest ? e.target.closest(SEL) : null;
        if (!item) return;
        // Firefox requires dataTransfer.setData() for the drag to begin at all.
        try { e.dataTransfer.setData('text/plain', item.dataset.tabId || ''); } catch (_) {}
        if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
        // Stash the source id on the menu element. We DON'T read it back from
        // dataTransfer on drop: Firefox doesn't reliably expose dataTransfer
        // data through React's synthetic onDrop, so drop_tab_spec reads this
        // attribute instead (setData above is only to satisfy FF's drag-start).
        var menu = menuEl();
        if (menu) menu.dataset.dragSrc = item.dataset.tabId || '';
        item.classList.add('tab-dragging');
    });
    document.addEventListener('dragover', function (e) {
        var item = e.target.closest ? e.target.closest(SEL) : null;
        if (!item) return;
        // Required to make the element a valid drop target.
        e.preventDefault();
        document.querySelectorAll('#right-panel-tab-menu .tab-drag-over')
            .forEach(function (el) { if (el !== item) el.classList.remove('tab-drag-over'); });
        item.classList.add('tab-drag-over');
    });
    document.addEventListener('dragleave', function (e) {
        var item = e.target.closest ? e.target.closest(SEL) : null;
        if (item) item.classList.remove('tab-drag-over');
    });
    document.addEventListener('drop', function (e) {
        var item = e.target.closest ? e.target.closest(SEL) : null;
        if (!item) return;
        // Stop the browser's default drop handling; the React on_drop handler
        // on the draggable_div element still fires and calls move_tab, reading
        // the source id from menu.dataset.dragSrc (set in dragstart).
        e.preventDefault();
        clearMarks();
    });
    document.addEventListener('dragend', function () {
        clearMarks();
        // Clear the stashed source only after the whole gesture is over, so it
        // can't race React's onDrop read regardless of listener ordering.
        var menu = menuEl();
        if (menu) delete menu.dataset.dragSrc;
    });
})();
"""


def _tab_item(tab_id: rx.Var[str]) -> rx.Component:
    """Render one draggable tab <div> matched from tab_id.

    All five tab variants are inlined here via rx.match so Reflex can
    evaluate the conditional at render time against the reactive var.
    """
    drag_style = {
        **RIGHT_PANEL_TAB_STYLE,
        "WebkitUserDrag": "element",
    }
    return rx.match(
        tab_id,
        (
            "input",
            draggable_div(
                fomantic_icon(
                    "database",
                    size=16,
                    color=rx.cond(UploadState.right_panel_active_tab == "input", "#6435c9", "#888"),
                ),
                " Input",
                rx.cond(
                    UploadState.vcf_preview_row_count > 0,
                    rx.el.span(
                        UploadState.vcf_preview_row_count,
                        " rows",
                        class_name="ui mini circular violet label",
                        style=RIGHT_PANEL_TAB_BADGE_STYLE,
                    ),
                    rx.fragment(),
                ),
                class_name=rx.cond(UploadState.right_panel_active_tab == "input", "active item", "item"),
                on_click=UploadState.switch_to_input_tab,
                on_drag_start=UploadState.drag_tab_start("input"),
                on_drag_over=rx.prevent_default,
                on_drop=UploadState.drop_tab_onto("input"),
                draggable=True,
                style=drag_style,
                data_tab_id="input",
            ),
        ),
        (
            "prs",
            draggable_div(
                fomantic_icon(
                    "chart bar",
                    size=16,
                    color=rx.cond(UploadState.right_panel_active_tab == "prs", "#6435c9", "#888"),
                ),
                " Polygenic Risk Scores",
                rx.cond(
                    PRSState.prs_results.length() > 0,
                    rx.el.span(
                        PRSState.prs_results.length(),
                        class_name="ui mini circular orange label",
                        style=RIGHT_PANEL_TAB_BADGE_STYLE,
                    ),
                    rx.fragment(),
                ),
                class_name=rx.cond(UploadState.right_panel_active_tab == "prs", "active item", "item"),
                on_click=UploadState.switch_to_prs_tab,
                on_drag_start=UploadState.drag_tab_start("prs"),
                on_drag_over=rx.prevent_default,
                on_drop=UploadState.drop_tab_onto("prs"),
                draggable=True,
                style=drag_style,
                data_tab_id="prs",
            ),
        ),
        (
            "annotated_files",
            draggable_div(
                fomantic_icon(
                    "file code outline",
                    size=16,
                    color=rx.cond(UploadState.right_panel_active_tab == "annotated_files", "#6435c9", "#888"),
                ),
                " Annotated Files",
                rx.el.span(
                    UploadState.output_file_count,
                    class_name="ui mini circular teal label",
                    style=RIGHT_PANEL_TAB_BADGE_STYLE,
                ),
                class_name=rx.cond(UploadState.right_panel_active_tab == "annotated_files", "active item", "item"),
                on_click=UploadState.switch_to_annotated_files_tab,
                on_drag_start=UploadState.drag_tab_start("annotated_files"),
                on_drag_over=rx.prevent_default,
                on_drop=UploadState.drop_tab_onto("annotated_files"),
                draggable=True,
                style=drag_style,
                data_tab_id="annotated_files",
            ),
        ),
        (
            "reports",
            draggable_div(
                fomantic_icon(
                    "file alternate outline",
                    size=16,
                    color=rx.cond(UploadState.right_panel_active_tab == "reports", "#6435c9", "#888"),
                ),
                " Reports",
                rx.cond(
                    UploadState.has_report_files,
                    rx.el.span(
                        UploadState.report_file_count,
                        class_name="ui mini circular pink label",
                        style=RIGHT_PANEL_TAB_BADGE_STYLE,
                    ),
                    rx.fragment(),
                ),
                class_name=rx.cond(UploadState.right_panel_active_tab == "reports", "active item", "item"),
                on_click=UploadState.switch_to_reports_tab,
                on_drag_start=UploadState.drag_tab_start("reports"),
                on_drag_over=rx.prevent_default,
                on_drop=UploadState.drop_tab_onto("reports"),
                draggable=True,
                style=drag_style,
                data_tab_id="reports",
            ),
        ),
        (
            "analysis",
            draggable_div(
                fomantic_icon(
                    "stethoscope",
                    size=16,
                    color=rx.cond(UploadState.right_panel_active_tab == "analysis", "#6435c9", "#888"),
                ),
                " Analysis Tools",
                rx.cond(
                    UploadState.selected_modules.length() > 0,
                    rx.el.span(
                        UploadState.selected_modules.length(),
                        " selected",
                        class_name="ui mini circular blue label",
                        style=RIGHT_PANEL_TAB_BADGE_STYLE,
                    ),
                    rx.fragment(),
                ),
                class_name=rx.cond(UploadState.right_panel_active_tab == "analysis", "active item", "item"),
                on_click=UploadState.switch_to_analysis_tab,
                on_drag_start=UploadState.drag_tab_start("analysis"),
                on_drag_over=rx.prevent_default,
                on_drop=UploadState.drop_tab_onto("analysis"),
                draggable=True,
                style=drag_style,
                data_tab_id="analysis",
            ),
        ),
        rx.fragment(),  # default / unknown tab id
    )


def _right_panel_tab_menu() -> rx.Component:
    """Top-level horizontal tab menu for the right panel.

    Tabs are flat and drag-reorderable: order is persisted in
    UploadState.tab_order. Drag a tab left/right to rearrange.
    """
    return rx.el.div(
        rx.el.style(TAB_DRAG_CSS),
        rx.script(TAB_DRAG_JS),
        rx.foreach(UploadState.tab_order, _tab_item),
        class_name="ui top attached tabular menu",
        style={"marginBottom": "0"},
        id="right-panel-tab-menu",
    )


def _tab_info_message(
    visible: rx.Var[bool],
    close_event: rx.event.EventHandler,
    icon_name: str,
    title: str,
    body: str,
) -> rx.Component:
    """Closable Fomantic info message for right-panel tabs."""
    return rx.cond(
        visible,
        rx.el.div(
            rx.el.i(
                "",
                class_name="close icon",
                on_click=close_event,
                role="button",
                aria_label=f"Close {title} message",
                tab_index=0,
                style={"cursor": "pointer"},
            ),
            fomantic_icon(icon_name, size=20, color="#2185d0"),
            rx.el.div(
                rx.el.div(title, class_name="header"),
                rx.el.p(body),
                class_name="content",
            ),
            class_name="ui icon info message",
            style={"margin": "0 0 16px 0"},
        ),
        rx.fragment(),
    )


def _input_tab_content() -> rx.Component:
    """Content for the Input tab: the normalized VCF preview."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_input_tab_info,
            UploadState.close_input_tab_info,
            "database",
            "Your uploaded DNA file, prepared for analysis",
            "This preview shows the variants after cleanup: low-quality rows are filtered, chromosome names are standardized, and the table is ready to match against annotation modules.",
        ),
        input_vcf_preview_section(),
        id="segment-vcf-preview",
    )


def _prs_workbench_tab_trigger(
    label: str,
    icon_name: str,
    value: str,
    description: str,
) -> rx.Component:
    """Radix tab trigger matching the standalone prs-ui By Trait / By PRS tabs."""
    return rx.tabs.trigger(
        rx.hstack(
            rx.icon(icon_name, size=18),
            rx.text(label, size="3", weight="bold"),
            rx.tooltip(
                rx.icon("info", size=14, color="gray"),
                content=description,
            ),
            spacing="2",
            align="center",
        ),
        value=value,
        padding="10px 20px",
        cursor="pointer",
    )


def _prs_ancestry_chip() -> rx.Component:
    """Detected super-population badge for the current-sample row."""
    return rx.cond(
        PRSState.ancestry_detection_status == "detecting",
        rx.hstack(
            rx.spinner(size="1"),
            rx.text("Detecting ancestry…", size="1", color="gray"),
            align="center",
            spacing="1",
        ),
        rx.cond(
            PRSState.ancestry_chip_label != "",
            rx.badge(
                rx.hstack(
                    rx.icon("shield-check", size=12),
                    rx.text(PRSState.ancestry_chip_label, size="1", weight="medium"),
                    rx.cond(
                        PRSState.ancestry_chip_confidence != "",
                        rx.text(PRSState.ancestry_chip_confidence, size="1", color="gray"),
                    ),
                    align="center",
                    spacing="1",
                ),
                color_scheme="green",
                variant="soft",
                size="1",
                title=(
                    "Genetic ancestry autodetected from this genome against the "
                    "1000 Genomes reference panel, with the classifier's "
                    "confidence. The trait dashboard Population dropdown is the "
                    "override for card numbers; chart curves stay per-population."
                ),
            ),
            rx.cond(
                PRSState.ancestry_detection_status == "unknown",
                rx.badge(
                    "Ancestry unknown",
                    color_scheme="gray",
                    variant="soft",
                    size="1",
                ),
                rx.fragment(),
            ),
        ),
    )


def _prs_fine_population_chip() -> rx.Component:
    """Closest 1000G cohort, linked to IGSR when the code is known."""
    return rx.cond(
        PRSState.detected_fine_label != "",
        rx.cond(
            PRSState.detected_fine_url != "",
            rx.link(
                rx.hstack(
                    rx.text(PRSState.detected_fine_label, size="1"),
                    rx.cond(
                        PRSState.detected_fine_confidence_label != "",
                        rx.text(PRSState.detected_fine_confidence_label, size="1", color="gray"),
                    ),
                    rx.icon("external-link", size=10),
                    align="center",
                    spacing="1",
                ),
                href=PRSState.detected_fine_url,
                is_external=True,
                title=PRSState.detected_fine_title,
                size="1",
                color_scheme="green",
                underline="hover",
            ),
            rx.hstack(
                rx.text(PRSState.detected_fine_label, size="1", color="gray"),
                rx.cond(
                    PRSState.detected_fine_confidence_label != "",
                    rx.text(PRSState.detected_fine_confidence_label, size="1", color="gray"),
                ),
                align="center",
                spacing="1",
            ),
        ),
        rx.fragment(),
    )


def _prs_current_sample_row() -> rx.Component:
    """One sample row for the genome already selected in the left panel."""
    return rx.hstack(
        rx.box(
            width="12px",
            height="12px",
            border_radius="50%",
            background=sample_color(0),
            flex_shrink="0",
        ),
        rx.text(UploadState.selected_file, size="2", weight="bold"),
        rx.badge("GRCh38", color_scheme="blue", variant="soft", size="1"),
        rx.select.root(
            rx.select.trigger(size="1"),
            rx.select.content(
                rx.select.item("WGS", value="wgs"),
                rx.select.item("Array / targeted", value="array"),
            ),
            value=PRSState.sample_type,
            on_change=PRSState.set_sample_type,
            size="1",
        ),
        rx.cond(
            PRSState.sample_type_label != "",
            rx.text(PRSState.sample_type_label, size="1", color="gray"),
            rx.fragment(),
        ),
        rx.spacer(),
        _prs_ancestry_chip(),
        _prs_fine_population_chip(),
        rx.cond(
            PRSState.sample_variant_label != "",
            rx.text(PRSState.sample_variant_label, size="1", color="gray"),
            rx.fragment(),
        ),
        align="center",
        spacing="2",
        width="100%",
        padding="6px 10px",
        border="1px solid var(--gray-4)",
        border_radius="8px",
        background="var(--gray-1)",
    )


def _prs_current_sample_source() -> rx.Component:
    """Host-app genotype source: the selected left-panel sample, not a dropzone."""
    return rx.vstack(
        rx.cond(
            UploadState.has_selected_file,
            rx.vstack(
                rx.text("Sample", size="1", weight="bold", color="gray"),
                _prs_current_sample_row(),
                rx.cond(
                    PRSState.detected_fine_label != "",
                    rx.text(
                        "Closest 1000G cohort is the nearest of the 1000 Genomes "
                        "reference cohorts (26 worldwide) — a reference point, not a "
                        "nationality. Many populations have no dedicated cohort in the "
                        "panel (e.g. Slavic / Eastern European genomes usually land on "
                        "the Northern/Western European cohort as their closest match).",
                        size="1",
                        color="gray",
                    ),
                    rx.fragment(),
                ),
                rx.checkbox(
                    "Force recompute (ignore saved results)",
                    checked=PRSState.prs_force_recompute,
                    on_change=PRSState.set_prs_force_recompute,
                    size="1",
                    color_scheme="gray",
                ),
                spacing="1",
                width="100%",
            ),
            rx.callout(
                "Select a sample in the left panel to compute PRS. "
                "The catalog below stays browsable; selection unlocks once "
                "the genotype table is ready.",
                icon="arrow-left",
                color_scheme="blue",
                size="1",
                width="100%",
            ),
        ),
        spacing="2",
        width="100%",
    )


def _prs_tab_content() -> rx.Component:
    """PRS tab: prs-ui workbench layout driven by the selected left-panel genome."""
    normalizing = UploadState.vcf_preview_loading
    trait_panel = prs_workbench_mode_panel(
        PRSState,
        lambda: trait_selector(PRSTraitState, normalizing=normalizing),
        "grouped",
        "Compute PRS for Selected Traits",
        normalizing=normalizing,
    )
    prs_panel = prs_workbench_mode_panel(
        PRSState,
        lambda: prs_scores_selector(PRSState, normalizing=normalizing),
        "individual",
        "Compute PRS",
        normalizing=normalizing,
    )
    return rx.el.div(
        rx.el.style(PRS_ALIGNMENT_CSS),
        data_grid_scroll_css(),
        _tab_info_message(
            UploadState.show_prs_tab_info,
            UploadState.close_prs_tab_info,
            "chart-bar",
            "Polygenic Risk Scores from the PGS Catalog",
            "A PRS combines many DNA variants into one score using weights from a published model. We import the full PGS Catalog here, so you can search available scores, pick relevant models, and compute them for the selected genome.",
        ),
        rx.theme(
            rx.vstack(
                _prs_current_sample_source(),
                rx.tabs.root(
                    rx.tabs.list(
                        _prs_workbench_tab_trigger(
                            "By Trait",
                            "layers",
                            "trait",
                            "Start from a disease or phenotype, then compute related "
                            "PGS models together.",
                        ),
                        _prs_workbench_tab_trigger(
                            "By PRS",
                            "list-checks",
                            "prs",
                            "Choose specific PGS Catalog scoring models and compute "
                            "them for the selected genome.",
                        ),
                        size="2",
                    ),
                    rx.tabs.content(trait_panel, value="trait", width="100%"),
                    rx.tabs.content(prs_panel, value="prs", width="100%"),
                    value=PRSState.compute_mode,
                    on_change=PRSState.set_compute_mode,
                    width="100%",
                ),
                width="100%",
                spacing="4",
            ),
            has_background=False,
        ),
        id="segment-prs",
    )


def _annotated_files_tab_content() -> rx.Component:
    """Content for the Annotated Files tab: output data cards and inline preview."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_annotated_files_tab_info,
            UploadState.close_annotated_files_tab_info,
            "folder-output",
            "Annotated files created by your analysis",
            "Each file shows which module produced it. You can open any result in the data grid to explore the annotated variants with search, sorting, and filtering options.",
        ),
        _data_files_content(),
        _output_preview_grid(),
        id="segment-annotated-files",
    )


def _reports_tab_content() -> rx.Component:
    """Content for the Reports tab: generated HTML reports."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_reports_tab_info,
            UploadState.close_reports_tab_info,
            "file-text",
            "Readable summaries",
            "Reports turn the output tables into a browser-friendly view so you can explore the main matches without opening parquet files.",
        ),
        _reports_content(),
        id="segment-reports",
    )


def _latest_run_status_card() -> rx.Component:
    """Compact card under the New Analysis form showing the most recently started run.

    Gives the user immediate feedback after clicking Run. Highlights with a yellow border + spinner
    while the run is still RUNNING/QUEUED/STARTING.
    """
    last = UploadState.last_run_for_file
    last_id = UploadState.latest_run_id
    is_running = UploadState.selected_file_is_running
    dagster_url = UploadState.dagster_web_url + "/runs/" + last_id

    return rx.cond(
        UploadState.has_last_run,
        rx.el.div(
            rx.el.div(
                rx.cond(
                    is_running,
                    fomantic_icon("loader-circle", size=16, color="#fbbd08"),
                    fomantic_icon("history", size=16, color="#2185d0"),
                ),
                rx.el.span(
                    rx.cond(is_running, "Run in progress", "Latest run"),
                    style={"fontWeight": "700", "marginLeft": "8px", "fontSize": "1.05rem"},
                ),
                run_status_badge(last["status"].to(str)),
                rx.el.span(
                    last["started_at"].to(str),
                    style={"marginLeft": "10px", "color": "#666", "fontSize": "0.95rem", "flex": "1"},
                ),
                rx.el.span(
                    last["modules"].to(list).length(),
                    " modules",
                    class_name="ui blue label",
                    style={"marginLeft": "8px"},
                ),
                style={"display": "flex", "alignItems": "center", "gap": "6px", "flexWrap": "wrap"},
            ),
            rx.el.div(
                rx.el.button(
                    fomantic_icon("history", size=12),
                    " View Annotated Files",
                    on_click=lambda: UploadState.view_run_in_results(last_id),
                    class_name="ui green button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "6px"},
                ),
                rx.el.a(
                    fomantic_icon("external-link", size=12),
                    " Dagster",
                    href=dagster_url,
                    target="_blank",
                    class_name="ui basic button",
                    style={"display": "inline-flex", "alignItems": "center", "gap": "6px", "marginLeft": "8px"},
                ),
                style={"marginTop": "10px"},
            ),
            class_name=rx.cond(
                is_running,
                "ui yellow segment",
                "ui segment",
            ),
            style={"marginTop": "16px", "padding": "14px 16px"},
            id="segment-latest-run-status",
        ),
        rx.fragment(),
    )


def _analysis_tab_content() -> rx.Component:
    """Content for the Analysis tab: module selection, start button, and latest-run status."""
    return rx.el.div(
        _tab_info_message(
            UploadState.show_analysis_tab_info,
            UploadState.close_analysis_tab_info,
            "plus-circle",
            "Choose what to compare",
            "Pick one or more annotation modules, then run the pipeline. The tool joins your cleaned variant table with those module databases and saves the results.",
        ),
        new_analysis_section(),
        _latest_run_status_card(),
        id="segment-new-analysis",
    )


def right_panel_run_view() -> rx.Component:
    """
    Run-centric right panel organized as flat horizontal tabs:
    Input | PRS | Annotated Files | Reports | New Analysis.
    """
    return rx.el.div(
        # Header – DNA gradient banner (green -> teal -> blue from logo)
        rx.el.div(
            rx.cond(
                UploadState.has_selected_file,
                rx.el.span(
                    fomantic_icon("dna", size=22, color="#fff"),
                    rx.el.span(
                        " Results for ",
                        rx.el.strong(UploadState.selected_file, style={"fontWeight": "600"}),
                        style={"fontSize": "1.1rem", "marginLeft": "8px", "color": "#fff"},
                    ),
                    style={"display": "inline-flex", "alignItems": "center"},
                ),
                # No file selected: animated arrow pointing at the left panel,
                # right where the user has to act (better than a CTA buried at
                # the bottom of the welcome page).
                rx.el.span(
                    rx.el.span(
                        fomantic_icon("arrow left", size=22, color="#fff"),
                        class_name="jd-left-nudge",
                    ),
                    rx.el.span(
                        " Start in the left panel \u2014 add or select a sample to begin",
                        style={"fontSize": "1.1rem", "marginLeft": "10px", "color": "#fff", "fontWeight": "600"},
                    ),
                    style={"display": "inline-flex", "alignItems": "center"},
                ),
            ),
            style={
                "display": "flex",
                "alignItems": "center",
                "padding": "14px 16px",
                "marginBottom": "16px",
                "background": "linear-gradient(135deg, #21ba45, #00b5ad, #2185d0)",
                "color": "#fff",
                "borderRadius": "6px",
            },
            id="right-column-header",
        ),
        # One React tree per sample.  Partitioned work (VCF, PRS, reports)
        # must not inherit MUI/Vega instance state from the previous genome.
        rx.cond(
            UploadState.has_selected_file,
            rx.el.div(
                _right_panel_tab_menu(),
                rx.el.div(
                    rx.match(
                        UploadState.right_panel_active_tab,
                        ("input", _input_tab_content()),
                        ("prs", _prs_tab_content()),
                        ("annotated_files", _annotated_files_tab_content()),
                        ("reports", _reports_tab_content()),
                        ("analysis", _analysis_tab_content()),
                        _input_tab_content(),
                    ),
                    class_name="ui bottom attached segment",
                    style={"padding": "16px"},
                    id="right-panel-tab-content",
                ),
                key=UploadState.selected_file,
                id="right-panel-sample-workspace",
            ),
            no_file_selected_message(),
        ),
        id="right-panel-run-view",
        style={"padding": "0"},
    )




# ============================================================================
# POLLING INTERVAL FOR REAL-TIME UPDATES
# ============================================================================

def polling_interval() -> rx.Component:
    """Hidden interval component for polling run status."""
    return rx.cond(
        UploadState.selected_file_is_running,
        rx.moment(
            interval=3000,
            on_change=UploadState.poll_run_status,
        ),
        rx.box(),
    )


# ============================================================================
# MAIN PAGE
# ============================================================================

@rx.page(
    route="/annotate",
    title="Annotate | Just DNA Lite",
    on_load=UploadState.on_load,
    meta=page_meta("/annotate"),
    image=page_image_url(),
)
def annotate_page() -> rx.Component:
    """Annotation page with two-panel run-centric layout."""
    return template(
        # Two-column layout with run-centric right panel
        two_column_layout(
            left=file_column_content(),
            right=right_panel_run_view(),
        ),
        
        # Polling component (hidden)
        polling_interval(),
    )
