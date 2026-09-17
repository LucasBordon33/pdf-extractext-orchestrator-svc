import pytest

from orchestrator.models.pdf import PDF
from orchestrator.models.pipeline import PipelineResult, StageStatus


def test_pdf_stores_fields():
    pdf = PDF(id="abc", name="doc.pdf", text="hola", checksum="sha")
    assert pdf.id == "abc"
    assert pdf.name == "doc.pdf"
    assert pdf.text == "hola"
    assert pdf.checksum == "sha"


def test_pipeline_result_tracks_stage_status():
    result = PipelineResult()
    stage = result.start_stage("validate")
    result.finish_stage(stage, StageStatus.SUCCEEDED)
    assert result.stage_status("validate") is StageStatus.SUCCEEDED


def test_pipeline_result_overall_succeeded_when_all_stages_pass():
    result = PipelineResult()
    for name in ("validate", "extract", "store"):
        result.finish_stage(result.start_stage(name), StageStatus.SUCCEEDED)
    assert result.overall is StageStatus.SUCCEEDED


def test_pipeline_result_overall_failed_when_any_stage_fails():
    result = PipelineResult()
    result.finish_stage(result.start_stage("validate"), StageStatus.SUCCEEDED)
    result.finish_stage(result.start_stage("extract"), StageStatus.FAILED)
    result.finish_stage(result.start_stage("store"), StageStatus.FAILED)
    assert result.overall is StageStatus.FAILED


def test_finalize_is_callable_after_success():
    result = PipelineResult()
    for name in ("validate", "extract", "store"):
        result.finish_stage(result.start_stage(name), StageStatus.SUCCEEDED)
    result.finalize()
    assert result.overall is StageStatus.SUCCEEDED