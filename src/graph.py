"""LangGraph pipeline for multi-agent onboarding.

Wraps the sequential Document Extractor → Policy Validator → PII Guardian
pipeline in a StateGraph for end-to-end tracing, confidence routing,
and future support for human-in-the-loop.
"""

import time
from contextvars import ContextVar

from langgraph.graph import END, START, StateGraph
from typing_extensions import NotRequired, TypedDict

from .agent import extract_document_data
from .metrics import PipelineRunMetric, StageMetric, get_metrics_collector
from .pii_guardian import get_pii_report, mask_dict, process_and_save_customer
from .policy_validator import validate_customer_from_document_data
from .schemas import RoutingDecision, make_routing_decision

_callbacks_var: ContextVar[list] = ContextVar("callbacks", default=[])


class OnboardingState(TypedDict):
    image_path: str
    account_type: str
    document_data: NotRequired[dict]
    routing_decision: NotRequired[str]
    validation_result: NotRequired[dict]
    masked_data: NotRequired[dict]
    pii_report: NotRequired[dict]
    save_result: NotRequired[dict]
    final_report: NotRequired[dict]
    error: NotRequired[str]


def extract_document_node(state: OnboardingState) -> dict:
    callbacks = _callbacks_var.get()
    document_data = extract_document_data(state["image_path"], callbacks=callbacks)
    decision = make_routing_decision(document_data.get("confidence", 0.0))
    return {
        "document_data": document_data,
        "routing_decision": decision.value,
    }


def validate_policy_node(state: OnboardingState) -> dict:
    callbacks = _callbacks_var.get()
    validation_result = validate_customer_from_document_data(
        state["document_data"],
        state["account_type"],
        callbacks=callbacks,
    )
    return {"validation_result": validation_result}


def mask_pii_node(state: OnboardingState) -> dict:
    masked = mask_dict(state["document_data"])
    report = get_pii_report(state["document_data"])
    return {
        "masked_data": masked.masked_data,
        "pii_report": report,
    }


def save_customer_node(state: OnboardingState) -> dict:
    record = process_and_save_customer(
        state["document_data"],
        state["validation_result"],
    )
    return {"save_result": record}


def generate_report_node(state: OnboardingState) -> dict:
    report = {
        "extraction": state.get("document_data"),
        "validation": state.get("validation_result"),
        "pii_report": state.get("pii_report"),
        "saved_record": state.get("save_result"),
    }
    if state.get("routing_decision") == RoutingDecision.REJECTED.value:
        report["error"] = "Kualitas dokumen terlalu rendah (confidence rendah). Silakan upload foto yang lebih jelas."
    return {"final_report": report}


def route_after_extraction(state: OnboardingState) -> str:
    if state.get("routing_decision") == RoutingDecision.REJECTED.value:
        return "rejected"
    return "proceed"


pipeline = None


def build_pipeline(metrics: dict | None = None) -> StateGraph:
    builder = StateGraph(OnboardingState)

    if metrics is not None:
        def _wrap(name, func):
            def wrapper(state):
                start = time.monotonic()
                try:
                    result = func(state)
                    duration = (time.monotonic() - start) * 1000
                    metrics["stages"].append(
                        StageMetric(stage=name, duration_ms=duration, success=True)
                    )
                    return result
                except Exception as exc:
                    duration = (time.monotonic() - start) * 1000
                    metrics["stages"].append(
                        StageMetric(
                            stage=name,
                            duration_ms=duration,
                            success=False,
                            error_message=str(exc),
                        )
                    )
                    raise
            return wrapper

        builder.add_node("extract_document", _wrap("extract_document", extract_document_node))
        builder.add_node("validate_policy", _wrap("validate_policy", validate_policy_node))
        builder.add_node("mask_pii", _wrap("mask_pii", mask_pii_node))
        builder.add_node("save_customer", _wrap("save_customer", save_customer_node))
        builder.add_node("generate_report", _wrap("generate_report", generate_report_node))
    else:
        builder.add_node("extract_document", extract_document_node)
        builder.add_node("validate_policy", validate_policy_node)
        builder.add_node("mask_pii", mask_pii_node)
        builder.add_node("save_customer", save_customer_node)
        builder.add_node("generate_report", generate_report_node)

    builder.add_edge(START, "extract_document")

    builder.add_conditional_edges(
        "extract_document",
        route_after_extraction,
        {"proceed": "validate_policy", "rejected": "generate_report"},
    )

    builder.add_edge("validate_policy", "mask_pii")
    builder.add_edge("mask_pii", "save_customer")
    builder.add_edge("save_customer", "generate_report")
    builder.add_edge("generate_report", END)

    return builder.compile()


def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = build_pipeline()
    return pipeline


def run_pipeline(
    image_path: str,
    account_type: str,
    callbacks: list | None = None,
) -> dict:
    _callbacks_var.set(callbacks or [])
    metrics: dict = {"stages": []}
    pipeline_start = time.monotonic()

    graph = build_pipeline(metrics=metrics)
    try:
        result = graph.invoke({
            "image_path": image_path,
            "account_type": account_type,
        })
    except Exception:
        total_duration = (time.monotonic() - pipeline_start) * 1000
        run_metric = PipelineRunMetric(
            total_duration_ms=total_duration,
            stages=metrics["stages"],
            account_type=account_type,
            validation_status="ERROR",
        )
        get_metrics_collector().record_run(run_metric)
        raise

    total_duration = (time.monotonic() - pipeline_start) * 1000

    final_report = result.get("final_report") or result
    doc_data = result.get("document_data", {})
    val_result = result.get("validation_result", {})

    run_metric = PipelineRunMetric(
        total_duration_ms=total_duration,
        stages=metrics["stages"],
        account_type=account_type,
        confidence_score=doc_data.get("confidence", 0.0),
        validation_status=val_result.get("status", ""),
    )
    get_metrics_collector().record_run(run_metric)

    return final_report
