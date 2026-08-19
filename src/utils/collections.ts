import {
  Product,
  ProductCategory,
  WarehouseLocation,
  Carrier,
} from "../types/models";

export function filterProductsByWarehouse(
  products: Product[],
  warehouse: WarehouseLocation
): Product[] {
  return products.filter((p) => p.warehouse === warehouse);
}

export function filterProductsByCategory(
  products: Product[],
  category: ProductCategory
): Product[] {
  return products.filter((p) => p.category === category);
}

export function filterLowStockProducts(products: Product[]): Product[] {
  return products.filter((p) => p.stockQuantity <= p.minStockThreshold);
}

export function sortProductsByStock(
  products: Product[],
  order: "asc" | "desc"
): Product[] {
  const sorted = [...products].sort((a, b) =>
    order === "asc"
      ? a.stockQuantity - b.stockQuantity
      : b.stockQuantity - a.stockQuantity
  );
  return sorted;
}

export function sortCarriersByReliability(
  carriers: Carrier[],
  order: "asc" | "desc"
): Carrier[] {
  const sorted = [...carriers].sort((a, b) =>
    order === "asc"
      ? a.onTimeRate - b.onTimeRate
      : b.onTimeRate - a.onTimeRate
  );
  return sorted;
}
