"""Hugging Face Gradio / ZeroGPU entry point.

Local development continues to use FastAPI (`backend.main:app`).
This file is the Space UI and the programmatic API for Vercel.
"""

from __future__ import annotations

import spaces
import gradio as gr

from backend.services.space_runtime import (
    analyze_payload,
    generate_payload,
    health_payload,
    try_load_space_model,
)

# Import `spaces` before loading weights. ZeroGPU intercepts `.to("cuda")` at
# module scope, packs both BERT stages, and streams them into VRAM on demand.
try_load_space_model()

KINDS = [
    "auto",
    "functional",
    "performance",
    "security",
    "usability",
    "availability",
    "compatibility",
    "other",
]


@spaces.GPU(duration=45)
def analyze(requirement: str) -> dict:
    """Analyze one requirement. Same JSON shape as POST /api/analyze."""
    return analyze_payload(requirement)


@spaces.GPU(duration=45)
def generate_requirement(
    idea: str,
    requirement_type: str | None = None,
    details: str | None = None,
) -> dict:
    """Create a requirement from an idea. Same JSON shape as POST /api/generate-requirement."""
    return generate_payload(idea, requirement_type, details)


def health() -> dict:
    """Report whether Stage A and Stage B files/models are available."""
    return health_payload()


with gr.Blocks(title="Requirement Ambiguity AI") as demo:
    gr.Markdown(
        "Two-stage BERT requirement analysis on ZeroGPU. "
        "Programmatic API names: `/health`, `/analyze`, `/generate_requirement`."
    )
    with gr.Tab("Analyze"):
        requirement = gr.Textbox(label="requirement", lines=5)
        analyze_button = gr.Button("Analyze")
        analyze_result = gr.JSON(label="result")
        analyze_button.click(
            analyze,
            inputs=requirement,
            outputs=analyze_result,
            api_name="analyze",
        )
    with gr.Tab("Generate"):
        idea = gr.Textbox(label="idea", lines=4)
        requirement_type = gr.Dropdown(KINDS, value="auto", label="requirement_type")
        details = gr.Textbox(label="details")
        generate_button = gr.Button("Generate requirement")
        generate_result = gr.JSON(label="result")
        generate_button.click(
            generate_requirement,
            inputs=[idea, requirement_type, details],
            outputs=generate_result,
            api_name="generate_requirement",
        )
    with gr.Tab("Health"):
        health_button = gr.Button("Check health")
        health_result = gr.JSON(label="result")
        health_button.click(health, outputs=health_result, api_name="health")

demo.queue()

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0")
