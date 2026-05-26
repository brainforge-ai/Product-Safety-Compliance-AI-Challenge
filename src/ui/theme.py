"""
UI Theme configuration - dark theme inspired by shadcn/ui.

Separates presentation from business logic.
"""
import gradio as gr

# Theme configuration
theme = gr.themes.Base(
    primary_hue="zinc",
    secondary_hue="zinc",
    neutral_hue="zinc",
    font=gr.themes.GoogleFont("Inter"),
    font_mono=gr.themes.GoogleFont("JetBrains Mono"),
).set(
    body_background_fill="#0a0a0a",
    body_background_fill_dark="#0a0a0a",
    block_background_fill="#141414",
    block_background_fill_dark="#141414",
    block_border_color="#262626",
    block_border_color_dark="#262626",
    block_border_width="1px",
    block_label_text_color="#a3a3a3",
    block_label_text_color_dark="#a3a3a3",
    block_title_text_color="#fafafa",
    block_title_text_color_dark="#fafafa",
    input_background_fill="#1a1a1a",
    input_background_fill_dark="#1a1a1a",
    input_border_color="#262626",
    input_border_color_dark="#262626",
    button_primary_background_fill="#fafafa",
    button_primary_background_fill_dark="#fafafa",
    button_primary_background_fill_hover="#e5e5e5",
    button_primary_background_fill_hover_dark="#e5e5e5",
    button_primary_text_color="#0a0a0a",
    button_primary_text_color_dark="#0a0a0a",
    button_secondary_background_fill="#262626",
    button_secondary_background_fill_dark="#262626",
    button_secondary_text_color="#fafafa",
    button_secondary_text_color_dark="#fafafa",
    border_color_primary="#262626",
    border_color_primary_dark="#262626",
    background_fill_primary="#0a0a0a",
    background_fill_primary_dark="#0a0a0a",
    background_fill_secondary="#141414",
    background_fill_secondary_dark="#141414",
)

css = """
.gradio-container {
    min-width: 700px !important;
    max-width: 900px !important;
    width: 900px !important;
    margin: auto !important;
}
.contain {
    min-width: 700px !important;
}
footer { display: none !important; }

/* Title styles */
.title {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    color: #fafafa !important;
    margin-bottom: 0.25rem !important;
}
.subtitle {
    font-size: 0.875rem !important;
    color: #737373 !important;
    margin-bottom: 1.5rem !important;
}

/* Output text */
.output-text textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    line-height: 1.7 !important;
    color: #e5e5e5 !important;
}

/* Tab styling - active tab is white */
button.tab-nav {
    font-weight: 500 !important;
    color: #525252 !important;
    background: transparent !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
}
button.tab-nav.selected {
    color: #fafafa !important;
    border-bottom: 2px solid #fafafa !important;
}
.tabs > div:first-child {
    border-bottom: 1px solid #262626 !important;
    margin-bottom: 1.5rem !important;
}
/* Gradio 5 tab selectors */
.tabitem {
    background: transparent !important;
}
div.tab-nav > button {
    color: #525252 !important;
    background: transparent !important;
}
div.tab-nav > button.selected {
    color: #fafafa !important;
    border-bottom: 2px solid #fafafa !important;
}

/* File upload */
.file-upload {
    border: 1px dashed #404040 !important;
    border-radius: 8px !important;
    min-height: 80px !important;
}

/* Tabs container */
.tabs {
    min-width: 100% !important;
}

/* Progress bar */
.progress-bar {
    background: #22c55e !important;
}
"""
