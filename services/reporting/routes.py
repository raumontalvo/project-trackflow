from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from data.pipelines.pipeline import (
    get_latest_pipeline_run,
    get_weekly_warehouse_client_performance,
    trigger_weekly_performance_run,
)
from services.api.auth import get_current_user
from services.reporting.schemas import (
    ManualPipelineRunRequest,
    ManualPipelineRunResponse,
    PipelineRunResponse,
    WeeklyPerformanceResponse,
)


router = APIRouter(
    prefix="/reporting",
    tags=["reporting"],
)


@router.get(
    "/weekly-warehouse-client-performance",
    response_model=WeeklyPerformanceResponse,
)
def read_weekly_warehouse_client_performance(
    week_start: date | None = Query(default=None),
) -> dict:
    return get_weekly_warehouse_client_performance(
        week_start
    )


@router.get(
    "/pipeline-runs/latest",
    response_model=PipelineRunResponse,
)
def read_latest_pipeline_run() -> dict:
    result = get_latest_pipeline_run()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pipeline runs found",
        )

    return result


@router.post(
    "/pipeline-runs",
    response_model=ManualPipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(get_current_user)],
)
def create_manual_pipeline_run(
    request: ManualPipelineRunRequest,
) -> dict:
    try:
        return trigger_weekly_performance_run(
            request.week_start
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error