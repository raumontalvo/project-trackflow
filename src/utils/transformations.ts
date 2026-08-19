import {
  Product,
  Carrier,
  Shipment,
  ProductCategory,
  ShipmentStatus,
  ShipmentPriority,
} from "../types/models";

export function calculateShippingCost(
  shipment: Shipment,
  product: Product,
  carrier: Carrier
): number {
  const base = carrier.baseRateUSD;
  const weightCost = product.weightKg * carrier.ratePerKgUSD * shipment.quantity;
  const distanceCost =
    shipment.destination.distanceKm * carrier.ratePerKmUSD;
  let surcharge = 0;
  switch (shipment.priority) {
    case "Express":
      surcharge = 0.3;
      break;
    case "Same-day":
      surcharge = 0.6;
      break;
    default:
      surcharge = 0;
  }
  const subtotal = base + weightCost + distanceCost;
  const total = subtotal * (1 + surcharge);
  return Math.round(total * 100) / 100;
}

export function scoreCarrierForShipment(
  carrier: Carrier,
  shipment: Shipment,
  product: Product
): number {
  let score = 0;
  // Destination country supported
  if (carrier.operatesIn.includes(shipment.destination.country)) score += 20;
  // Can handle total weight
  if (carrier.maxWeightKg >= product.weightKg * shipment.quantity) score += 20;
  // Supports priority
  if (carrier.acceptsPriority.includes(shipment.priority)) score += 15;
  // Fragile handling
  if (!product.isFragile) score += 15;
  else if (product.isFragile && carrier.handlesFragile) score += 15;
  // Reliability
  score += carrier.onTimeRate * 0.3;
  return Math.round(score * 100) / 100;
}

export function selectBestCarrier(
  carriers: Carrier[],
  shipment: Shipment,
  product: Product
):
  | { carrier: Carrier; score: number; cost: number }
  | null {
  const scored = carriers
    .map((carrier) => {
      const score = scoreCarrierForShipment(carrier, shipment, product);
      if (score < 50) return null;
      const cost = calculateShippingCost(shipment, product, carrier);
      return { carrier, score, cost };
    })
    .filter((x): x is { carrier: Carrier; score: number; cost: number } => x !== null);

  if (scored.length === 0) return null;
  scored.sort((a, b) => a.cost - b.cost);
  return scored[0];
}

export function countProductsByCategory(
  products: Product[]
): Record<ProductCategory, number> {
  const result: Record<ProductCategory, number> = {
    Fashion: 0,
    Electronics: 0,
    Cosmetics: 0,
    Home: 0,
    Other: 0,
  };
  for (const p of products) {
    result[p.category] += 1;
  }
  return result;
}

export function calculateTotalInventoryValue(products: Product[]): number {
  const total = products.reduce(
    (sum, p) => sum + p.stockQuantity * p.unitCostUSD,
    0
  );
  return Math.round(total * 100) / 100;
}

export function calculateAverageShipmentDistance(
  shipments: Shipment[]
): number {
  if (shipments.length === 0) return 0;
  const total = shipments.reduce(
    (sum, s) => sum + s.destination.distanceKm,
    0
  );
  return Math.round((total / shipments.length) * 100) / 100;
}

export function groupShipmentsByStatus(
  shipments: Shipment[]
): Record<ShipmentStatus, Shipment[]> {
  const result: Record<ShipmentStatus, Shipment[]> = {
    Pending: [],
    Assigned: [],
    "In transit": [],
    Delivered: [],
    Failed: [],
  };
  for (const s of shipments) {
    result[s.status].push(s);
  }
  return result;
}

export function findTopCarriers(
  shipments: Shipment[],
  topN: number
): Array<{ carrier: string; count: number }> {
  const counts: Record<string, number> = {};
  for (const s of shipments) {
    if (s.carrier) {
      counts[s.carrier] = (counts[s.carrier] || 0) + 1;
    }
  }
  const arr = Object.entries(counts)
    .map(([carrier, count]) => ({ carrier, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, topN);
  return arr;
}
