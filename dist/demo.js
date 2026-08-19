"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const collections_1 = require("./utils/collections");
const search_1 = require("./utils/search");
const transformations_1 = require("./utils/transformations");
const validations_1 = require("./utils/validations");
// Sample data
const sampleProducts = [
    {
        sku: "SHOE-BLK-42",
        name: "Black Running Shoes - Size 42",
        category: "Fashion",
        weightKg: 0.8,
        dimensions: { lengthCm: 35, widthCm: 22, heightCm: 12 },
        warehouse: "Los Angeles",
        stockQuantity: 45,
        minStockThreshold: 20,
        unitCostUSD: 35.0,
        isFragile: false,
        status: "Active",
    },
    {
        sku: "LAPTOP-DELL-15",
        name: "Dell Laptop 15 inch",
        category: "Electronics",
        weightKg: 2.3,
        dimensions: { lengthCm: 40, widthCm: 28, heightCm: 3 },
        warehouse: "Zaragoza",
        stockQuantity: 8,
        minStockThreshold: 10,
        unitCostUSD: 650.0,
        isFragile: true,
        status: "Low stock",
    },
    {
        sku: "PERFUME-COCO-50",
        name: "Coco Perfume 50ml",
        category: "Cosmetics",
        weightKg: 0.3,
        dimensions: { lengthCm: 12, widthCm: 8, heightCm: 15 },
        warehouse: "Los Angeles",
        stockQuantity: 120,
        minStockThreshold: 30,
        unitCostUSD: 85.0,
        isFragile: true,
        status: "Active",
    },
];
const sampleCarriers = [
    {
        id: "CAR-UPS",
        name: "UPS",
        operatesIn: ["United States"],
        baseRateUSD: 5.0,
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
        baseRateUSD: 12.0,
        ratePerKgUSD: 2.0,
        ratePerKmUSD: 0.1,
        avgDeliveryDays: 1,
        onTimeRate: 95,
        maxWeightKg: 50,
        handlesFragile: true,
        acceptsPriority: ["Express", "Same-day"],
    },
];
const sampleShipment = {
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
    declaredValueUSD: 650.0,
    carrier: null,
    status: "Pending",
    createdAt: new Date("2024-03-15"),
};
// --- Filtering ---
console.log("Products in Los Angeles:", (0, collections_1.filterProductsByWarehouse)(sampleProducts, "Los Angeles"));
console.log("Cosmetics products:", (0, collections_1.filterProductsByCategory)(sampleProducts, "Cosmetics"));
console.log("Low stock products:", (0, collections_1.filterLowStockProducts)(sampleProducts));
// --- Sorting ---
console.log("Products by stock asc:", (0, collections_1.sortProductsByStock)(sampleProducts, "asc"));
console.log("Carriers by reliability desc:", (0, collections_1.sortCarriersByReliability)(sampleCarriers, "desc"));
// --- Search ---
console.log("Find product by SKU (case-insensitive):", (0, search_1.findProductBySKU)(sampleProducts, "laptop-dell-15"));
console.log("Find shipment by ID:", (0, search_1.findShipmentById)([sampleShipment], "SH-2024-8821"));
const sortedByWeight = [...sampleProducts].sort((a, b) => a.weightKg - b.weightKg);
console.log("Binary search product by weight 2.3:", (0, search_1.binarySearchProductByWeight)(sortedByWeight, 2.3));
console.log("Binary search product by weight 5.0 (not found):", (0, search_1.binarySearchProductByWeight)(sortedByWeight, 5.0));
// --- Transformations ---
console.log("Shipping cost (SEUR):", (0, transformations_1.calculateShippingCost)(sampleShipment, sampleProducts[1], sampleCarriers[1]));
console.log("Carrier score (SEUR):", (0, transformations_1.scoreCarrierForShipment)(sampleCarriers[1], sampleShipment, sampleProducts[1]));
console.log("Best carrier:", (0, transformations_1.selectBestCarrier)(sampleCarriers, sampleShipment, sampleProducts[1]));
console.log("Count by category:", (0, transformations_1.countProductsByCategory)(sampleProducts));
console.log("Total inventory value:", (0, transformations_1.calculateTotalInventoryValue)(sampleProducts));
console.log("Average shipment distance:", (0, transformations_1.calculateAverageShipmentDistance)([sampleShipment]));
console.log("Group shipments by status:", (0, transformations_1.groupShipmentsByStatus)([sampleShipment]));
console.log("Top carriers:", (0, transformations_1.findTopCarriers)([{ ...sampleShipment, carrier: "SEUR" }, { ...sampleShipment, carrier: "DHL Express" }, { ...sampleShipment, carrier: "SEUR" }], 2));
// --- Validations ---
console.log("Validate product (valid):", (0, validations_1.validateProduct)(sampleProducts[0]));
console.log("Validate product (invalid):", (0, validations_1.validateProduct)({ ...sampleProducts[0], sku: "", weightKg: -1, unitCostUSD: 0 }));
console.log("Validate shipment (valid):", (0, validations_1.validateShipment)(sampleShipment));
console.log("Validate shipment (invalid):", (0, validations_1.validateShipment)({ ...sampleShipment, quantity: 0, declaredValueUSD: -5, destination: { ...sampleShipment.destination, distanceKm: -1 } }));
console.log("Validate carrier (valid):", (0, validations_1.validateCarrier)(sampleCarriers[0]));
console.log("Validate carrier (invalid):", (0, validations_1.validateCarrier)({ ...sampleCarriers[0], baseRateUSD: -1, onTimeRate: 120, operatesIn: [] }));
// --- Edge cases ---
console.log("Empty product array, filter by warehouse:", (0, collections_1.filterProductsByWarehouse)([], "Los Angeles"));
console.log("Empty shipment array, average distance:", (0, transformations_1.calculateAverageShipmentDistance)([]));
console.log("No suitable carrier:", (0, transformations_1.selectBestCarrier)([
    { ...sampleCarriers[0], operatesIn: ["United States"], onTimeRate: 0, acceptsPriority: [] }
], sampleShipment, sampleProducts[1]));
