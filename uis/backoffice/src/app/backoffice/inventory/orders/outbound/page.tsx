"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  createOutboundOrder,
  getInventoryProducts,
  type ExitType,
  type InventoryProduct,
  type Warehouse,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

const MIN_STOCK_THRESHOLD = 10;

function normalizeWarehouse(
  warehouse: Warehouse
): "los_angeles" | "zaragoza" {
  return warehouse === "LA" ? "los_angeles" : "zaragoza";
}

function createClientId(clientName: string): string {
  return clientName
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function getCreatedBy(): string {
  if (typeof window === "undefined") {
    return "unknown";
  }

  return localStorage.getItem("user_uuid") ?? "unknown";
}

function getOrderId(response: unknown): string {
  if (
    typeof response === "object" &&
    response !== null &&
    "id" in response
  ) {
    const id = (response as { id?: unknown }).id;

    if (typeof id === "string" || typeof id === "number") {
      return String(id);
    }
  }

  return crypto.randomUUID();
}

function getFailureReason(
  error: unknown
):
  | "insufficient_stock"
  | "unknown_sku"
  | "invalid_quantity"
  | "unknown_client" {
  if (!(error instanceof Error)) {
    return "unknown_sku";
  }

  const message = error.message.toLowerCase();

  if (message.includes("insufficient stock")) {
    return "insufficient_stock";
  }

  if (message.includes("quantity") || message.includes("validation")) {
    return "invalid_quantity";
  }

  if (message.includes("client")) {
    return "unknown_client";
  }

  return "unknown_sku";
}

export default function OutboundOrderPage() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [skuId, setSkuId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [exitType, setExitType] = useState<ExitType>("dispatch");
  const [trackingNumber, setTrackingNumber] = useState("");
  const [warehouse, setWarehouse] = useState<Warehouse>("LA");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [quantityError, setQuantityError] = useState("");
  const [success, setSuccess] = useState("");

  const formStartedAt = useRef<number | null>(null);
  const submissionCompleted = useRef(false);

  const selectedProduct = useMemo(
    () => products.find((product) => product.id === Number(skuId)),
    [products, skuId]
  );

  const requestedQuantity = Number(quantity || 0);
  const availableStock = selectedProduct?.current_stock ?? 0;

  const overAvailableStock =
    Boolean(selectedProduct) && requestedQuantity > availableStock;

  useEffect(() => {
    async function loadProducts() {
      try {
        setLoading(true);
        setError("");

        const data = await getInventoryProducts();
        setProducts(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load products."
        );
      } finally {
        setLoading(false);
      }
    }

    void loadProducts();
  }, []);

  useEffect(() => {
    return () => {
      if (
        submissionCompleted.current ||
        formStartedAt.current === null ||
        !selectedProduct
      ) {
        return;
      }

      const timeOnFormSeconds = Math.max(
        1,
        Math.round((Date.now() - formStartedAt.current) / 1000)
      );

      let abandonedStep:
        | "sku_selection"
        | "quantity_entry"
        | "carrier_selection"
        | "final_submit" = "sku_selection";

      if (skuId && !quantity) {
        abandonedStep = "quantity_entry";
      } else if (
        skuId &&
        quantity &&
        exitType === "dispatch" &&
        !trackingNumber
      ) {
        abandonedStep = "carrier_selection";
      } else if (skuId && quantity) {
        abandonedStep = "final_submit";
      }

      track("dispatch_form_abandoned", {
        warehouse: normalizeWarehouse(warehouse),
        sku_id: String(selectedProduct.id),
        client_id: createClientId(selectedProduct.client_name),
        abandoned_step: abandonedStep,
        time_on_form_seconds: timeOnFormSeconds,
        created_by: getCreatedBy(),
      });
    };
  }, [
    exitType,
    quantity,
    selectedProduct,
    skuId,
    trackingNumber,
    warehouse,
  ]);

  function markFormStarted(): void {
    if (formStartedAt.current === null) {
      formStartedAt.current = Date.now();
    }

    submissionCompleted.current = false;
  }

  function trackDispatchFailure(
    failureReason:
      | "insufficient_stock"
      | "unknown_sku"
      | "invalid_quantity"
      | "unknown_client"
  ): void {
    if (!selectedProduct) {
      return;
    }

    track("dispatch_order_failed", {
      sku_id: String(selectedProduct.id),
      sku_code: selectedProduct.sku,
      warehouse: normalizeWarehouse(warehouse),
      client_id: createClientId(selectedProduct.client_name),
      destination_country: "unknown",
      quantity: Number(quantity || 0),
      failure_reason: failureReason,
      created_by: getCreatedBy(),
      sla_sensitive: exitType === "dispatch",
    });
  }

  async function handleSubmit(
    event: React.FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    setError("");
    setQuantityError("");
    setSuccess("");

    if (!selectedProduct) {
      setError("Choose a valid SKU before registering the outbound exit.");
      return;
    }

    const numericQuantity = Number(quantity);

    if (!Number.isInteger(numericQuantity) || numericQuantity <= 0) {
      trackDispatchFailure("invalid_quantity");
      setQuantityError("Quantity must be a positive whole number.");
      return;
    }

    if (exitType === "dispatch" && !trackingNumber.trim()) {
      setError("Tracking number is required for dispatch orders.");
      return;
    }

    if (overAvailableStock) {
      trackDispatchFailure("insufficient_stock");

      setQuantityError(
        `Only ${availableStock} units are currently available for this SKU.`
      );

      return;
    }

    try {
      setSubmitting(true);

      const response = await createOutboundOrder({
        sku_id: selectedProduct.id,
        quantity: numericQuantity,
        exit_type: exitType,
        tracking_number:
          exitType === "dispatch" ? trackingNumber.trim() : null,
        warehouse,
      });

      const dispatchOrderId = getOrderId(response);
      const currentStock = availableStock - numericQuantity;

      track("dispatch_order_created", {
        dispatch_order_id: dispatchOrderId,
        sku_id: String(selectedProduct.id),
        sku_code: selectedProduct.sku,
        warehouse: normalizeWarehouse(warehouse),
        client_id: createClientId(selectedProduct.client_name),
        destination_country: "unknown",
        quantity: numericQuantity,
        carrier: exitType === "dispatch" ? "configured_carrier" : "not_applicable",
        created_by: getCreatedBy(),
      });

      if (currentStock <= MIN_STOCK_THRESHOLD) {
        track("stock_threshold_triggered", {
          sku_id: String(selectedProduct.id),
          sku_code: selectedProduct.sku,
          warehouse: normalizeWarehouse(warehouse),
          client_id: createClientId(selectedProduct.client_name),
          current_stock: currentStock,
          min_stock_threshold: MIN_STOCK_THRESHOLD,
          triggering_dispatch_order_id: dispatchOrderId,
        });
      }

      submissionCompleted.current = true;
      formStartedAt.current = null;

      setSkuId("");
      setQuantity("");
      setExitType("dispatch");
      setTrackingNumber("");
      setWarehouse("LA");
      setSuccess("Outbound exit registered successfully.");
    } catch (err) {
      trackDispatchFailure(getFailureReason(err));

      const message =
        err instanceof Error
          ? err.message
          : "Failed to register outbound exit.";

      if (message.toLowerCase().includes("insufficient stock")) {
        setQuantityError(message);
      } else {
        setError(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main
      style={{
        padding: "32px",
        maxWidth: "760px",
        margin: "0 auto",
      }}
    >
      <header style={{ marginBottom: "24px" }}>
        <p
          style={{
            color: "#6b7280",
            marginBottom: "8px",
          }}
        >
          TrackFlow Warehouse Operations
        </p>

        <h1
          style={{
            fontSize: "32px",
            marginBottom: "8px",
          }}
        >
          Register Outbound Exit
        </h1>

        <p style={{ color: "#6b7280" }}>
          Log dispatches, consumption, losses, or exits from warehouse stock.
        </p>
      </header>

      <nav
        style={{
          display: "flex",
          gap: "12px",
          marginBottom: "24px",
          flexWrap: "wrap",
        }}
      >
        <Link href="/backoffice/inventory/products">
          Products
        </Link>

        <Link href="/backoffice/inventory/orders/inbound">
          Inbound Delivery
        </Link>

        <Link href="/backoffice/inventory/orders">
          Order History
        </Link>
      </nav>

      {loading && <p>Loading SKUs...</p>}

      {error && (
        <div
          style={{
            padding: "16px",
            background: "#fee2e2",
            color: "#991b1b",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          {error}
        </div>
      )}

      {quantityError && (
        <div
          style={{
            padding: "16px",
            background: "#fef3c7",
            color: "#92400e",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          {quantityError}
        </div>
      )}

      {success && (
        <div
          style={{
            padding: "16px",
            background: "#dcfce7",
            color: "#166534",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          {success}
        </div>
      )}

      {!loading && (
        <form
          onSubmit={handleSubmit}
          onChange={markFormStarted}
          style={{
            display: "grid",
            gap: "16px",
          }}
        >
          <label
            style={{
              display: "grid",
              gap: "6px",
            }}
          >
            <span>SKU</span>

            <select
              required
              value={skuId}
              onChange={(event) => {
                markFormStarted();

                const nextSkuId = event.target.value;
                const product = products.find(
                  (item) => item.id === Number(nextSkuId)
                );

                setSkuId(nextSkuId);

                if (product) {
                  setWarehouse(product.warehouse);
                }
              }}
              style={{ padding: "12px" }}
            >
              <option value="">Choose a SKU</option>

              {products.map((product) => (
                <option
                  key={product.id}
                  value={product.id}
                >
                  {product.sku} — {product.name} — stock:{" "}
                  {product.current_stock}
                </option>
              ))}
            </select>
          </label>

          <label
            style={{
              display: "grid",
              gap: "6px",
            }}
          >
            <span>Quantity</span>

            <input
              type="number"
              min="1"
              step="1"
              required
              value={quantity}
              onChange={(event) => {
                markFormStarted();
                setQuantity(event.target.value);
              }}
              style={{ padding: "12px" }}
            />
          </label>

          <label
            style={{
              display: "grid",
              gap: "6px",
            }}
          >
            <span>Exit type</span>

            <select
              value={exitType}
              onChange={(event) => {
                markFormStarted();

                const nextExitType = event.target.value as ExitType;
                setExitType(nextExitType);

                if (nextExitType === "loss") {
                  setTrackingNumber("");
                }
              }}
              style={{ padding: "12px" }}
            >
              <option value="dispatch">Dispatch</option>
              <option value="loss">Loss</option>
            </select>
          </label>

          {exitType === "dispatch" && (
            <label
              style={{
                display: "grid",
                gap: "6px",
              }}
            >
              <span>Tracking number</span>

              <input
                type="text"
                required
                value={trackingNumber}
                onChange={(event) => {
                  markFormStarted();
                  setTrackingNumber(event.target.value);
                }}
                style={{ padding: "12px" }}
              />
            </label>
          )}

          <label
            style={{
              display: "grid",
              gap: "6px",
            }}
          >
            <span>Warehouse</span>

            <select
              value={warehouse}
              onChange={(event) => {
                markFormStarted();
                setWarehouse(event.target.value as Warehouse);
              }}
              style={{ padding: "12px" }}
            >
              <option value="LA">Los Angeles</option>
              <option value="ZGZ">Zaragoza</option>
            </select>
          </label>

          {selectedProduct && (
            <p>
              Available stock: <strong>{availableStock}</strong>
            </p>
          )}

          <button
            type="submit"
            disabled={submitting || products.length === 0}
            style={{
              padding: "12px",
              fontWeight: 700,
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            {submitting
              ? "Registering..."
              : "Register Outbound Exit"}
          </button>
        </form>
      )}
    </main>
  );
}