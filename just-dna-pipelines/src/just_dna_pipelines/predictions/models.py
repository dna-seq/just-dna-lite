"""The prediction models this app can run, as a list of entries rather than branches in code.

Each entry says where the model lives on HuggingFace (pinned to one commit), which files a run needs,
what it is called on screen, its licence and its fixed input window. A second model is a second
entry here plus whatever its outputs need in ``scoring``; nothing else keys on a model name.
"""

from pydantic import BaseModel, Field


class PredictionModel(BaseModel):
    """One sequence-to-function model, pinned to a HuggingFace revision."""

    id: str = Field(description="Stable key used in run config, file names and the UI.")
    title: str
    summary: str = Field(description="One line for the model picker.")
    repo_id: str
    revision: str = Field(description="HuggingFace commit sha the files are fetched at.")
    files: tuple[str, ...] = Field(description="Files a run needs, fetched one by one.")
    onnx_file: str = "model.onnx"
    window: int = Field(description="Bases the ONNX graph reads per row (fixed in the graph).")
    checkpoint_step: int
    author: str
    licence: str
    licence_url: str
    output_stem: str = Field(description="Prefix of the parquet and report file names.")
    research_note: str = Field(description="What the model is and is not, shown in the report.")

    @property
    def model_card_url(self) -> str:
        return f"https://huggingface.co/{self.repo_id}"


KRONGENOME_F = PredictionModel(
    id="krongenome_f",
    title="KronGenome F",
    summary=(
        "KronLSTM sequence-to-function model (54.6 M parameters) that predicts splice sites, "
        "DNase accessibility and 155 functional tracks from 131,072 bases of DNA."
    ),
    repo_id="just-dna-seq/KronGenome-F-1Mb",
    revision="9acfb4dad8c281e8eac65e97f056c1c338463cb1",
    # model.safetensors is the PyTorch route; the ONNX graph needs no torch.
    files=("model.onnx", "onnx_meta.json", "channels.json", "config.json", "README.md"),
    window=131_072,
    checkpoint_step=96_000,
    author="Anton Kulaga",
    licence="CC BY-NC 4.0",
    licence_url="https://creativecommons.org/licenses/by-nc/4.0/",
    output_stem="krongenome_variant_effects",
    research_note=(
        "KronGenome F is a research model, and this is an intermediate training checkpoint "
        "(step 96,000 of a run scheduled to 380,000). Its splice-site prediction is well behind "
        "AlphaGenome at this checkpoint. It is not a clinical tool."
    ),
)

PREDICTION_MODELS: dict[str, PredictionModel] = {model.id: model for model in (KRONGENOME_F,)}
DEFAULT_PREDICTION_MODEL = KRONGENOME_F.id


def get_prediction_model(model_id: str) -> PredictionModel:
    """The registered model with this id; an unknown id names the ones that exist."""
    if model_id not in PREDICTION_MODELS:
        raise KeyError(f"Unknown prediction model {model_id!r}. Known: {sorted(PREDICTION_MODELS)}")
    return PREDICTION_MODELS[model_id]
