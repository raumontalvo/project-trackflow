"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  createInboundOrder,
  getInventoryProducts,
  type InventoryProduct,
  type Warehouse,
} from "@/lib/inventory";

export default function InboundOrderPage() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [skuId, setSkuId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [reference, setReference] = useState("");
  const [warehouse, setWarehouse] = useState<Warehouse>("LA");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    async function loadProducts() {
      try {
        setLoading(true);
        setError("");
        const data = await getInventoryProducts();
        setProducts(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load products.");
      } finally {
        setLoading(false);
      }
    }

    loadProducts();
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!skuId) {
      setError("Choose a SKU before registering the inbound delivery.");
      return;
    }

    try {
      setSubmitting(true);

      await createInboundOrder({
        sku_id: Number(skuId),
        quantity: Number(quantity),
        reference,
        warehouse,
      });

      setSkuId("");
      setQuantity("");
      setReference("");
      setWarehouse("LA");
      setSuccess("Inbound delivery registered successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register inbound delivery.");
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
          Register Inbound Delivery
        </h1>
        <p style={{ color: "#6b7280" }}>
          Log stock received into the Los Angeles or Zaragoza warehouse.
        </p>
      </header>

      <nav style={{ display: "flex", gap: "12px", marginBottom: "24px", flexWrap: "wrap" }}>
        <Link href="/backoffice/inventory/products">Products</Link>
        <Link href="/backoffice/inventory/orders/outbound">Outbound Exit</Link>
        <Link href="/backoffice/inventory/orders">Order History</Link>
      </nav>

      {loading && <p>Loading SKUs...</p>}

      {error && (
        <div style={{ padding: "16px", background: "#fee2e2", color: "#991b1b", borderRadius: "8px", marginBottom: "16px" }}>
          {error}
        </div>
      )}

      {success && (
        <div style={{ padding: "16px", background: "#dcfce7", color: "#166534", borderRadius: "8px", marginBottom: "16px" }}>
          {success}
        </div>
      )}

      {!loading && (
        <form onSubmit={handleSubmit} style={{ display: "grid", gap: "16px" }}>
          <label>
            SKU Product
            <select
              value={skuId}
              onChange={(event) => setSkuId(event.target.value)}
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

          <label>
            Warehouse
            <select
              value={warehouse}
              onChange={(event) => setWarehouse(event.target.value as Warehouse)}
              required
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            >
              <option value="LA">Los Angeles Warehouse</option>
              <option value="ZGZ">Zaragoza Warehouse</option>
            </select>
          </label>

          <label>
            Quantity Received
            <input
              type="number"
              min="1"
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              required
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            />
          </label>

          <label>
            Delivery Reference
            <input
              value={reference}
              onChange={(event) => setReference(event.target.value)}
              required
              placeholder="Supplier delivery note, email reference, or warehouse receipt"
              style={{ width: "100%", padding: "12px", marginTop: "6px" }}
            />
          </label>

          <button
            type="submit"
            disabled={submitting}
            style={{ padding: "12px 16px", fontWeight: 700, cursor: "pointer" }}
          >
            {submitting ? "Saving Delivery..." : "Register Inbound Delivery"}
          </button>
        </form>
      )}
    </main>
  );
}