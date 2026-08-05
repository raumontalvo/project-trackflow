import {
  filterLowStockProducts,
  sortCarriersByReliability,
} from "../../../../src/utils/collections";

import {
  calculateAverageShipmentDistance,
  calculateShippingCost,
  calculateTotalInventoryValue,
  countProductsByCategory,
  selectBestCarrier,
} from "../../../../src/utils/transformations";

import type {
  Carrier,
  Product,
  Shipment,
} from "../../../../src/types/models";

const products: Product[] = [
  {
    sku: "SHOE-BLK-42",
    name: "Black Running Shoes - Size 42",
    category: "Fashion",
    weightKg: 0.8,
    dimensions: {
      lengthCm: 35,
      widthCm: 22,
      heightCm: 12,
    },
    warehouse: "Los Angeles",
    stockQuantity: 45,
    minStockThreshold: 20,
    unitCostUSD: 35,
    isFragile: false,
    status: "Active",
  },
  {
    sku: "LAPTOP-DELL-15",
    name: "Dell Laptop 15 inch",
    category: "Electronics",
    weightKg: 2.3,
    dimensions: {
      lengthCm: 40,
      widthCm: 28,
      heightCm: 3,
    },
    warehouse: "Zaragoza",
    stockQuantity: 8,
    minStockThreshold: 10,
    unitCostUSD: 650,
    isFragile: true,
    status: "Low stock",
  },
  {
    sku: "PERFUME-COCO-50",
    name: "Coco Perfume 50ml",
    category: "Cosmetics",
    weightKg: 0.3,
    dimensions: {
      lengthCm: 12,
      widthCm: 8,
      heightCm: 15,
    },
    warehouse: "Los Angeles",
    stockQuantity: 120,
    minStockThreshold: 30,
    unitCostUSD: 85,
    isFragile: true,
    status: "Active",
  },
];

const carriers: Carrier[] = [
  {
    id: "CAR-UPS",
    name: "UPS",
    operatesIn: ["United States"],
    baseRateUSD: 5,
    ratePerKgUSD: 1.2,
    ratePerKmUSD: 0.05,
    avgDeliveryDays: 3,
    onTimeRate: 88,
    maxWeightKg: 30,
    handlesFragile: true,
    acceptsPriority: ["Standard", "Express"],
  },
  {
    id: "CAR-SEUR",
    name: "SEUR",
    operatesIn: ["Spain"],
    baseRateUSD: 6.5,
    ratePerKgUSD: 1.5,
    ratePerKmUSD: 0.08,
    avgDeliveryDays: 2,
    onTimeRate: 92,
    maxWeightKg: 25,
    handlesFragile: true,
    acceptsPriority: ["Standard", "Express", "Same-day"],
  },
  {
    id: "CAR-DHL",
    name: "DHL Express",
    operatesIn: ["United States", "Spain"],
    baseRateUSD: 12,
    ratePerKgUSD: 2,
    ratePerKmUSD: 0.1,
    avgDeliveryDays: 1,
    onTimeRate: 95,
    maxWeightKg: 50,
    handlesFragile: true,
    acceptsPriority: ["Express", "Same-day"],
  },
];

const shipment: Shipment = {
  id: "SH-2024-8821",
  sku: "LAPTOP-DELL-15",
  quantity: 1,
  origin: "Zaragoza",
  destination: {
    city: "Madrid",
    country: "Spain",
    postalCode: "28001",
    distanceKm: 320,
  },
  priority: "Express",
  declaredValueUSD: 650,
  carrier: null,
  status: "Pending",
  createdAt: new Date("2024-03-15"),
};

export function runTrackFlowDashboard() {
  const shipmentProduct = products.find(
    (product) => product.sku === shipment.sku
  );

  if (!shipmentProduct) {
    throw new Error(`Product ${shipment.sku} was not found.`);
  }

  const recommendedCarrier = selectBestCarrier(
    carriers,
    shipment,
    shipmentProduct
  );

  const seur = carriers.find((carrier) => carrier.name === "SEUR");

  if (!seur) {
    throw new Error("SEUR carrier was not found.");
  }

  return {
    products,
    shipment,
    lowStockProducts: filterLowStockProducts(products),
    totalInventoryValue: calculateTotalInventoryValue(products),
    productCountByCategory: countProductsByCategory(products),
    carriersByReliability: sortCarriersByReliability(carriers, "desc"),
    averageShipmentDistance: calculateAverageShipmentDistance([shipment]),
    seurShippingCost: calculateShippingCost(
      shipment,
      shipmentProduct,
      seur
    ),
    recommendedCarrier,
  };
}
