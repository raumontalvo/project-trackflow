"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  createOutboundOrder,
  getInventoryProducts,
  type ExitType,
  type InventoryProduct,
  type Warehouse,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

function getTelemetryErrorCode(error: unknown): string {
  if (!(error instanceof Error)) {
    return "unknown_error";
  }

  const message = error.message.toLowerCase();

  if (message.includes("insufficient stock")) {
    return "insufficient_stock";
  }

  if (
    message.includes("logged in") ||
    message.includes("unauthorized") ||
    message.includes("credentials")
  ) {
    return "unauthorized";
  }

  if (message.includes("validation")) {
    return "validation_error";
  }

  if (
    message.includes("network") ||
    message.includes("fetch") ||
    message.includes("failed to connect")
  ) {
    return "network_error";
  }

  return "inventory_api_error";
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
          err instanceof Error ? err.message : "Failed to load products."
        );
      } finally {
        setLoading(false);
      }
    }

    void loadProducts();
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setQuantityError("");
    setSuccess("");

    if (!skuId) {
      setError("Choose a SKU before registering the outbound exit.");
      return;
    }

    const numericSkuId = Number(skuId);
    const numericQuantity = Number(quantity);

    if (overAvailableStock) {
      track("stock_exit_failed", {
        error_code: "insufficient_stock",
        sku_id: numericSkuId,
        warehouse,
        exit_type: exitType,
      });

      setQuantityError(
        `Only ${availableStock} units are currently available for this SKU.`
      );
      return;
    }

    try {
      setSubmitting(true);

      await createOutboundOrder({
        sku_id: numericSkuId,
        quantity: numericQuantity,
        exit_type: exitType,
        tracking_number: exitType === "dispatch" ? trackingNumber : null,
        warehouse,
      });

      track("stock_exit_created", {
        sku_id: numericSkuId,
        quantity: numericQuantity,
        warehouse,
        exit_type: exitType,
      });

      setSkuId("");
      setQuantity("");
      setExitType("dispatch");
      setTrackingNumber("");
      setWarehouse("LA");
      setSuccess("Outbound exit registered successfully.");
    } catch (err) {
      track("stock_exit_failed", {
        error_code: getTelemetryErrorCode(err),
        sku_id: numericSkuId,
        warehouse,
        exit_type: exitType,
      });

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
    <main style={{ padding: "32px", maxWidth: "760px", margin: "0 auto" }}>
      <header style={{ marginBottom: "24px" }}>
        <p style={{ color: "#6b7280", marginBottom: "8px" }}>
          TrackFlow Warehouse Operations
        </p>

        <h1 style={{ fontSize: "32px", marginBottom: "8px" }}>
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
        <Link href="/backoffice/inventory/products">Products</Link>
        <Link href="/backoffice/inventory/orders/inbound">
          Inbound Delivery
        </Link>
        <Link href="/backoffice/inventory/orders">Order History</Link>
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
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: "16px" }}>
          <label>
            SKU Product
            <select
              value={skuId}
              onChange={(event) => {
                const nextSkuId = event.target.value;
                setSkuId(nextSkuId);

                const nextProduct = products.find(
                  (product) => product.id === Number(nextSkuId)
                );

                if (nextProduct) {
                  setWarehouse(nextProduct.warehouse);
                }
              }}
              required
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            >
              <option value="">Choose a product</option>

              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} — {product.sku} — {product.warehouse}
                </option>
              ))}
            </select>
          </label>

          {selectedProduct && (
            <div
              style={{
                padding: "16px",
                background: "#eff6ff",
                color: "#1e3a8a",
                borderRadius: "8px",
              }}
            >
              <strong>Available Stock:</strong>{" "}
              {selectedProduct.current_stock} units
              <br />

              <span>
                {selectedProduct.name} / {selectedProduct.sku} /{" "}
                {selectedProduct.warehouse}
              </span>
            </div>
          )}

          <label>
            Warehouse
            <select
              value={warehouse}
              onChange={(event) =>
                setWarehouse(event.target.value as Warehouse)
              }
              required
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            >
              <option value="LA">Los Angeles Warehouse</option>
              <option value="ZGZ">Zaragoza Warehouse</option>
            </select>
          </label>

          <label>
            Exit Type
            <select
              value={exitType}
              onChange={(event) => {
                const nextExitType = event.target.value as ExitType;
                setExitType(nextExitType);

                if (nextExitType === "loss") {
                  setTrackingNumber("");
                }
              }}
              required
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            >
              <option value="dispatch">Dispatch</option>
              <option value="loss">Loss</option>
            </select>
          </label>

          <label>
            Quantity Exiting Stock
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              required
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            />
          </label>

          {overAvailableStock && (
            <div
              style={{
                padding: "12px",
                background: "#fef3c7",
                color: "#92400e",
                borderRadius: "8px",
              }}
            >
              Warning: only {availableStock} units are available. You requested{" "}
              {requestedQuantity}.
            </div>
          )}

          {quantityError && (
            <div
              style={{
                padding: "12px",
                background: "#fee2e2",
                color: "#991b1b",
                borderRadius: "8px",
              }}
            >
              {quantityError}
            </div>
          )}

          {exitType === "dispatch" && (
            <label>
              Tracking Number
              <input
                value={trackingNumber}
                onChange={(event) => setTrackingNumber(event.target.value)}
                required
                placeholder="Carrier tracking number"
                style={{ width: "100%", padding: "12px", marginTop: "6px" }}
              />
            </label>
          )}

          <button
            type="submit"
            disabled={submitting}
            style={{
              padding: "12px 16px",
              fontWeight: 700,
              cursor: submitting ? "not-allowed" : "pointer",
            }}
          >
            {submitting ? "Saving Exit..." : "Register Outbound Exit"}
          </button>
        </form>
      )}
    </main>
  );
}