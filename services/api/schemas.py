from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Existing inventory API schemas
# ---------------------------------------------------------------------------

Warehouse = Literal["LA", "ZGZ"]
Category = Literal["fashion", "electronics", "cosmetics"]
ExitType = Literal["dispatch", "loss"]


class SKUCreate(BaseModel):
    name: str = Field(..., min_length=1)
    sku: str = Field(..., min_length=1)
    client_name: str = Field(..., min_length=1)
    category: Category
    warehouse: Warehouse


class SKUResponse(SKUCreate):
    id: int
    current_stock: int


class StockEntryCreate(BaseModel):
    sku_id: int
    quantity: int = Field(..., gt=0)
    reference: str = Field(..., min_length=1)
    warehouse: Warehouse


class StockEntryResponse(StockEntryCreate):
    id: int
    created_at: datetime
    user_uuid: str


class StockExitCreate(BaseModel):
    sku_id: int
    quantity: int = Field(..., gt=0)
    exit_type: ExitType
    tracking_number: str | None = None
    warehouse: Warehouse

    @model_validator(mode="after")
    def validate_tracking_number(self):
        if self.exit_type == "dispatch" and not self.tracking_number:
            raise ValueError(
                "tracking_number is required when exit_type is dispatch"
            )

        if self.exit_type == "loss" and self.tracking_number is not None:
            raise ValueError(
                "tracking_number must be null when exit_type is loss"
            )

        return self


class StockExitResponse(StockExitCreate):
    id: int
    created_at: datetime
    user_uuid: str


class StockMovementResponse(BaseModel):
    id: int
    movement_type: Literal["entry", "exit"]
    sku_id: int
    sku: str
    sku_name: str
    quantity: int
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    reference: str | None = None
    exit_type: str | None = None
    tracking_number: str | None = None


# ---------------------------------------------------------------------------
# Milestone 9 Part 1 — RFP intake API schemas
# ---------------------------------------------------------------------------

RFPStatus = Literal[
    "analyzing",
    "discarded",
    "intake_complete",
    "drafting",
    "under_evaluation",
    "waiting_for_approval",
    "done",
]

DepartmentId = Literal[
    "warehouse",
    "lastmile",
    "reverse",
]

ServiceId = Literal[
    "warehousing",
    "last_mile",
    "returns",
]

ClientCountry = Literal[
    "US",
    "Spain",
]

Currency = Literal[
    "USD",
    "EUR",
]


class ClassificationResult(BaseModel):
    """
    Structured result produced by the RFP classifier.
    """

    is_rfp: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)


class ReadabilityMetrics(BaseModel):
    """
    Readability measurements calculated from converted Markdown.
    """

    flesch_reading_ease: float | None = None
    flesch_kincaid_grade: float | None = None
    gunning_fog: float | None = None
    coleman_liau: float | None = None
    word_count: int | None = None


class RFPMetadataResponse(BaseModel):
    """
    Trusted metadata for a document accepted as a TrackFlow RFP.
    """

    model_config = ConfigDict(from_attributes=True)

    rfp_id: str

    client_name: str | None = None
    client_country: ClientCountry | None = None
    currency: Currency | None = None

    services_requested: list[ServiceId] = Field(default_factory=list)

    monthly_volume: int | None = None
    deadline: date | None = None
    budget_range: str | None = None

    departments_needed: list[DepartmentId] = Field(
        default_factory=list
    )

    readability_metrics: dict = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime


class DepartmentKeyAspects(BaseModel):
    """
    Structured Part 1 output from a department worker.
    """

    department_id: DepartmentId
    owner: str

    requested_scope: list[str] = Field(default_factory=list)

    known_requirements: list[str] = Field(default_factory=list)

    quantitative_requirements: dict[str, str | int | float] = Field(
        default_factory=dict
    )

    open_questions: list[str] = Field(default_factory=list)

    relevant_extracts: list[str] = Field(default_factory=list)


class DepartmentSectionResponse(BaseModel):
    """
    Persisted department analysis returned to Sales.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    rfp_id: str

    department_id: DepartmentId
    owner: str

    key_aspects: dict = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime


class IntakeSummary(BaseModel):
    """
    Synthesized result Sales can read without opening the source PDF.
    """

    client_name: str | None = None
    client_country: ClientCountry | None = None
    currency: Currency | None = None

    departments_needed: list[DepartmentId] = Field(
        default_factory=list
    )

    department_results: list[DepartmentKeyAspects] = Field(
        default_factory=list
    )

    sales_questions: list[str] = Field(default_factory=list)


class TicketCreatedResponse(BaseModel):
    """
    Immediate response returned after PDF upload.

    The HTTP endpoint should return this with status 202.
    """

    ticket_id: str
    status: Literal["analyzing"]


class TicketStatusResponse(BaseModel):
    """
    Polling response for the ticket-mode UI.
    """

    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    status: RFPStatus
    rfp_id: str | None = None
    raw_pdf_path: str
    error_message: str | None = None

    created_at: datetime
    updated_at: datetime


class RFPIntakeResultResponse(BaseModel):
    """
    Full Part 1 result returned when a ticket has finished processing.
    """

    ticket: TicketStatusResponse

    classification: ClassificationResult | None = None

    rfp: RFPMetadataResponse | None = None

    departments: list[DepartmentSectionResponse] = Field(
        default_factory=list
    )

    summary: IntakeSummary | None = None