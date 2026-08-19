"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.filterProductsByWarehouse = filterProductsByWarehouse;
exports.filterProductsByCategory = filterProductsByCategory;
exports.filterLowStockProducts = filterLowStockProducts;
exports.sortProductsByStock = sortProductsByStock;
exports.sortCarriersByReliability = sortCarriersByReliability;
function filterProductsByWarehouse(products, warehouse) {
    return products.filter((p) => p.warehouse === warehouse);
}
function filterProductsByCategory(products, category) {
    return products.filter((p) => p.category === category);
}
function filterLowStockProducts(products) {
    return products.filter((p) => p.stockQuantity <= p.minStockThreshold);
}
function sortProductsByStock(products, order) {
    const sorted = [...products].sort((a, b) => order === "asc"
        ? a.stockQuantity - b.stockQuantity
        : b.stockQuantity - a.stockQuantity);
    return sorted;
}
function sortCarriersByReliability(carriers, order) {
    const sorted = [...carriers].sort((a, b) => order === "asc"
        ? a.onTimeRate - b.onTimeRate
        : b.onTimeRate - a.onTimeRate);
    return sorted;
}
