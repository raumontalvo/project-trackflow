"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.validateProduct = validateProduct;
exports.validateShipment = validateShipment;
exports.validateCarrier = validateCarrier;
function validateProduct(product) {
    const errors = [];
    if (!product.sku || product.sku.trim() === "")
        errors.push("SKU must not be empty");
    if (product.weightKg <= 0 || product.weightKg > 100)
        errors.push("weightKg must be > 0 and <= 100");
    if (product.dimensions.lengthCm <= 0 ||
        product.dimensions.lengthCm > 200)
        errors.push("lengthCm must be > 0 and <= 200");
    if (product.dimensions.widthCm <= 0 ||
        product.dimensions.widthCm > 200)
        errors.push("widthCm must be > 0 and <= 200");
    if (product.dimensions.heightCm <= 0 ||
        product.dimensions.heightCm > 200)
        errors.push("heightCm must be > 0 and <= 200");
    if (product.stockQuantity < 0)
        errors.push("stockQuantity must be >= 0");
    if (product.minStockThreshold < 0)
        errors.push("minStockThreshold must be >= 0");
    if (product.unitCostUSD <= 0)
        errors.push("unitCostUSD must be > 0");
    return { valid: errors.length === 0, errors };
}
function validateShipment(shipment) {
    const errors = [];
    if (shipment.quantity <= 0)
        errors.push("quantity must be > 0");
    if (shipment.declaredValueUSD <= 0)
        errors.push("declaredValueUSD must be > 0");
    if (shipment.destination.distanceKm < 0)
        errors.push("distanceKm must be >= 0");
    return { valid: errors.length === 0, errors };
}
function validateCarrier(carrier) {
    const errors = [];
    if (carrier.baseRateUSD < 0)
        errors.push("baseRateUSD must be >= 0");
    if (carrier.ratePerKgUSD < 0)
        errors.push("ratePerKgUSD must be >= 0");
    if (carrier.ratePerKmUSD < 0)
        errors.push("ratePerKmUSD must be >= 0");
    if (carrier.avgDeliveryDays <= 0)
        errors.push("avgDeliveryDays must be > 0");
    if (carrier.onTimeRate < 0 || carrier.onTimeRate > 100)
        errors.push("onTimeRate must be between 0 and 100");
    if (carrier.maxWeightKg <= 0)
        errors.push("maxWeightKg must be > 0");
    if (!carrier.operatesIn || carrier.operatesIn.length === 0)
        errors.push("operatesIn must contain at least 1 country");
    return { valid: errors.length === 0, errors };
}
