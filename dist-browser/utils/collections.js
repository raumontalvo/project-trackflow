export function filterProductsByWarehouse(products, warehouse) {
    return products.filter((p) => p.warehouse === warehouse);
}
export function filterProductsByCategory(products, category) {
    return products.filter((p) => p.category === category);
}
export function filterLowStockProducts(products) {
    return products.filter((p) => p.stockQuantity <= p.minStockThreshold);
}
export function sortProductsByStock(products, order) {
    const sorted = [...products].sort((a, b) => order === "asc"
        ? a.stockQuantity - b.stockQuantity
        : b.stockQuantity - a.stockQuantity);
    return sorted;
}
export function sortCarriersByReliability(carriers, order) {
    const sorted = [...carriers].sort((a, b) => order === "asc"
        ? a.onTimeRate - b.onTimeRate
        : b.onTimeRate - a.onTimeRate);
    return sorted;
}
