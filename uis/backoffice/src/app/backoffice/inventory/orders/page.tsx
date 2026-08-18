"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getInventoryOrders, type StockMovement } from "@/lib/inventory";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function OrdersHistoryPage() {
  const [orders, setOrders] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadOrders() {
      try {
        setLoading(true);
        setError("");
        const data = await getInventoryOrders();
        setOrders(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load orders.");
      } finally {
        setLoading(false);
      }
    }

    loadOrders();
  }, []);

  return (
    <main style={{ padding: "32px", maxWidth: "1200px", margin: "0 auto" }}>
      <header style={{ marginBottom: "24px" }}>
        <p style={{ color: "#6b7280", marginBottom: "8px" }}>
          TrackFlow Warehouse Operations
        </p>
        <h1 style={{ fontSize: "32px", marginBottom: "8px" }}>
          Inventory Order History
        </h1>
        <p style={{ color: "#6b7280" }}>
          Read-only history of inbound deliveries and outbound stock exits.
        </p>
      </header>

      <nav style={{ display: "flex", gap: "12px", marginBottom: "24px", flexWrap: "wrap" }}>
        <Link href="/backoffice/inventory/products">Products</Link>
        <Link href="/backoffice/inventory/orders/inbound">Inbound Delivery</Link>
        <Link href="/backoffice/inventory/orders/outbound">Outbound Exit</Link>
      </nav>

      {loading && <p>Loading inventory order history...</p>}

      {error && (
        <div style={{ padding: "16px", background: "#fee2e2", color: "#991b1b", borderRadius: "8px" }}>
          {error}
        </div>
      )}

      {!loading && !error && orders.length === 0 && (
        <p>No inventory orders found.</p>
      )}

      {!loading && !error && orders.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", background: "white", color: "#111827" }}>
            <thead>
              <tr style={{ background: "#f3f4f6", textAlign: "left" }}>
                <th style={{ padding: "12px" }}>Date</th>
                <th style={{ padding: "12px" }}>SKU</th>
                <th style={{ padding: "12px" }}>Product Name</th>
                <th style={{ padding: "12px" }}>Movement</th>
                <th style={{ padding: "12px" }}>Quantity</th>
                <th style={{ padding: "12px" }}>Warehouse</th>
                <th style={{ padding: "12px" }}>Reference / Tracking</th>
                <th style={{ padding: "12px" }}>Created By</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const isEntry = order.movement_type === "entry";

                return (
                  <tr
                    key={`${order.movement_type}-${order.id}`}
                    style={{
                      borderTop: "1px solid #e5e7eb",
                      background: isEntry ? "#f0fdf4" : "#fef2f2",
                    }}
                  >
                    <td style={{ padding: "12px" }}>{formatDate(order.created_at)}</td>
                    <td style={{ padding: "12px", fontWeight: 700 }}>{order.sku}</td>
                    <td style={{ padding: "12px" }}>{order.sku_name}</td>
                    <td style={{ padding: "12px", fontWeight: 700 }}>
                      {isEntry ? "Inbound Delivery" : "Outbound Exit"}
                    </td>
                    <td style={{ padding: "12px" }}>{order.quantity}</td>
                    <td style={{ padding: "12px" }}>{order.warehouse}</td>
                    <td style={{ padding: "12px" }}>
                      {order.reference || order.tracking_number || order.exit_type || "—"}
                    </td>
                    <td style={{ padding: "12px" }}>{order.user_uuid}</td>
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