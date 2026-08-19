"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  getInventoryProducts,
  type InventoryProduct,
  type Warehouse,
} from "@/lib/inventory";
import { track } from "@/lib/telemetry";

function getStockStatus(stock: number) {
  if (stock <= 10) {
    return {
      label: "Critical",
      color: "#dc2626",
    };
  }

  if (stock <= 25) {
    return {
      label: "Low",
      color: "#ca8a04",
    };
  }

  return {
    label: "Healthy",
    color: "#16a34a",
  };
}

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

export default function InventoryProductsPage() {
  const [products, setProducts] = useState<InventoryProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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

  function rejectDirectStockEdit(product: InventoryProduct): void {
    track("direct_stock_edit_rejected", {
      sku_id: String(product.id),
      sku_code: product.sku,
      warehouse: normalizeWarehouse(product.warehouse),
      client_id: createClientId(product.client_name),
      attempted_field: "current_stock",
      rejection_reason: "direct_stock_modification_not_allowed",
      created_by: getCreatedBy(),
    });

    setNotice(
      `Direct stock editing is not allowed for ${product.sku}. Use an inbound or outbound order instead.`
    );
  }

  return (
    <main
      style={{
        padding: "32px",
        maxWidth: "1200px",
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
          Inventory Products
        </h1>

        <p style={{ color: "#6b7280" }}>
          Real-time SKU stock visibility across Los Angeles and Zaragoza
          warehouses.
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
        <Link href="/backoffice/inventory/orders/inbound">
          Register Inbound Delivery
        </Link>

        <Link href="/backoffice/inventory/orders/outbound">
          Register Outbound Exit
        </Link>

        <Link href="/backoffice/inventory/orders">
          View Order History
        </Link>
      </nav>

      {loading && <p>Loading inventory products...</p>}

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

      {notice && (
        <div
          style={{
            padding: "16px",
            background: "#fef3c7",
            color: "#92400e",
            borderRadius: "8px",
            marginBottom: "16px",
          }}
        >
          {notice}
        </div>
      )}

      {!loading && !error && products.length === 0 && (
        <p>No inventory products found.</p>
      )}

      {!loading && !error && products.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              background: "white",
              color: "#111827",
            }}
          >
            <thead>
              <tr
                style={{
                  background: "#f3f4f6",
                  textAlign: "left",
                }}
              >
                <th style={{ padding: "12px" }}>SKU</th>
                <th style={{ padding: "12px" }}>Product</th>
                <th style={{ padding: "12px" }}>Client</th>
                <th style={{ padding: "12px" }}>Category</th>
                <th style={{ padding: "12px" }}>Warehouse</th>
                <th style={{ padding: "12px" }}>Current Stock</th>
                <th style={{ padding: "12px" }}>Stock Status</th>
                <th style={{ padding: "12px" }}>Actions</th>
              </tr>
            </thead>

            <tbody>
              {products.map((product) => {
                const status = getStockStatus(product.current_stock);

                return (
                  <tr
                    key={product.id}
                    style={{
                      borderTop: "1px solid #e5e7eb",
                    }}
                  >
                    <td
                      style={{
                        padding: "12px",
                        fontWeight: 700,
                      }}
                    >
                      {product.sku}
                    </td>

                    <td style={{ padding: "12px" }}>
                      {product.name}
                    </td>

                    <td style={{ padding: "12px" }}>
                      {product.client_name}
                    </td>

                    <td style={{ padding: "12px" }}>
                      {product.category}
                    </td>

                    <td style={{ padding: "12px" }}>
                      {product.warehouse}
                    </td>

                    <td style={{ padding: "12px" }}>
                      {product.current_stock}
                    </td>

                    <td style={{ padding: "12px" }}>
                      <span
                        style={{
                          color: status.color,
                          fontWeight: 700,
                        }}
                      >
                        {status.label}
                      </span>
                    </td>

                    <td
                      style={{
                        padding: "12px",
                        display: "flex",
                        gap: "8px",
                        flexWrap: "wrap",
                      }}
                    >
                      <Link
                        href={`/backoffice/inventory/orders/inbound?skuId=${product.id}`}
                      >
                        Inbound
                      </Link>

                      <Link
                        href={`/backoffice/inventory/orders/outbound?skuId=${product.id}`}
                      >
                        Outbound
                      </Link>

                      <button
                        type="button"
                        onClick={() => rejectDirectStockEdit(product)}
                        style={{
                          border: "1px solid #dc2626",
                          background: "white",
                          color: "#dc2626",
                          padding: "4px 8px",
                          borderRadius: "4px",
                          cursor: "pointer",
                        }}
                      >
                        Edit Stock
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}