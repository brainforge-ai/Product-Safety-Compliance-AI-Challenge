"""
Product Safety Compliance - Web UI

Gradio dashboard for evaluating product ingredients.
"""
from pathlib import Path
from typing import Optional

import gradio as gr

from dotenv import load_dotenv
load_dotenv()

from src.core.bootstrap import create_pipeline, evaluate_file as core_evaluate_file
from src.core.matching import MatchPipeline
from src.ui.theme import theme, css

# Global default pipeline (initialized on startup)
default_pipeline: Optional[MatchPipeline] = None


async def init_default_pipeline():
    """Initialize the default matching pipeline."""
    global default_pipeline
    if default_pipeline is None:
        default_pipeline = await create_pipeline()
    return default_pipeline


async def get_pipeline(forbidden_file=None) -> MatchPipeline:
    """Get pipeline - custom if forbidden file provided, else default."""
    if forbidden_file is not None:
        # Create custom pipeline with uploaded forbidden list
        forbidden_path = Path(forbidden_file.name)
        return await create_pipeline(forbidden_path=forbidden_path)
    return await init_default_pipeline()


async def evaluate_single_async(file_obj, forbidden_file=None):
    """Async evaluation of a single file."""
    if file_obj is None:
        return "Upload a file to evaluate"

    filepath = file_obj.name if hasattr(file_obj, 'name') else str(file_obj)
    path = Path(filepath)

    try:
        pipeline = await get_pipeline(forbidden_file)
        result = await core_evaluate_file(pipeline, path)

        lines = []

        if result.reason:
            lines.append("❌ REJECTED")
            lines.append("")
            lines.append(f"File: {path.name}")
            lines.append(f"Product: {result.product_name}")
            lines.append("")
            lines.append("Forbidden ingredients found:")
            for r in result.reason:
                lines.append(f"  • {r}")
        else:
            lines.append("✅ ACCEPTED")
            lines.append("")
            lines.append(f"File: {path.name}")
            lines.append(f"Product: {result.product_name}")
            lines.append("")
            lines.append("No forbidden ingredients detected")

        lines.append("")
        lines.append(f"Ingredients analyzed: {len(result.ingredients_detected)}")

        if forbidden_file:
            lines.append(f"Using custom forbidden list: {Path(forbidden_file.name).name}")

        return "\n".join(lines)

    except Exception as e:
        return f"⚠️ ERROR\n\nFile: {path.name}\n\n{str(e)}"


def evaluate_single(file_obj, forbidden_file, progress=gr.Progress(track_tqdm=True)):
    """Single file evaluation wrapper."""
    import asyncio
    progress(0.1, desc="Processing...")
    result = asyncio.run(evaluate_single_async(file_obj, forbidden_file))
    progress(1.0, desc="Done")
    return result


def evaluate_batch(file_list, forbidden_file, progress=gr.Progress(track_tqdm=True)):
    """Batch evaluation wrapper with progress."""
    import asyncio

    if not file_list:
        yield "Upload files to evaluate"
        return

    async def run_batch():
        pipeline = await get_pipeline(forbidden_file)

        total = len(file_list)
        results = []
        accepted = 0
        rejected = 0

        for idx, file_obj in enumerate(file_list):
            filepath = file_obj.name if hasattr(file_obj, 'name') else str(file_obj)
            path = Path(filepath)

            try:
                result = await core_evaluate_file(pipeline, path)

                if result.reason:
                    rejected += 1
                    reason = ", ".join(result.reason)
                    results.append(f"❌  {path.name}")
                    results.append(f"    └─ {reason}")
                else:
                    accepted += 1
                    results.append(f"✅  {path.name}")

            except Exception as e:
                results.append(f"⚠️  {path.name}")
                results.append(f"    └─ Error: {e}")

        return total, accepted, rejected, results, forbidden_file

    progress(0.1, desc="Processing...")

    total, accepted, rejected, results, forbidden_file = asyncio.run(run_batch())

    progress(1.0, desc="Complete")

    header = f"Complete: {total} files\n"
    header += f"✅ {accepted} accepted  |  ❌ {rejected} rejected\n"
    if forbidden_file:
        header += f"Using: {Path(forbidden_file.name).name}\n"
    header += "─" * 40 + "\n\n"

    yield header + "\n".join(results)


# Build interface
with gr.Blocks(title="Product Safety", theme=theme, css=css) as demo:

    gr.HTML("""
        <div style="padding: 1rem 0;">
            <h1 class="title">Product Safety Compliance</h1>
            <p class="subtitle">Upload product files to check for forbidden ingredients</p>
        </div>
    """)

    with gr.Tabs():
        with gr.Tab("Single File", id="single"):
            with gr.Row():
                single_input = gr.File(
                    label="Product File",
                    file_types=[".pdf", ".png", ".jpg", ".jpeg", ".txt"],
                    elem_classes="file-upload",
                )
                single_forbidden = gr.File(
                    label="Custom Forbidden List (optional)",
                    file_types=[".csv"],
                    elem_classes="file-upload",
                )
            single_btn = gr.Button("Evaluate", variant="primary", size="lg")
            single_output = gr.Textbox(
                label="Result",
                lines=14,
                max_lines=20,
                interactive=False,
                elem_classes="output-text",
                placeholder="Results will appear here...",
            )

            single_btn.click(
                fn=evaluate_single,
                inputs=[single_input, single_forbidden],
                outputs=[single_output],
            )

        with gr.Tab("Batch", id="batch"):
            with gr.Row():
                batch_input = gr.File(
                    label="Product Files",
                    file_count="multiple",
                    file_types=[".pdf", ".png", ".jpg", ".jpeg", ".txt"],
                    elem_classes="file-upload",
                )
                batch_forbidden = gr.File(
                    label="Custom Forbidden List (optional)",
                    file_types=[".csv"],
                    elem_classes="file-upload",
                )
            batch_btn = gr.Button("Evaluate All", variant="primary", size="lg")
            batch_output = gr.Textbox(
                label="Results",
                lines=18,
                max_lines=30,
                interactive=False,
                elem_classes="output-text",
                placeholder="Results will appear here...",
                autoscroll=True,
            )

            batch_btn.click(
                fn=evaluate_batch,
                inputs=[batch_input, batch_forbidden],
                outputs=[batch_output],
            )


def main():
    import asyncio
    print("Initializing pipeline...")
    asyncio.run(init_default_pipeline())
    print("Starting UI at http://localhost:7860")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )


if __name__ == "__main__":
    main()
