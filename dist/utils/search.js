"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.findProductBySKU = findProductBySKU;
exports.findShipmentById = findShipmentById;
exports.binarySearchProductByWeight = binarySearchProductByWeight;
function findProductBySKU(products, sku) {
    const found = products.find((p) => p.sku.toLowerCase() === sku.toLowerCase());
    return found || null;
}
function findShipmentById(shipments, id) {
    const found = shipments.find((s) => s.id === id);
    return found || null;
}
// Assumes sortedProducts is sorted ascending by weightKg
function binarySearchProductByWeight(sortedProducts, targetWeight) {
    let left = 0;
    let right = sortedProducts.length - 1;
    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        const weight = sortedProducts[mid].weightKg;
        if (weight === targetWeight)
            return mid;
        if (weight < targetWeight)
            left = mid + 1;
        else
            right = mid - 1;
    }
    return -1;
}
