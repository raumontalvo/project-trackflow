import { Product, Shipment } from "../types/models";

export function findProductBySKU(
  products: Product[],
  sku: string
): Product | null {
  const found = products.find(
    (p) => p.sku.toLowerCase() === sku.toLowerCase()
  );
  return found || null;
}

export function findShipmentById(
  shipments: Shipment[],
  id: string
): Shipment | null {
  const found = shipments.find((s) => s.id === id);
  return found || null;
}

// Assumes sortedProducts is sorted ascending by weightKg
export function binarySearchProductByWeight(
  sortedProducts: Product[],
  targetWeight: number
): number {
  let left = 0;
  let right = sortedProducts.length - 1;
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const weight = sortedProducts[mid].weightKg;
    if (weight === targetWeight) return mid;
    if (weight < targetWeight) left = mid + 1;
    else right = mid - 1;
  }
  return -1;
}
