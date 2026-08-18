const API_BASE_URL =
  process.env.NEXT_PUBLIC_INVENTORY_API_URL || "http://localhost:8000";

export type Warehouse = "LA" | "ZGZ";
export type Category = "fashion" | "electronics" | "cosmetics";
export type ExitType = "dispatch" | "loss";

export type InventoryProduct = {
  id: number;
  name: string;
  sku: string;
  client_name: string;
  category: Category;
  warehouse: Warehouse;
  current_stock: number;
};

export type StockMovement = {
  id: number;
  movement_type: "entry" | "exit";
  sku_id: number;
  sku: string;
  sku_name: string;
  quantity: number;
  warehouse: Warehouse;
  created_at: string;
  user_uuid: string;
  reference?: string | null;
  exit_type?: ExitType | null;
  tracking_number?: string | null;
};

export type InboundOrderPayload = {
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: Warehouse;
};

export type OutboundOrderPayload = {
  sku_id: number;
  quantity: number;
  exit_type: ExitType;
  tracking_number: string | null;
  warehouse: Warehouse;
};

async function parseApiError(response: Response): Promise<string> {
  try {
    const data = await response.json();

    if (typeof data.detail === "string") {
      return data.detail;
    }

    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { msg?: string }) => item.msg || "Validation error")
        .join(", ");
    }

    return "The inventory API returned an error.";
  } catch {
    return `Request failed with status ${response.status}`;
  }
}

async function inventoryRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }

    throw new Error("You must be logged in to access inventory.");
  }

  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }

  return response.json() as Promise<T>;
}

export function getInventoryProducts(): Promise<InventoryProduct[]> {
  return inventoryRequest<InventoryProduct[]>("/inventory/products");
}

export function getInventoryOrders(): Promise<StockMovement[]> {
  return inventoryRequest<StockMovement[]>("/inventory/orders");
}

export function createInboundOrder(
  payload: InboundOrderPayload
): Promise<unknown> {
  return inventoryRequest<unknown>("/inventory/orders/inbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function createOutboundOrder(
  payload: OutboundOrderPayload
): Promise<unknown> {
  return inventoryRequest<unknown>("/inventory/orders/outbound", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}