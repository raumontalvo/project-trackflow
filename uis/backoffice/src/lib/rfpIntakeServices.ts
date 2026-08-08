export type RfpStatus =
  | "analyzing"
  | "discarded"
  | "intake_complete"
  | "drafting"
  | "under_evaluation"
  | "waiting_for_approval"
  | "done";

export interface ReadabilityMetrics {
  flesch_reading_ease?: number | null;
  flesch_kincaid_grade?: number | null;
  gunning_fog?: number | null;
  coleman_liau?: number | null;
  word_count?: number | null;
}

export interface DepartmentKeyAspects {
  department_id: string;
  owner: string;
  requested_scope?: string[];
  known_requirements?: string[];
  quantitative_requirements?: Record<string, string | number>;
  open_questions?: string[];
  relevant_extracts?: string[];
}

export interface DepartmentSection {
  id: string;
  rfp_id: string;
  department_id: string;
  owner: string;
  key_aspects: DepartmentKeyAspects;
  created_at: string;
  updated_at: string;
}

export interface RfpMetadata {
  rfp_id: string;
  client_name: string | null;
  client_country: string | null;
  currency: string | null;
  services_requested: string[];
  monthly_volume: number | null;
  deadline: string | null;
  budget_range: string | null;
  departments_needed: string[];
  readability_metrics: ReadabilityMetrics;
  created_at: string;
  updated_at: string;
}

export interface IntakeSummary {
  client_name?: string | null;
  client_country?: string | null;
  currency?: string | null;
  departments_needed?: string[];
  department_results?: DepartmentKeyAspects[];
  sales_questions?: string[];
}

export interface TicketCreatedResponse {
  ticket_id: string;
  status: "analyzing";
}

export interface TicketResponse {
  ticket_id: string;
  status: RfpStatus;
  rfp_id: string | null;
  raw_pdf_path: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  rfp: RfpMetadata | null;
  departments: DepartmentSection[];
  summary: IntakeSummary | null;
}

const API_BASE_URL = "/api";


async function readErrorMessage(
  response: Response,
  fallback: string
): Promise<string> {
  try {
    const body = await response.json();

    if (
      body &&
      typeof body === "object" &&
      "detail" in body &&
      typeof body.detail === "string"
    ) {
      return body.detail;
    }
  } catch {
    // Ignore JSON parsing errors and use the fallback message.
  }

  return fallback;
}


export async function uploadRfp(
  file: File
): Promise<TicketCreatedResponse> {
  const formData = new FormData();

  formData.append("file", file);

  const response = await fetch(
    `${API_BASE_URL}/rfp-intake`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      "Unable to upload RFP."
    );

    throw new Error(message);
  }

  return response.json() as Promise<TicketCreatedResponse>;
}


export async function getRfpTicket(
  ticketId: string
): Promise<TicketResponse> {
  const response = await fetch(
    `${API_BASE_URL}/rfp-intake/${encodeURIComponent(
      ticketId
    )}`,
    {
      method: "GET",
      cache: "no-store",
    }
  );

  if (!response.ok) {
    const message = await readErrorMessage(
      response,
      "Unable to load RFP ticket."
    );

    throw new Error(message);
  }

  return response.json() as Promise<TicketResponse>;
}